import json
from unittest.mock import MagicMock, patch

import pytest

from printing.services.protocol import MessageType, ServerMessage
from printing.services.ws_client import PropsWebSocketClient


class TestPropsWebSocketClient:
    def test_init(self):
        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://beams.example.com/ws/print-service/",
            pairing_token="token-123",
            client_name="Test Printer",
        )
        assert client.connection_id == 1
        assert client.server_url == "wss://beams.example.com/ws/print-service/"
        assert client.pairing_token == "token-123"

    def test_backoff_calculation(self):
        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
        )
        assert client._get_backoff_delay(0) == 1
        assert client._get_backoff_delay(1) == 2
        assert client._get_backoff_delay(2) == 4
        assert client._get_backoff_delay(10) == 60  # capped at 60

    @pytest.mark.asyncio
    async def test_build_printer_info(self):
        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
        )
        with patch("printing.services.ws_client.Printer") as MockPrinter:
            mock_printer = MagicMock()
            mock_printer.pk = 1
            mock_printer.name = "Zebra"
            mock_printer.status = "online"
            mock_printer.default_template = MagicMock()
            mock_printer.default_template.name = "Square"
            MockPrinter.objects.filter.return_value.select_related.return_value = [
                mock_printer
            ]
            info = await client._build_printer_info()
            assert len(info) == 1
            assert info[0]["name"] == "Zebra"
            assert info[0]["id"] == "1"
            assert info[0]["templates"] == ["Square"]


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_auth_result_success_rotates_token(self):
        received_tokens = []

        async def mock_token_received(conn_id, token):
            received_tokens.append((conn_id, token))

        async def mock_status_change(conn_id, status):
            pass

        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
            pairing_token="old-token",
            on_token_received=mock_token_received,
            on_status_change=mock_status_change,
        )
        mock_ws = MagicMock()
        message = ServerMessage(
            type=MessageType.AUTH_RESULT,
            data={
                "success": True,
                "server_name": "PROPS",
                "new_token": "rotated-token",
            },
        )
        await client._handle_message(message, mock_ws)
        assert client.pairing_token == "rotated-token"
        assert received_tokens == [(1, "rotated-token")]

    @pytest.mark.asyncio
    async def test_auth_result_success_without_new_token(self):
        async def mock_status_change(conn_id, status):
            pass

        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
            pairing_token="existing-token",
            on_status_change=mock_status_change,
        )
        mock_ws = MagicMock()
        message = ServerMessage(
            type=MessageType.AUTH_RESULT,
            data={"success": True, "server_name": "PROPS"},
        )
        await client._handle_message(message, mock_ws)
        assert client.pairing_token == "existing-token"

    @pytest.mark.asyncio
    async def test_print_sends_ack_before_processing(self):
        sent_messages = []

        async def mock_send(m):
            sent_messages.append(m)

        mock_ws = MagicMock()
        mock_ws.send = mock_send

        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
        )
        message = ServerMessage(
            type=MessageType.PRINT,
            data={
                "job_id": "test-job-1",
                "printer_id": "1",
                "barcode": "ABC123",
                "asset_name": "Mic",
                "category_name": "Audio",
            },
        )
        await client._handle_message(message, mock_ws)

        first_msg = json.loads(sent_messages[0])
        assert first_msg["type"] == "print_ack"
        assert first_msg["job_id"] == "test-job-1"
        second_msg = json.loads(sent_messages[1])
        assert second_msg["type"] == "print_status"

    @pytest.mark.asyncio
    async def test_pairing_pending_is_handled(self):
        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
        )
        mock_ws = MagicMock()
        message = ServerMessage(
            type=MessageType.PAIRING_PENDING,
            data={"message": "Waiting for admin approval"},
        )
        # Should not raise
        await client._handle_message(message, mock_ws)

    @pytest.mark.asyncio
    async def test_error_message_sets_error_status(self):
        statuses = []

        async def mock_status_change(conn_id, status):
            statuses.append((conn_id, status))

        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
            on_status_change=mock_status_change,
        )
        mock_ws = MagicMock()
        message = ServerMessage(
            type=MessageType.ERROR,
            data={"code": "INVALID_TOKEN", "message": "Token expired"},
        )
        await client._handle_message(message, mock_ws)
        assert (1, "error") in statuses

    @pytest.mark.asyncio
    async def test_force_disconnect_stops_client(self):
        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
        )
        client._running = True
        mock_ws = MagicMock()
        message = ServerMessage(
            type=MessageType.FORCE_DISCONNECT,
            data={"reason": "Server shutting down"},
        )
        await client._handle_message(message, mock_ws)
        assert client._running is False
