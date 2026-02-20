from unittest.mock import MagicMock, patch

import pytest

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
