import asyncio
import logging

from django.core.management.base import BaseCommand

from printing.models import LabelTemplate, Printer, PrintJob, PropsConnection
from printing.services.job_processor import process_print_job
from printing.services.ws_client import PropsWebSocketClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the PROPS print client WebSocket connections"

    def add_arguments(self, parser):
        parser.add_argument(
            "--client-name",
            default="PROPS Print Client",
            help="Name to identify this client to PROPS servers",
        )

    def handle(self, *args, **options):
        client_name = options["client_name"]
        connections = PropsConnection.objects.filter(is_active=True)

        if not connections.exists():
            self.stdout.write(self.style.WARNING("No active connections configured."))
            self.stdout.write("Add connections via the admin interface at /admin/")
            return

        for conn in connections:
            status = "paired" if conn.is_paired else "unpaired"
            self.stdout.write(f"  - {conn.name} ({status})")

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting print client '{client_name}' with "
                f"{connections.count()} connection(s)..."
            )
        )

        asyncio.run(self._run(client_name))

    async def _run(self, client_name: str):
        connections = PropsConnection.objects.filter(is_active=True)
        tasks = []

        for conn in connections:
            client = PropsWebSocketClient(
                connection_id=conn.pk,
                server_url=conn.server_url,
                client_name=client_name,
                pairing_token=conn.pairing_token,
                on_token_received=self._on_token_received,
                on_status_change=self._on_status_change,
                on_print_job=self._on_print_job,
            )
            tasks.append(asyncio.create_task(client.connect()))

        if tasks:
            await asyncio.gather(*tasks)

    async def _on_token_received(self, connection_id: int, token: str):
        conn = await asyncio.to_thread(PropsConnection.objects.get, pk=connection_id)
        conn.pairing_token = token
        await asyncio.to_thread(conn.save, update_fields=["pairing_token"])
        logger.info("Stored pairing token for connection %s", connection_id)

    async def _on_status_change(self, connection_id: int, status: str):
        from django.utils import timezone

        def _update():
            conn = PropsConnection.objects.get(pk=connection_id)
            conn.status = status
            fields = ["status"]
            if status == "connected":
                conn.last_connected_at = timezone.now()
                fields.append("last_connected_at")
            conn.save(update_fields=fields)

        await asyncio.to_thread(_update)

    async def _on_print_job(self, connection_id: int, data: dict):
        def _process():
            printer = Printer.objects.get(pk=int(data["printer_id"]))
            template = printer.default_template
            if not template:
                template = LabelTemplate.objects.filter(is_default=True).first()
            if not template:
                raise Exception("No template available for printer")

            job = PrintJob.objects.create(
                props_connection_id=connection_id,
                printer=printer,
                template=template,
                barcode=data["barcode"],
                asset_name=data["asset_name"],
                category_name=data["category_name"],
                quantity=data.get("quantity", 1),
            )
            process_print_job(job)

        await asyncio.to_thread(_process)
