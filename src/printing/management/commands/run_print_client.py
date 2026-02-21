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

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting print client '{client_name}' "
                f"(syncing connections every 10s)..."
            )
        )

        asyncio.run(self._run(client_name))

    async def _run(self, client_name: str):
        self._clients = {}  # connection_id -> PropsWebSocketClient
        self._tasks = {}  # connection_id -> asyncio.Task
        self._client_name = client_name
        self._printer_fingerprint = None

        while True:
            await self._sync_connections()
            await asyncio.sleep(10)

    async def _sync_connections(self):
        # Discover CUPS printers from Docker labels
        results = await asyncio.to_thread(self._discover_printers)
        for r in results:
            if r["created"]:
                logger.info(
                    "Discovered new printer: %s (queue: %s, server: %s)",
                    r["name"],
                    r["cups_queue"],
                    r["cups_server"],
                )

        # Remove dead tasks (crashed or unexpectedly finished)
        dead_ids = [conn_id for conn_id, task in self._tasks.items() if task.done()]
        for conn_id in dead_ids:
            task = self._tasks[conn_id]
            if task.exception():
                logger.error(
                    "Client for connection %s crashed: %s",
                    conn_id,
                    task.exception(),
                )
            else:
                logger.warning("Client for connection %s stopped unexpectedly", conn_id)
            del self._clients[conn_id]
            del self._tasks[conn_id]

        desired, printer_fp = await asyncio.to_thread(self._get_desired_state)
        desired_ids = set(desired.keys())
        running_ids = set(self._clients.keys())

        # Restart all clients if the printer list changed
        if (
            self._printer_fingerprint is not None
            and printer_fp != self._printer_fingerprint
        ):
            logger.info("Printer configuration changed, restarting all connections")
            for conn_id in list(running_ids):
                self._clients[conn_id].stop()
                del self._clients[conn_id]
                del self._tasks[conn_id]
            running_ids = set()
        self._printer_fingerprint = printer_fp

        # Start new connections (or restart dead ones)
        for conn_id in desired_ids - running_ids:
            conn = desired[conn_id]
            client = PropsWebSocketClient(
                connection_id=conn_id,
                server_url=conn["server_url"],
                client_name=self._client_name,
                pairing_token=conn["pairing_token"],
                on_token_received=self._on_token_received,
                on_status_change=self._on_status_change,
                on_print_job=self._on_print_job,
            )
            self._clients[conn_id] = client
            self._tasks[conn_id] = asyncio.create_task(client.connect())
            logger.info("Started client for connection %s", conn_id)

        # Stop removed/deactivated connections
        for conn_id in running_ids - desired_ids:
            self._clients[conn_id].stop()
            del self._clients[conn_id]
            del self._tasks[conn_id]
            logger.info("Stopped client for connection %s", conn_id)

    def _get_desired_state(self):
        """Synchronous DB read — called via to_thread.

        Returns (connections_dict, printer_fingerprint).
        """
        connections = PropsConnection.objects.filter(is_active=True)
        conn_dict = {
            conn.pk: {
                "server_url": conn.server_url,
                "pairing_token": conn.pairing_token,
            }
            for conn in connections
        }
        printers = Printer.objects.filter(is_active=True).values_list(
            "pk", "name", "printer_type", "status"
        )
        printer_fp = frozenset(printers)
        return conn_dict, printer_fp

    def _discover_printers(self):
        from printing.services.docker_discovery import discover_printers

        return discover_printers()

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

            label_type = data.get("label_type", "asset")

            job = PrintJob.objects.create(
                props_connection_id=connection_id,
                printer=printer,
                template=template,
                label_type=label_type,
                barcode=data.get("barcode", ""),
                asset_name=data.get("asset_name", ""),
                category_name=data.get("category_name", ""),
                qr_content=data.get("qr_content", ""),
                quantity=data.get("quantity", 1),
                department_name=data.get("department_name", ""),
                site_short_name=data.get("site_short_name", ""),
                location_name=data.get("location_name", ""),
                location_description=data.get("location_description", ""),
                location_categories=data.get("location_categories", ""),
                location_departments=data.get("location_departments", ""),
            )
            process_print_job(job)

        await asyncio.to_thread(_process)
