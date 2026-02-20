import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone
from printing.models import (
    LabelTemplate, LabelElement, ElementType, FontChoices, TextAlign,
    Printer, PrintJob, JobStatus,
)
from printing.services.job_processor import process_print_job
from printing.services.printer import PrintError


@pytest.mark.django_db
class TestJobProcessor:
    def _setup(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        LabelElement.objects.create(
            template=template, element_type=ElementType.BARCODE_TEXT,
            x_mm=2, y_mm=50, width_mm=58, height_mm=5,
            font_name=FontChoices.COURIER, font_size_pt=8,
            text_align=TextAlign.CENTER, sort_order=1
        )
        printer = Printer.objects.create(
            name="Test", ip_address="192.168.1.100"
        )
        return template, printer

    @patch("printing.services.job_processor.PrinterService")
    @patch("printing.services.job_processor.LabelRenderer")
    def test_successful_job(self, MockRenderer, MockPrinterService):
        template, printer = self._setup()
        MockRenderer.return_value.render.return_value = b"%PDF-fake"
        job = PrintJob.objects.create(
            printer=printer, template=template,
            barcode="BEAMS-12345678", asset_name="Test", category_name="Cat"
        )
        process_print_job(job)
        job.refresh_from_db()
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None

    @patch("printing.services.job_processor.PrinterService")
    @patch("printing.services.job_processor.LabelRenderer")
    def test_render_failure(self, MockRenderer, MockPrinterService):
        template, printer = self._setup()
        MockRenderer.return_value.render.side_effect = Exception("render error")
        job = PrintJob.objects.create(
            printer=printer, template=template,
            barcode="BEAMS-12345678", asset_name="Test", category_name="Cat"
        )
        process_print_job(job)
        job.refresh_from_db()
        assert job.status == JobStatus.FAILED
        assert "render error" in job.error_message

    @patch("printing.services.job_processor.PrinterService")
    @patch("printing.services.job_processor.LabelRenderer")
    def test_print_failure(self, MockRenderer, MockPrinterService):
        template, printer = self._setup()
        MockRenderer.return_value.render.return_value = b"%PDF-fake"
        MockPrinterService.return_value.send.side_effect = PrintError("connection refused")
        job = PrintJob.objects.create(
            printer=printer, template=template,
            barcode="BEAMS-12345678", asset_name="Test", category_name="Cat"
        )
        process_print_job(job)
        job.refresh_from_db()
        assert job.status == JobStatus.FAILED
        assert "connection refused" in job.error_message

    @patch("printing.services.job_processor.PrinterService")
    @patch("printing.services.job_processor.LabelRenderer")
    def test_job_passes_quantity(self, MockRenderer, MockPrinterService):
        template, printer = self._setup()
        MockRenderer.return_value.render.return_value = b"%PDF-fake"
        job = PrintJob.objects.create(
            printer=printer, template=template,
            barcode="BEAMS-12345678", asset_name="Test", category_name="Cat",
            quantity=5,
        )
        process_print_job(job)
        MockRenderer.return_value.render.assert_called_once_with(
            barcode_text="BEAMS-12345678",
            asset_name="Test",
            category_name="Cat",
            quantity=5,
        )
