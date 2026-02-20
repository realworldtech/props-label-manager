import pytest
from unittest.mock import patch, MagicMock
from django.core.management import call_command
from io import StringIO
from printing.models import PropsConnection


@pytest.mark.django_db
class TestRunPrintClientCommand:
    def test_no_active_connections(self):
        out = StringIO()
        with patch("printing.management.commands.run_print_client.asyncio") as mock_asyncio:
            mock_asyncio.run = MagicMock()
            call_command("run_print_client", stdout=out)
            output = out.getvalue()
            assert "No active connections" in output

    def test_lists_active_connections(self):
        PropsConnection.objects.create(
            name="BeaMS Test",
            server_url="wss://beams.example.com/ws/print-service/",
            pairing_token="test-token",
            is_active=True,
        )
        out = StringIO()
        with patch("printing.management.commands.run_print_client.asyncio") as mock_asyncio:
            mock_asyncio.run = MagicMock()
            call_command("run_print_client", stdout=out)
            output = out.getvalue()
            assert "BeaMS Test" in output
