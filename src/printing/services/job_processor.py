import logging

from django.utils import timezone

from printing.models import JobStatus, PrintJob
from printing.services.label_renderer import LabelRenderer
from printing.services.printer import PrintError, PrinterService

logger = logging.getLogger(__name__)


def process_print_job(job: PrintJob) -> None:
    try:
        job.status = JobStatus.RENDERING
        job.save(update_fields=["status"])

        renderer = LabelRenderer(job.template)
        pdf_bytes = renderer.render(
            barcode_text=job.barcode,
            asset_name=job.asset_name,
            category_name=job.category_name,
            qr_content=job.qr_content or "",
            quantity=job.quantity,
            department_name=job.department_name,
            site_short_name=job.site_short_name,
        )
    except Exception as e:
        logger.error("Failed to render job %s: %s", job.pk, e)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.save(update_fields=["status", "error_message"])
        return

    try:
        job.status = JobStatus.SENDING
        job.save(update_fields=["status"])

        service = PrinterService(job.printer.ip_address, job.printer.port)
        service.send(pdf_bytes)
    except PrintError as e:
        logger.error("Failed to print job %s: %s", job.pk, e)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.save(update_fields=["status", "error_message"])
        return

    job.status = JobStatus.COMPLETED
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "completed_at"])
    logger.info("Print job %s completed successfully", job.pk)
