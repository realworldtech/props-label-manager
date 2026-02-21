import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

PROTOCOL_VERSION = "1"


class MessageType(Enum):
    AUTH_RESULT = "auth_result"
    PAIRING_APPROVED = "pairing_approved"
    PAIRING_DENIED = "pairing_denied"
    PRINT = "print"


class ProtocolError(Exception):
    pass


@dataclass
class ServerMessage:
    type: MessageType
    data: dict[str, Any]


PRINT_REQUIRED_FIELDS = [
    "job_id",
    "printer_id",
    "barcode",
    "asset_name",
    "category_name",
]


def build_authenticate_message(
    token: str, client_name: str, printers: list[dict]
) -> str:
    return json.dumps(
        {
            "type": "authenticate",
            "protocol_version": PROTOCOL_VERSION,
            "token": token,
            "client_name": client_name,
            "printers": printers,
        }
    )


def build_pairing_request_message(client_name: str) -> str:
    return json.dumps(
        {
            "type": "pairing_request",
            "protocol_version": PROTOCOL_VERSION,
            "client_name": client_name,
        }
    )


def build_print_ack_message(job_id: str) -> str:
    return json.dumps(
        {
            "type": "print_ack",
            "job_id": job_id,
        }
    )


def build_print_status_message(
    job_id: str, status: str, error: Optional[str] = None
) -> str:
    return json.dumps(
        {
            "type": "print_status",
            "job_id": job_id,
            "status": status,
            "error": error,
        }
    )


def parse_server_message(raw: str) -> ServerMessage:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"Invalid JSON: {e}")

    if "type" not in data:
        raise ProtocolError("Missing 'type' field in message")

    msg_type_str = data["type"]
    try:
        msg_type = MessageType(msg_type_str)
    except ValueError:
        raise ProtocolError(f"Unknown message type: {msg_type_str}")

    if msg_type == MessageType.PRINT:
        for field in PRINT_REQUIRED_FIELDS:
            if field not in data:
                raise ProtocolError(
                    f"Missing required field '{field}' in print message"
                )

    return ServerMessage(type=msg_type, data=data)
