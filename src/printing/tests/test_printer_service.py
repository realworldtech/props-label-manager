import pytest
from unittest.mock import patch, MagicMock
from printing.services.printer import PrinterService, PrintError


class TestPrinterService:
    def test_send_to_printer_success(self):
        mock_socket = MagicMock()
        with patch("printing.services.printer.socket.socket", return_value=mock_socket):
            service = PrinterService("192.168.1.100", 9100)
            service.send(b"%PDF-fake-data")
            mock_socket.connect.assert_called_once_with(("192.168.1.100", 9100))
            mock_socket.sendall.assert_called_once_with(b"%PDF-fake-data")
            mock_socket.close.assert_called_once()

    def test_send_to_printer_connection_error(self):
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = ConnectionRefusedError("refused")
        with patch("printing.services.printer.socket.socket", return_value=mock_socket):
            service = PrinterService("192.168.1.100", 9100)
            with pytest.raises(PrintError, match="Failed to connect"):
                service.send(b"%PDF-fake-data")

    def test_send_to_printer_timeout(self):
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = TimeoutError("timed out")
        with patch("printing.services.printer.socket.socket", return_value=mock_socket):
            service = PrinterService("192.168.1.100", 9100)
            with pytest.raises(PrintError, match="Failed to connect"):
                service.send(b"%PDF-fake-data")

    def test_send_sets_timeout(self):
        mock_socket = MagicMock()
        with patch("printing.services.printer.socket.socket", return_value=mock_socket):
            service = PrinterService("192.168.1.100", 9100, timeout=10)
            service.send(b"data")
            mock_socket.settimeout.assert_called_once_with(10)
