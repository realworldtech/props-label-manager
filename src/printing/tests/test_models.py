import pytest
from printing.models import (
    LabelTemplate, LabelElement, FontChoices, ElementType, TextAlign,
    Printer, PropsConnection, PrintJob,
    ConnectionStatus, PrinterStatus, JobStatus,
)


@pytest.mark.django_db
class TestLabelTemplate:
    def test_create_template(self):
        template = LabelTemplate.objects.create(
            name="Square 62x62mm",
            width_mm=62,
            height_mm=62,
        )
        assert template.name == "Square 62x62mm"
        assert template.width_mm == 62
        assert template.height_mm == 62
        assert template.background_color == "#FFFFFF"
        assert template.is_default is False
        assert str(template) == "Square 62x62mm (62x62mm)"

    def test_only_one_default(self):
        t1 = LabelTemplate.objects.create(
            name="Template 1", width_mm=62, height_mm=62, is_default=True
        )
        t2 = LabelTemplate.objects.create(
            name="Template 2", width_mm=62, height_mm=29, is_default=True
        )
        t1.refresh_from_db()
        assert t1.is_default is False
        assert t2.is_default is True


@pytest.mark.django_db
class TestLabelElement:
    def test_create_element(self):
        template = LabelTemplate.objects.create(
            name="Test", width_mm=62, height_mm=62
        )
        element = LabelElement.objects.create(
            template=template,
            element_type=ElementType.BARCODE_128,
            x_mm=5,
            y_mm=10,
            width_mm=50,
            height_mm=15,
            sort_order=1,
        )
        assert element.element_type == "barcode_128"
        assert element.rotation == 0
        assert element.font_bold is False

    def test_text_element_with_font(self):
        template = LabelTemplate.objects.create(
            name="Test", width_mm=62, height_mm=62
        )
        element = LabelElement.objects.create(
            template=template,
            element_type=ElementType.ASSET_NAME,
            x_mm=5,
            y_mm=40,
            width_mm=50,
            height_mm=10,
            font_name=FontChoices.HELVETICA,
            font_size_pt=12,
            font_bold=True,
            text_align=TextAlign.CENTER,
            max_chars=20,
            sort_order=2,
        )
        assert element.font_name == "helvetica"
        assert element.text_align == "center"

    def test_element_ordering(self):
        template = LabelTemplate.objects.create(
            name="Test", width_mm=62, height_mm=62
        )
        e2 = LabelElement.objects.create(
            template=template, element_type=ElementType.QR_CODE,
            x_mm=0, y_mm=0, width_mm=10, height_mm=10, sort_order=2
        )
        e1 = LabelElement.objects.create(
            template=template, element_type=ElementType.BARCODE_128,
            x_mm=0, y_mm=0, width_mm=10, height_mm=10, sort_order=1
        )
        elements = list(template.elements.all())
        assert elements[0] == e1
        assert elements[1] == e2


@pytest.mark.django_db
class TestPrinter:
    def test_create_printer(self):
        printer = Printer.objects.create(
            name="Warehouse Zebra",
            ip_address="192.168.1.100",
        )
        assert printer.port == 9100
        assert printer.is_active is True
        assert printer.status == "unknown"
        assert str(printer) == "Warehouse Zebra (192.168.1.100:9100)"

    def test_printer_with_default_template(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(
            name="Office", ip_address="10.0.0.50",
            default_template=template,
        )
        assert printer.default_template == template


@pytest.mark.django_db
class TestPropsConnection:
    def test_create_connection(self):
        conn = PropsConnection.objects.create(
            name="BeaMS Production",
            server_url="wss://beams.example.com/ws/print-service/",
        )
        assert conn.is_active is True
        assert conn.status == "disconnected"
        assert conn.pairing_token is None
        assert str(conn) == "BeaMS Production"

    def test_connection_with_token(self):
        conn = PropsConnection.objects.create(
            name="BeaMS",
            server_url="wss://beams.example.com/ws/print-service/",
            pairing_token="secret-token-123",
        )
        assert conn.pairing_token == "secret-token-123"
        assert conn.is_paired is True

    def test_unpaired_connection(self):
        conn = PropsConnection.objects.create(
            name="BeaMS",
            server_url="wss://beams.example.com/ws/print-service/",
        )
        assert conn.is_paired is False


@pytest.mark.django_db
class TestPrintJob:
    def test_create_print_job(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(
            name="Zebra", ip_address="192.168.1.100"
        )
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            barcode="BEAMS-A1B2C3D4",
            asset_name="Wireless Mic",
            category_name="Audio",
        )
        assert job.status == "queued"
        assert job.quantity == 1
        assert job.props_connection is None
        assert job.completed_at is None
        assert str(job) == "BEAMS-A1B2C3D4 - queued"

    def test_print_job_with_connection(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(
            name="Zebra", ip_address="192.168.1.100"
        )
        conn = PropsConnection.objects.create(
            name="BeaMS", server_url="wss://beams.example.com/ws/print-service/"
        )
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            props_connection=conn,
            barcode="BEAMS-DEADBEEF",
            asset_name="Camera",
            category_name="Video",
            quantity=3,
        )
        assert job.props_connection == conn
        assert job.quantity == 3
