import json

import pytest

from printing.services.protocol import (
    PROTOCOL_VERSION,
    MessageType,
    ProtocolError,
    build_authenticate_message,
    build_pairing_request_message,
    build_print_ack_message,
    build_print_status_message,
    parse_server_message,
)


class TestBuildMessages:
    def test_build_authenticate(self):
        printers = [
            {
                "id": 1,
                "name": "Zebra",
                "status": "online",
                "templates": ["square-62x62"],
            }
        ]
        msg = build_authenticate_message("secret-token", "Office Printer", printers)
        parsed = json.loads(msg)
        assert parsed["type"] == "authenticate"
        assert parsed["token"] == "secret-token"
        assert parsed["client_name"] == "Office Printer"
        assert len(parsed["printers"]) == 1

    def test_build_pairing_request(self):
        msg = build_pairing_request_message("New Printer")
        parsed = json.loads(msg)
        assert parsed["type"] == "pairing_request"
        assert parsed["client_name"] == "New Printer"

    def test_protocol_version_constant(self):
        assert PROTOCOL_VERSION == "2"

    def test_build_authenticate_includes_protocol_version(self):
        printers = [{"id": 1, "name": "Zebra", "status": "online", "templates": []}]
        msg = build_authenticate_message("token", "Client", printers)
        parsed = json.loads(msg)
        assert parsed["protocol_version"] == "2"

    def test_build_pairing_request_includes_protocol_version(self):
        msg = build_pairing_request_message("Client")
        parsed = json.loads(msg)
        assert parsed["protocol_version"] == "2"

    def test_build_print_status_completed(self):
        msg = build_print_status_message("job-uuid-123", "completed")
        parsed = json.loads(msg)
        assert parsed["type"] == "print_status"
        assert parsed["job_id"] == "job-uuid-123"
        assert parsed["status"] == "completed"
        assert parsed["error"] is None

    def test_build_print_ack(self):
        msg = build_print_ack_message("job-uuid-789")
        parsed = json.loads(msg)
        assert parsed["type"] == "print_ack"
        assert parsed["job_id"] == "job-uuid-789"

    def test_build_print_status_failed(self):
        msg = build_print_status_message("job-uuid-123", "failed", "printer offline")
        parsed = json.loads(msg)
        assert parsed["status"] == "failed"
        assert parsed["error"] == "printer offline"


class TestParseMessages:
    def test_parse_auth_result_success(self):
        raw = json.dumps(
            {"type": "auth_result", "success": True, "server_name": "BeaMS"}
        )
        msg = parse_server_message(raw)
        assert msg.type == MessageType.AUTH_RESULT
        assert msg.data["success"] is True
        assert msg.data["server_name"] == "BeaMS"

    def test_parse_auth_result_failure(self):
        raw = json.dumps(
            {"type": "auth_result", "success": False, "server_name": "BeaMS"}
        )
        msg = parse_server_message(raw)
        assert msg.data["success"] is False

    def test_parse_pairing_approved(self):
        raw = json.dumps(
            {
                "type": "pairing_approved",
                "token": "new-token-xyz",
                "server_name": "BeaMS Production",
            }
        )
        msg = parse_server_message(raw)
        assert msg.type == MessageType.PAIRING_APPROVED
        assert msg.data["token"] == "new-token-xyz"

    def test_parse_print_request(self):
        raw = json.dumps(
            {
                "type": "print",
                "job_id": "uuid-123",
                "printer_id": "1",
                "barcode": "BEAMS-A1B2C3D4",
                "asset_name": "Wireless Mic",
                "category_name": "Audio",
                "quantity": 2,
            }
        )
        msg = parse_server_message(raw)
        assert msg.type == MessageType.PRINT
        assert msg.data["barcode"] == "BEAMS-A1B2C3D4"
        assert msg.data["quantity"] == 2

    def test_parse_print_request_with_qr_content(self):
        raw = json.dumps(
            {
                "type": "print",
                "job_id": "uuid-456",
                "printer_id": "1",
                "barcode": "BEAMS-A1B2C3D4",
                "asset_name": "Wireless Mic",
                "category_name": "Audio",
                "qr_content": "https://beams.example.com/assets/A1B2C3D4",
                "quantity": 1,
            }
        )
        msg = parse_server_message(raw)
        assert msg.type == MessageType.PRINT
        assert msg.data["qr_content"] == "https://beams.example.com/assets/A1B2C3D4"

    def test_parse_invalid_json(self):
        with pytest.raises(ProtocolError, match="Invalid JSON"):
            parse_server_message("not json{{{")

    def test_parse_missing_type(self):
        with pytest.raises(ProtocolError, match="Missing 'type'"):
            parse_server_message(json.dumps({"data": "no type field"}))

    def test_parse_unknown_type(self):
        with pytest.raises(ProtocolError, match="Unknown message type"):
            parse_server_message(json.dumps({"type": "unknown_thing"}))

    def test_parse_pairing_pending(self):
        raw = json.dumps(
            {
                "type": "pairing_pending",
                "client_id": 42,
                "message": "Awaiting admin approval.",
            }
        )
        msg = parse_server_message(raw)
        assert msg.type == MessageType.PAIRING_PENDING
        assert msg.data["client_id"] == 42

    def test_parse_error_message(self):
        raw = json.dumps(
            {
                "type": "error",
                "code": "version_mismatch",
                "message": "Unsupported protocol version",
            }
        )
        msg = parse_server_message(raw)
        assert msg.type == MessageType.ERROR
        assert msg.data["code"] == "version_mismatch"

    def test_parse_force_disconnect(self):
        raw = json.dumps({"type": "force_disconnect"})
        msg = parse_server_message(raw)
        assert msg.type == MessageType.FORCE_DISCONNECT

    def test_parse_print_missing_required_fields(self):
        raw = json.dumps({"type": "print", "job_id": "123"})
        with pytest.raises(ProtocolError, match="Missing required field"):
            parse_server_message(raw)
