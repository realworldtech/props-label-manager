from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse

from printing.models import (
    ElementType,
    FontChoices,
    JobStatus,
    LabelElement,
    LabelTemplate,
    Printer,
    PrinterType,
    PrintJob,
    TextAlign,
)

PROCESS_JOB = "printing.services.job_processor.process_print_job"


@pytest.fixture
def admin_client(db):
    from django.contrib.auth.models import User

    user = User.objects.create_superuser("admin", "admin@test.com", "password")
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def template(db):
    t = LabelTemplate.objects.create(name="Test Label", width_mm=62, height_mm=62)
    LabelElement.objects.create(
        template=t,
        element_type=ElementType.BARCODE_TEXT,
        x_mm=2,
        y_mm=50,
        width_mm=58,
        height_mm=5,
        font_name=FontChoices.COURIER,
        font_size_pt=8,
        text_align=TextAlign.CENTER,
        sort_order=1,
    )
    return t


@pytest.fixture
def printer(template):
    return Printer.objects.create(
        name="Test Printer",
        printer_type=PrinterType.VIRTUAL,
        ip_address="192.168.1.100",
        default_template=template,
    )


def _test_print_url(printer_pk):
    return f"/admin/printing/printer/{printer_pk}/test-print/"


@pytest.mark.django_db
class TestSendTestPrint:
    @patch(PROCESS_JOB)
    def test_successful_test_print(self, mock_process, admin_client, printer, template):
        def complete_job(job):
            job.status = JobStatus.COMPLETED
            job.save(update_fields=["status"])

        mock_process.side_effect = complete_job

        response = admin_client.post(_test_print_url(printer.pk))

        assert response.status_code == 302
        mock_process.assert_called_once()

        job = PrintJob.objects.get()
        assert job.printer == printer
        assert job.template == template
        assert job.barcode == "TEST-001"
        assert job.asset_name == "Test Print"
        assert response.url == reverse("admin:printing_printjob_change", args=[job.pk])

    def test_no_templates_shows_error(self, admin_client, db):
        LabelTemplate.objects.all().delete()
        printer = Printer.objects.create(
            name="No Template Printer",
            printer_type=PrinterType.VIRTUAL,
            ip_address="192.168.1.100",
        )

        response = admin_client.post(_test_print_url(printer.pk))

        assert response.status_code == 302
        assert response.url == reverse(
            "admin:printing_printer_change", args=[printer.pk]
        )
        assert PrintJob.objects.count() == 0

    @patch(PROCESS_JOB)
    def test_uses_printer_default_template(
        self, mock_process, admin_client, template, db
    ):
        other_template = LabelTemplate.objects.create(
            name="Other", width_mm=50, height_mm=25, is_default=True
        )
        printer = Printer.objects.create(
            name="With Default",
            printer_type=PrinterType.VIRTUAL,
            ip_address="192.168.1.101",
            default_template=template,
        )

        mock_process.side_effect = lambda job: None

        admin_client.post(_test_print_url(printer.pk))

        job = PrintJob.objects.get()
        assert job.template == template
        assert job.template != other_template

    @patch(PROCESS_JOB)
    def test_falls_back_to_default_template(self, mock_process, admin_client, db):
        LabelTemplate.objects.all().delete()
        default = LabelTemplate.objects.create(
            name="Default", width_mm=62, height_mm=62, is_default=True
        )
        LabelTemplate.objects.create(
            name="Other", width_mm=50, height_mm=25, is_default=False
        )
        printer = Printer.objects.create(
            name="Fallback Printer",
            printer_type=PrinterType.VIRTUAL,
            ip_address="192.168.1.100",
        )

        mock_process.side_effect = lambda job: None

        admin_client.post(_test_print_url(printer.pk))

        job = PrintJob.objects.get()
        assert job.template == default

    @patch(PROCESS_JOB)
    def test_failed_print_shows_error_message(
        self, mock_process, admin_client, printer, template
    ):
        def fail_job(job):
            job.status = JobStatus.FAILED
            job.error_message = "Connection refused"
            job.save(update_fields=["status", "error_message"])

        mock_process.side_effect = fail_job

        response = admin_client.post(_test_print_url(printer.pk))

        assert response.status_code == 302
        job = PrintJob.objects.get()
        assert job.status == JobStatus.FAILED
