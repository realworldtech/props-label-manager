import pytest
from unittest.mock import patch
from printing.models import (
    LabelTemplate,
    LabelElement,
    ElementType,
    FontChoices,
    TextAlign,
    Printer,
    PrintJob,
    PropsConnection,
    JobStatus,
)
from printing.services.job_processor import process_print_job


@pytest.mark.django_db
class TestFullPrintFlow:
    def test_end_to_end_print_job(self):
        """Test complete flow: create job -> render PDF -> send to printer."""
        # Setup template
        template = LabelTemplate.objects.create(
            name="Integration Test", width_mm=62, height_mm=62
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.QR_CODE,
            x_mm=6,
            y_mm=7,
            width_mm=50,
            height_mm=50,
            sort_order=1,
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.ASSET_NAME,
            x_mm=2,
            y_mm=1,
            width_mm=58,
            height_mm=5,
            font_name=FontChoices.HELVETICA,
            font_size_pt=7,
            font_bold=True,
            text_align=TextAlign.CENTER,
            max_chars=20,
            sort_order=2,
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.BARCODE_TEXT,
            x_mm=2,
            y_mm=57,
            width_mm=58,
            height_mm=4,
            font_name=FontChoices.COURIER,
            font_size_pt=5,
            text_align=TextAlign.CENTER,
            sort_order=3,
        )

        # Setup printer and connection
        printer = Printer.objects.create(
            name="Test Printer", ip_address="192.168.1.100"
        )
        connection = PropsConnection.objects.create(
            name="Test Server",
            server_url="wss://test.example.com/ws/print-service/",
        )

        # Create job
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            props_connection=connection,
            barcode="BEAMS-TESTTEST",
            asset_name="Test Microphone",
            category_name="Audio Equipment",
            quantity=2,
        )

        # Process with mocked printer (only mock the socket, not the renderer)
        with patch("printing.services.printer.socket.socket") as mock_socket_cls:
            mock_socket = mock_socket_cls.return_value
            process_print_job(job)

            # Verify PDF was sent to printer via socket
            mock_socket.connect.assert_called_once_with(("192.168.1.100", 9100))
            mock_socket.sendall.assert_called_once()
            pdf_data = mock_socket.sendall.call_args[0][0]
            assert pdf_data[:5] == b"%PDF-"

        # Verify job completed
        job.refresh_from_db()
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        assert job.error_message is None
