import logging

from django.core.files.base import ContentFile
from django.utils import timezone

from printing.models import JobStatus, PrinterType, PrintJob
from printing.services.cups_printer import CupsPrinterService
from printing.services.label_renderer import LabelRenderer
from printing.services.printer import PrintError, PrinterService

logger = logging.getLogger(__name__)


def _save_virtual_pdf(job: PrintJob, pdf_bytes: bytes) -> str:
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{job.pk}_{job.barcode}_{timestamp}.pdf"
    job.output_file.save(filename, ContentFile(pdf_bytes), save=False)
    return job.output_file.name


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
            location_name=job.location_name,
            location_description=job.location_description,
            location_categories=job.location_categories,
            location_departments=job.location_departments,
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

        if job.printer.printer_type == PrinterType.VIRTUAL:
            saved_name = _save_virtual_pdf(job, pdf_bytes)
            logger.info("Virtual print job %s saved to %s", job.pk, saved_name)
        elif job.printer.printer_type == PrinterType.CUPS:
            service = CupsPrinterService(
                job.printer.cups_queue,
                server=job.printer.cups_server,
            )
            service.send(pdf_bytes)
        else:
            service = PrinterService(job.printer.ip_address, job.printer.port)
            service.send(pdf_bytes)
    except PrintError as e:
        logger.error("Failed to print job %s: %s", job.pk, e)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.save(update_fields=["status", "error_message"])
        return
    except OSError as e:
        logger.error("Failed to save virtual print job %s: %s", job.pk, e)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.save(update_fields=["status", "error_message"])
        return

    job.status = JobStatus.COMPLETED
    job.completed_at = timezone.now()
    update_fields = ["status", "completed_at"]
    if job.output_file:
        update_fields.append("output_file")
    job.save(update_fields=update_fields)
    logger.info("Print job %s completed successfully", job.pk)
