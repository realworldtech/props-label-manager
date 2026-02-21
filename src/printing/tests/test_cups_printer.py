import subprocess
from unittest.mock import patch

import pytest

from printing.services.cups_printer import CupsPrinterService
from printing.services.printer import PrintError


class TestCupsPrinterService:
    def test_send_success(self, tmp_path):
        service = CupsPrinterService("DYMO_LabelWriter_5XL")
        stdout = "request id is DYMO_LabelWriter_5XL-42 (1 file(s))\n"

        with patch("printing.services.cups_printer.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=stdout, stderr=""
            )
            job_id = service.send(b"%PDF-fake")

        assert job_id == "DYMO_LabelWriter_5XL-42"
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][0][:3] == ["lp", "-d", "DYMO_LabelWriter_5XL"]

    def test_send_nonzero_exit(self):
        service = CupsPrinterService("bad_queue")

        with patch("printing.services.cups_printer.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="lp: Unknown destination"
            )
            with pytest.raises(PrintError, match="lp command failed"):
                service.send(b"%PDF-fake")

    def test_send_timeout(self):
        service = CupsPrinterService("slow_queue", timeout=5)

        with patch("printing.services.cups_printer.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="lp", timeout=5)
            with pytest.raises(PrintError, match="timed out"):
                service.send(b"%PDF-fake")

    def test_send_lp_not_found(self):
        service = CupsPrinterService("any_queue")

        with patch("printing.services.cups_printer.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(PrintError, match="lp command not found"):
                service.send(b"%PDF-fake")

    def test_parse_job_id_standard(self):
        stdout = "request id is DYMO_LabelWriter_5XL-123 (1 file(s))\n"
        assert CupsPrinterService._parse_job_id(stdout) == "DYMO_LabelWriter_5XL-123"

    def test_parse_job_id_no_match(self):
        assert CupsPrinterService._parse_job_id("unexpected output") is None

    def test_send_with_server_includes_h_flag(self):
        service = CupsPrinterService("DYMO-5XL", server="dymo-5xl:631")
        stdout = "request id is DYMO-5XL-1 (1 file(s))\n"

        with patch("printing.services.cups_printer.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=stdout, stderr=""
            )
            service.send(b"%PDF-fake")

        args = mock_run.call_args[0][0]
        assert args[:5] == ["lp", "-h", "dymo-5xl:631", "-d", "DYMO-5XL"]

    def test_send_without_server_omits_h_flag(self):
        service = CupsPrinterService("DYMO-5XL")
        stdout = "request id is DYMO-5XL-1 (1 file(s))\n"

        with patch("printing.services.cups_printer.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=stdout, stderr=""
            )
            service.send(b"%PDF-fake")

        args = mock_run.call_args[0][0]
        assert args[:3] == ["lp", "-d", "DYMO-5XL"]
        assert "-h" not in args

    def test_send_returns_empty_string_when_no_job_id(self):
        service = CupsPrinterService("test_queue")

        with patch("printing.services.cups_printer.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="ok\n", stderr=""
            )
            job_id = service.send(b"%PDF-fake")

        assert job_id == ""
