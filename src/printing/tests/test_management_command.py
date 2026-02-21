import asyncio
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.core.management import call_command

from printing.management.commands.run_print_client import Command
from printing.models import PropsConnection


@pytest.mark.django_db
class TestRunPrintClientCommand:
    def test_handle_starts_async_run(self):
        out = StringIO()
        with patch(
            "printing.management.commands.run_print_client.asyncio"
        ) as mock_asyncio:
            mock_asyncio.run = MagicMock()
            call_command("run_print_client", stdout=out)
            output = out.getvalue()
            assert "Starting print client" in output
            assert "syncing connections every 10s" in output
            mock_asyncio.run.assert_called_once()


def _make_ws_mock():
    """Create a PropsWebSocketClient mock with async connect."""
    mock = MagicMock()
    mock.return_value.connect = AsyncMock()
    return mock


@pytest.mark.django_db(transaction=True)
class TestSyncConnections:
    def _make_command(self):
        cmd = Command()
        cmd._clients = {}
        cmd._tasks = {}
        cmd._client_name = "Test Client"
        return cmd

    @pytest.mark.asyncio
    async def test_starts_clients_for_active_connections(self):
        conn = await asyncio.to_thread(
            PropsConnection.objects.create,
            name="Server A",
            server_url="wss://server-a.example.com/ws/",
            pairing_token="token-a",
            is_active=True,
        )
        cmd = self._make_command()

        with patch(
            "printing.management.commands.run_print_client.PropsWebSocketClient",
            new_callable=_make_ws_mock,
        ) as MockClient:
            await cmd._sync_connections()

            assert conn.pk in cmd._clients
            assert conn.pk in cmd._tasks
            MockClient.assert_called_once()
            call_kwargs = MockClient.call_args[1]
            assert call_kwargs["connection_id"] == conn.pk
            assert call_kwargs["server_url"] == conn.server_url
            assert call_kwargs["client_name"] == "Test Client"

    @pytest.mark.asyncio
    async def test_stops_clients_for_deactivated_connections(self):
        conn = await asyncio.to_thread(
            PropsConnection.objects.create,
            name="Server B",
            server_url="wss://server-b.example.com/ws/",
            pairing_token="token-b",
            is_active=True,
        )
        cmd = self._make_command()

        mock_client = MagicMock()
        cmd._clients[conn.pk] = mock_client
        cmd._tasks[conn.pk] = MagicMock()

        # Deactivate the connection
        conn.is_active = False
        await asyncio.to_thread(conn.save)

        with patch(
            "printing.management.commands.run_print_client.PropsWebSocketClient",
            new_callable=_make_ws_mock,
        ):
            await cmd._sync_connections()

        assert conn.pk not in cmd._clients
        assert conn.pk not in cmd._tasks
        mock_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_idempotent_when_nothing_changes(self):
        conn = await asyncio.to_thread(
            PropsConnection.objects.create,
            name="Server C",
            server_url="wss://server-c.example.com/ws/",
            pairing_token="token-c",
            is_active=True,
        )
        cmd = self._make_command()

        mock_client = MagicMock()
        cmd._clients[conn.pk] = mock_client
        cmd._tasks[conn.pk] = MagicMock()

        with patch(
            "printing.management.commands.run_print_client.PropsWebSocketClient",
            new_callable=_make_ws_mock,
        ) as MockClient:
            await cmd._sync_connections()

            # No new clients created, no clients stopped
            MockClient.assert_not_called()
            mock_client.stop.assert_not_called()
            assert conn.pk in cmd._clients

    @pytest.mark.asyncio
    async def test_adds_new_connection_while_existing_runs(self):
        conn_a = await asyncio.to_thread(
            PropsConnection.objects.create,
            name="Server D",
            server_url="wss://server-d.example.com/ws/",
            pairing_token="token-d",
            is_active=True,
        )
        cmd = self._make_command()

        mock_client_a = MagicMock()
        cmd._clients[conn_a.pk] = mock_client_a
        cmd._tasks[conn_a.pk] = MagicMock()

        # Add a second connection
        conn_b = await asyncio.to_thread(
            PropsConnection.objects.create,
            name="Server E",
            server_url="wss://server-e.example.com/ws/",
            pairing_token="token-e",
            is_active=True,
        )

        with patch(
            "printing.management.commands.run_print_client.PropsWebSocketClient",
            new_callable=_make_ws_mock,
        ) as MockClient:
            await cmd._sync_connections()

            # Original still running, new one started
            assert conn_a.pk in cmd._clients
            assert conn_b.pk in cmd._clients
            mock_client_a.stop.assert_not_called()
            MockClient.assert_called_once()
            assert MockClient.call_args[1]["connection_id"] == conn_b.pk

    def test_get_desired_connections_returns_active_only(self):
        active = PropsConnection.objects.create(
            name="Active",
            server_url="wss://active.example.com/ws/",
            pairing_token="token-123",
            is_active=True,
        )
        inactive = PropsConnection.objects.create(
            name="Inactive",
            server_url="wss://inactive.example.com/ws/",
            pairing_token="token-456",
            is_active=False,
        )

        cmd = self._make_command()
        result = cmd._get_desired_connections()

        assert active.pk in result
        assert inactive.pk not in result
        assert result[active.pk]["server_url"] == active.server_url
