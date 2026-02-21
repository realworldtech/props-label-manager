import asyncio
import logging
from typing import Optional

import websockets

from printing.models import Printer
from printing.services.protocol import (
    MessageType,
    ProtocolError,
    build_authenticate_message,
    build_pairing_request_message,
    build_print_ack_message,
    build_print_status_message,
    parse_server_message,
)

logger = logging.getLogger(__name__)

MAX_BACKOFF = 60


class PropsWebSocketClient:
    def __init__(
        self,
        connection_id: int,
        server_url: str,
        client_name: str,
        pairing_token: Optional[str] = None,
        on_token_received=None,
        on_status_change=None,
        on_print_job=None,
    ):
        self.connection_id = connection_id
        self.server_url = server_url
        self.client_name = client_name
        self.pairing_token = pairing_token
        self.on_token_received = on_token_received
        self.on_status_change = on_status_change
        self.on_print_job = on_print_job
        self._retry_count = 0
        self._running = False

    def _get_backoff_delay(self, retry_count: int) -> int:
        return min(2**retry_count, MAX_BACKOFF)

    async def _build_printer_info(self) -> list[dict]:
        return await asyncio.to_thread(self._get_printer_info)

    @staticmethod
    def _get_printer_info() -> list[dict]:
        printers = Printer.objects.filter(is_active=True).select_related(
            "default_template"
        )
        result = []
        for p in printers:
            templates = []
            if p.default_template:
                templates.append(p.default_template.name)
            result.append(
                {
                    "id": str(p.pk),
                    "name": p.name,
                    "status": p.status,
                    "templates": templates,
                }
            )
        return result

    async def connect(self):
        self._running = True
        while self._running:
            try:
                if self.on_status_change:
                    await self.on_status_change(self.connection_id, "connecting")

                async with websockets.connect(self.server_url) as ws:
                    self._retry_count = 0
                    await self._on_connected(ws)
                    await self._listen(ws)

            except (websockets.exceptions.ConnectionClosed, OSError) as e:
                logger.warning("Connection %s lost: %s", self.connection_id, e)
            except Exception as e:
                logger.error("Connection %s error: %s", self.connection_id, e)

            if not self._running:
                break

            try:
                if self.on_status_change:
                    await self.on_status_change(self.connection_id, "disconnected")
            except Exception as e:
                logger.error(
                    "Connection %s status callback error: %s",
                    self.connection_id,
                    e,
                )

            delay = self._get_backoff_delay(self._retry_count)
            self._retry_count += 1
            logger.info(
                "Connection %s reconnecting in %ds...",
                self.connection_id,
                delay,
            )
            await asyncio.sleep(delay)

    async def _on_connected(self, ws):
        printer_info = await self._build_printer_info()

        if self.pairing_token:
            msg = build_authenticate_message(
                self.pairing_token, self.client_name, printer_info
            )
        else:
            msg = build_pairing_request_message(self.client_name)
            if self.on_status_change:
                await self.on_status_change(self.connection_id, "pairing")

        await ws.send(msg)

    async def _listen(self, ws):
        async for raw_message in ws:
            try:
                message = parse_server_message(raw_message)
                await self._handle_message(message, ws)
            except ProtocolError as e:
                logger.warning(
                    "Connection %s protocol error: %s",
                    self.connection_id,
                    e,
                )

    async def _handle_message(self, message, ws):
        if message.type == MessageType.AUTH_RESULT:
            if message.data.get("success"):
                logger.info(
                    "Connection %s authenticated with %s",
                    self.connection_id,
                    message.data.get("server_name"),
                )
                new_token = message.data.get("new_token")
                if new_token:
                    self.pairing_token = new_token
                    if self.on_token_received:
                        await self.on_token_received(self.connection_id, new_token)
                if self.on_status_change:
                    await self.on_status_change(self.connection_id, "connected")
            else:
                logger.error(
                    "Connection %s authentication failed: %s",
                    self.connection_id,
                    message.data.get("message", "unknown error"),
                )
                if self.on_status_change:
                    await self.on_status_change(self.connection_id, "error")

        elif message.type == MessageType.PAIRING_APPROVED:
            token = message.data["token"]
            self.pairing_token = token
            if self.on_token_received:
                await self.on_token_received(self.connection_id, token)
            logger.info("Connection %s paired successfully", self.connection_id)
            printer_info = await self._build_printer_info()
            await ws.send(
                build_authenticate_message(token, self.client_name, printer_info)
            )

        elif message.type == MessageType.PAIRING_DENIED:
            logger.error("Connection %s pairing denied", self.connection_id)
            if self.on_status_change:
                await self.on_status_change(self.connection_id, "error")

        elif message.type == MessageType.PAIRING_PENDING:
            logger.info(
                "Connection %s pairing pending: %s",
                self.connection_id,
                message.data.get("message", ""),
            )

        elif message.type == MessageType.PRINT:
            job_id = message.data["job_id"]
            await ws.send(build_print_ack_message(job_id))
            try:
                if self.on_print_job:
                    await self.on_print_job(self.connection_id, message.data)
                await ws.send(build_print_status_message(job_id, "completed"))
            except Exception as e:
                logger.error("Print job %s failed: %s", job_id, e)
                await ws.send(build_print_status_message(job_id, "failed", str(e)))

        elif message.type == MessageType.ERROR:
            logger.error(
                "Connection %s error: code=%s message=%s",
                self.connection_id,
                message.data.get("code"),
                message.data.get("message"),
            )
            if self.on_status_change:
                await self.on_status_change(self.connection_id, "error")

        elif message.type == MessageType.FORCE_DISCONNECT:
            logger.warning(
                "Connection %s force disconnected: %s",
                self.connection_id,
                message.data.get("reason", ""),
            )
            self.stop()

    def stop(self):
        self._running = False
