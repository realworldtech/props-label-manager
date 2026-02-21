import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from printing.models import (
    ElementType,
    FontChoices,
    JobStatus,
    LabelElement,
    LabelTemplate,
    LabelType,
    Printer,
    PrintJob,
    TextAlign,
)
from printing.services.job_processor import process_print_job
from printing.services.label_renderer import LabelRenderer
from printing.services.protocol import (
    ProtocolError,
    parse_server_message,
)


class TestLocationProtocol:
    """Protocol validation for location label messages."""

    def test_parse_location_print_message(self):
        raw = json.dumps(
            {
                "type": "print",
                "label_type": "location",
                "job_id": "pj-abc123",
                "printer_id": "1",
                "location_name": "Storage Room A",
                "location_description": "Ground floor",
                "location_categories": "Audio, Lighting",
                "location_departments": "Sound",
                "qr_content": "https://props.example.com/locations/42/",
                "quantity": 1,
            }
        )
        msg = parse_server_message(raw)
        assert msg.data["label_type"] == "location"
        assert msg.data["location_name"] == "Storage Room A"

    def test_location_message_requires_location_name(self):
        raw = json.dumps(
            {
                "type": "print",
                "label_type": "location",
                "job_id": "pj-abc123",
                "printer_id": "1",
            }
        )
        with pytest.raises(ProtocolError, match="location_name"):
            parse_server_message(raw)

    def test_location_message_does_not_require_barcode(self):
        raw = json.dumps(
            {
                "type": "print",
                "label_type": "location",
                "job_id": "pj-abc123",
                "printer_id": "1",
                "location_name": "Room B",
            }
        )
        msg = parse_server_message(raw)
        assert msg.data["location_name"] == "Room B"
        assert "barcode" not in msg.data

    def test_asset_message_still_requires_barcode(self):
        raw = json.dumps(
            {
                "type": "print",
                "label_type": "asset",
                "job_id": "pj-abc123",
                "printer_id": "1",
                "asset_name": "Mic",
                "category_name": "Audio",
            }
        )
        with pytest.raises(ProtocolError, match="barcode"):
            parse_server_message(raw)

    def test_missing_label_type_defaults_to_asset(self):
        raw = json.dumps(
            {
                "type": "print",
                "job_id": "pj-abc123",
                "printer_id": "1",
                "barcode": "BEAMS-001",
                "asset_name": "Mic",
                "category_name": "Audio",
            }
        )
        msg = parse_server_message(raw)
        assert "label_type" not in msg.data or msg.data.get("label_type") == "asset"


@pytest.mark.django_db
class TestLocationLabelRenderer:
    """LabelRenderer handles location element types."""

    def _create_location_template(self):
        template = LabelTemplate.objects.create(
            name="Box Label", width_mm=62, height_mm=62
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.LOCATION_NAME,
            x_mm=2,
            y_mm=2,
            width_mm=58,
            height_mm=6,
            font_name=FontChoices.HELVETICA,
            font_size_pt=12,
            font_bold=True,
            text_align=TextAlign.CENTER,
            sort_order=1,
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.LOCATION_DESCRIPTION,
            x_mm=2,
            y_mm=10,
            width_mm=58,
            height_mm=5,
            font_name=FontChoices.HELVETICA,
            font_size_pt=8,
            text_align=TextAlign.LEFT,
            sort_order=2,
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.LOCATION_CATEGORIES,
            x_mm=2,
            y_mm=17,
            width_mm=58,
            height_mm=5,
            font_name=FontChoices.HELVETICA,
            font_size_pt=8,
            text_align=TextAlign.LEFT,
            sort_order=3,
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.LOCATION_DEPARTMENTS,
            x_mm=2,
            y_mm=24,
            width_mm=58,
            height_mm=5,
            font_name=FontChoices.HELVETICA,
            font_size_pt=8,
            text_align=TextAlign.LEFT,
            sort_order=4,
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.QR_CODE,
            x_mm=16,
            y_mm=32,
            width_mm=30,
            height_mm=30,
            sort_order=5,
        )
        return template

    def test_render_location_label_returns_pdf(self):
        template = self._create_location_template()
        renderer = LabelRenderer(template)
        pdf_bytes = renderer.render(
            barcode_text="",
            asset_name="",
            category_name="",
            qr_content="https://props.example.com/locations/42/",
            location_name="Storage Room A",
            location_description="Ground floor, behind reception",
            location_categories="Audio Equipment, Lighting, Cables",
            location_departments="Sound, Lighting",
        )
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_render_location_name_element(self):
        template = LabelTemplate.objects.create(
            name="Name Only", width_mm=62, height_mm=20
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.LOCATION_NAME,
            x_mm=2,
            y_mm=2,
            width_mm=58,
            height_mm=10,
            font_name=FontChoices.HELVETICA,
            font_size_pt=12,
            sort_order=1,
        )
        renderer = LabelRenderer(template)
        pdf_bytes = renderer.render(
            barcode_text="",
            asset_name="",
            category_name="",
            location_name="Warehouse B",
        )
        assert pdf_bytes[:5] == b"%PDF-"


@pytest.mark.django_db
class TestLocationJobProcessor:
    """Job processor handles location print jobs."""

    def _setup(self):
        template = LabelTemplate.objects.create(
            name="Box Label", width_mm=62, height_mm=62
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.LOCATION_NAME,
            x_mm=2,
            y_mm=2,
            width_mm=58,
            height_mm=6,
            font_name=FontChoices.HELVETICA,
            font_size_pt=12,
            sort_order=1,
        )
        printer = Printer.objects.create(name="Test", ip_address="192.168.1.100")
        return template, printer

    @patch("printing.services.job_processor.PrinterService")
    @patch("printing.services.job_processor.LabelRenderer")
    def test_location_job_completes(self, MockRenderer, MockPrinterService):
        template, printer = self._setup()
        MockRenderer.return_value.render.return_value = b"%PDF-fake"
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            label_type=LabelType.LOCATION,
            location_name="Storage Room A",
            location_description="Ground floor",
            location_categories="Audio, Lighting",
            location_departments="Sound",
            qr_content="https://props.example.com/locations/42/",
        )
        process_print_job(job)
        job.refresh_from_db()
        assert job.status == JobStatus.COMPLETED

    @patch("printing.services.job_processor.PrinterService")
    @patch("printing.services.job_processor.LabelRenderer")
    def test_location_job_passes_fields_to_renderer(
        self, MockRenderer, MockPrinterService
    ):
        template, printer = self._setup()
        MockRenderer.return_value.render.return_value = b"%PDF-fake"
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            label_type=LabelType.LOCATION,
            location_name="Storage Room A",
            location_description="Ground floor",
            location_categories="Audio, Lighting",
            location_departments="Sound",
            qr_content="https://props.example.com/locations/42/",
        )
        process_print_job(job)
        MockRenderer.return_value.render.assert_called_once_with(
            barcode_text="",
            asset_name="",
            category_name="",
            qr_content="https://props.example.com/locations/42/",
            quantity=1,
            department_name="",
            site_short_name="",
            location_name="Storage Room A",
            location_description="Ground floor",
            location_categories="Audio, Lighting",
            location_departments="Sound",
        )


@pytest.mark.django_db
class TestLocationDesignerPreview:
    """Designer preview includes location sample data."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client = Client()
        self.client.login(username="testuser", password="testpass")
        self.template = LabelTemplate.objects.create(
            name="Location Label", width_mm=62, height_mm=62
        )
        LabelElement.objects.create(
            template=self.template,
            element_type=ElementType.LOCATION_NAME,
            x_mm=2,
            y_mm=2,
            width_mm=58,
            height_mm=6,
            font_name=FontChoices.HELVETICA,
            font_size_pt=12,
            sort_order=1,
        )

    def test_preview_renders_location_elements(self):
        url = reverse("label-designer-preview", kwargs={"pk": self.template.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response.content[:5] == b"%PDF-"


@pytest.mark.django_db
class TestLocationPrintJobModel:
    """PrintJob model stores location fields correctly."""

    def test_create_location_print_job(self):
        template = LabelTemplate.objects.create(
            name="Box Label", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(name="Test", ip_address="192.168.1.100")
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            label_type=LabelType.LOCATION,
            location_name="Storage Room A",
            location_description="Ground floor, behind reception",
            location_categories="Audio Equipment, Lighting",
            location_departments="Sound, Lighting",
            qr_content="https://props.example.com/locations/42/",
        )
        job.refresh_from_db()
        assert job.label_type == LabelType.LOCATION
        assert job.location_name == "Storage Room A"
        assert job.location_description == "Ground floor, behind reception"
        assert job.location_categories == "Audio Equipment, Lighting"
        assert job.location_departments == "Sound, Lighting"

    def test_default_label_type_is_asset(self):
        template = LabelTemplate.objects.create(
            name="Default", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(name="Test", ip_address="192.168.1.100")
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            barcode="BEAMS-001",
            asset_name="Mic",
            category_name="Audio",
        )
        assert job.label_type == LabelType.ASSET

    def test_location_fields_default_empty(self):
        template = LabelTemplate.objects.create(
            name="Default", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(name="Test", ip_address="192.168.1.100")
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            barcode="BEAMS-001",
            asset_name="Mic",
            category_name="Audio",
        )
        assert job.location_name == ""
        assert job.location_description == ""
        assert job.location_categories == ""
        assert job.location_departments == ""
