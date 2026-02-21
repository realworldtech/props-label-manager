# PROPS Protocol v1 Alignment

**Date:** 2026-02-21
**Status:** Approved

## Problem

The PROPS server has merged its WebSocket print service implementation (PR #14). The label manager client has several protocol gaps that will prevent it from connecting and operating correctly:

1. Missing `protocol_version` field in outgoing messages (server rejects with `version_mismatch`)
2. Token rotation not handled (server rotates token on every auth; client would use stale token on reconnect)
3. Missing `print_ack` message (server expects `sent -> acked -> completed/failed` lifecycle)
4. Unrecognised server message types cause `ProtocolError` (`pairing_pending`, `error`, `force_disconnect`)
5. New print job fields (`department_name`, `site_short_name`) not captured

## Changes

### 1. Protocol Version

- Define `PROTOCOL_VERSION = "1"` constant in `protocol.py`
- Add `"protocol_version": "1"` to `build_pairing_request_message()` and `build_authenticate_message()`

### 2. Token Rotation

- In `ws_client.py` `_handle_message()` for `AUTH_RESULT` success: extract `new_token`, update `self.pairing_token`, call `on_token_received` callback to persist to DB
- No model changes needed (`PropsConnection.pairing_token` already exists)

### 3. Print Acknowledgement

- Add `build_print_ack_message(job_id)` to `protocol.py`
- In `ws_client.py` print handler: send `print_ack` immediately on receipt, then `print_status` after processing

### 4. New Server Message Types

Add to `MessageType` enum and handle in `_handle_message()`:

- `pairing_pending` — log, no action (client already in pairing state)
- `error` — log code/message, set status to `error`
- `force_disconnect` — log, call `self.stop()` (reconnect via backoff)

### 5. New Print Job Fields

- Add `department_name` (CharField, max 200, blank) and `site_short_name` (CharField, max 50, blank) to `PrintJob` model
- Add `DEPARTMENT_NAME` and `SITE_SHORT_NAME` to `ElementType` choices
- Store values from print message data in `run_print_client.py`

### 6. Tests

Update test files to cover all changes: protocol version in messages, token rotation flow, print_ack, new message types, new model fields.

## Files Affected

- `src/printing/services/protocol.py`
- `src/printing/services/ws_client.py`
- `src/printing/models.py`
- `src/printing/management/commands/run_print_client.py`
- `src/printing/tests/test_protocol.py`
- `src/printing/tests/test_ws_client.py`
- `src/printing/tests/test_models.py`
- `src/printing/tests/test_integration.py`
- New migration file
