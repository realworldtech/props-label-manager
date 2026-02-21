import pytest
from django.core.exceptions import ValidationError

from printing.models import (
    ElementType,
    FontChoices,
    LabelElement,
    LabelTemplate,
    Printer,
    PrinterType,
    PrintJob,
    PropsConnection,
    TextAlign,
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
        template = LabelTemplate.objects.create(name="Test", width_mm=62, height_mm=62)
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
        template = LabelTemplate.objects.create(name="Test", width_mm=62, height_mm=62)
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

    def test_department_name_element_type(self):
        assert ElementType.DEPARTMENT_NAME == "department_name"

    def test_site_short_name_element_type(self):
        assert ElementType.SITE_SHORT_NAME == "site_short_name"

    def test_element_ordering(self):
        template = LabelTemplate.objects.create(name="Test", width_mm=62, height_mm=62)
        e2 = LabelElement.objects.create(
            template=template,
            element_type=ElementType.QR_CODE,
            x_mm=0,
            y_mm=0,
            width_mm=10,
            height_mm=10,
            sort_order=2,
        )
        e1 = LabelElement.objects.create(
            template=template,
            element_type=ElementType.BARCODE_128,
            x_mm=0,
            y_mm=0,
            width_mm=10,
            height_mm=10,
            sort_order=1,
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

    def test_cups_printer_str(self):
        printer = Printer.objects.create(
            name="Dymo 5XL",
            printer_type=PrinterType.CUPS,
            cups_queue="DYMO_LabelWriter_5XL",
        )
        assert str(printer) == "Dymo 5XL (CUPS: DYMO_LabelWriter_5XL)"

    def test_cups_printer_str_with_server(self):
        printer = Printer.objects.create(
            name="Dymo 5XL",
            printer_type=PrinterType.CUPS,
            cups_queue="DYMO-5XL",
            cups_server="dymo-5xl:631",
        )
        assert str(printer) == "Dymo 5XL (CUPS: DYMO-5XL @ dymo-5xl:631)"

    def test_virtual_printer_str(self):
        printer = Printer.objects.create(
            name="PDF Output",
            printer_type=PrinterType.VIRTUAL,
        )
        assert str(printer) == "PDF Output (Virtual)"

    def test_clean_tcp_requires_ip_address(self):
        printer = Printer(name="TCP No IP", printer_type=PrinterType.TCP)
        with pytest.raises(ValidationError) as exc_info:
            printer.clean()
        assert "ip_address" in exc_info.value.message_dict

    def test_clean_tcp_with_ip_passes(self):
        printer = Printer(
            name="TCP OK", printer_type=PrinterType.TCP, ip_address="192.168.1.1"
        )
        printer.clean()

    def test_clean_cups_requires_queue(self):
        printer = Printer(name="CUPS No Queue", printer_type=PrinterType.CUPS)
        with pytest.raises(ValidationError) as exc_info:
            printer.clean()
        assert "cups_queue" in exc_info.value.message_dict

    def test_clean_cups_with_queue_passes(self):
        printer = Printer(
            name="CUPS OK",
            printer_type=PrinterType.CUPS,
            cups_queue="DYMO_LabelWriter_5XL",
        )
        printer.clean()

    def test_clean_virtual_no_requirements(self):
        printer = Printer(name="Virtual", printer_type=PrinterType.VIRTUAL)
        printer.clean()

    def test_printer_with_default_template(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(
            name="Office",
            ip_address="10.0.0.50",
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

    def test_server_url_normalizes_bare_hostname(self):
        conn = PropsConnection(name="Test", server_url="props.example.com")
        conn.full_clean()
        assert conn.server_url == "wss://props.example.com/ws/print-service/"

    def test_server_url_normalizes_https_url(self):
        conn = PropsConnection(name="Test", server_url="https://props.example.com")
        conn.full_clean()
        assert conn.server_url == "wss://props.example.com/ws/print-service/"

    def test_server_url_normalizes_http_url(self):
        conn = PropsConnection(name="Test", server_url="http://localhost:8000")
        conn.full_clean()
        assert conn.server_url == "ws://localhost:8000/ws/print-service/"

    def test_server_url_preserves_correct_wss_url(self):
        conn = PropsConnection(
            name="Test",
            server_url="wss://props.example.com/ws/print-service/",
        )
        conn.full_clean()
        assert conn.server_url == "wss://props.example.com/ws/print-service/"

    def test_server_url_normalizes_https_with_trailing_slash(self):
        conn = PropsConnection(name="Test", server_url="https://props.example.com/")
        conn.full_clean()
        assert conn.server_url == "wss://props.example.com/ws/print-service/"

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
        printer = Printer.objects.create(name="Zebra", ip_address="192.168.1.100")
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

    def test_print_job_with_qr_content(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(name="Zebra", ip_address="192.168.1.100")
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            barcode="BEAMS-A1B2C3D4",
            asset_name="Wireless Mic",
            category_name="Audio",
            qr_content="https://beams.example.com/assets/A1B2C3D4",
        )
        assert job.qr_content == "https://beams.example.com/assets/A1B2C3D4"

    def test_print_job_qr_content_defaults_blank(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(name="Zebra", ip_address="192.168.1.100")
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            barcode="BEAMS-A1B2C3D4",
            asset_name="Wireless Mic",
            category_name="Audio",
        )
        assert job.qr_content is None

    def test_print_job_with_connection(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(name="Zebra", ip_address="192.168.1.100")
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

    def test_print_job_with_department_and_site(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(name="Zebra", ip_address="192.168.1.100")
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            barcode="BEAMS-A1B2C3D4",
            asset_name="Wireless Mic",
            category_name="Audio",
            department_name="Technical",
            site_short_name="HDM",
        )
        assert job.department_name == "Technical"
        assert job.site_short_name == "HDM"

    def test_print_job_department_and_site_default_blank(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(name="Zebra", ip_address="192.168.1.100")
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            barcode="BEAMS-A1B2C3D4",
            asset_name="Wireless Mic",
            category_name="Audio",
        )
        assert job.department_name == ""
        assert job.site_short_name == ""
