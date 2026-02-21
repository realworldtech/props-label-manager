# PROPS Protocol v1 Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align the label manager WebSocket client with the merged PROPS server protocol v1, fixing protocol version, token rotation, print acknowledgement, new message types, and new print job fields.

**Architecture:** The changes span the protocol layer (message builders/parsers), the WebSocket client (message handling), the data model (new fields + migration), the label renderer (new element types), and the management command (data mapping). All changes are additive — no breaking changes to existing functionality.

**Tech Stack:** Django 5.x, pytest, websockets, ReportLab

---

### Task 1: Add `protocol_version` to outgoing messages

**Files:**
- Modify: `src/printing/services/protocol.py:1-52`
- Test: `src/printing/tests/test_protocol.py`

**Step 1: Write failing tests**

Add to `TestBuildMessages` in `src/printing/tests/test_protocol.py`:

```python
def test_build_authenticate_includes_protocol_version(self):
    msg = build_authenticate_message("token", "Client", [])
    parsed = json.loads(msg)
    assert parsed["protocol_version"] == "1"

def test_build_pairing_request_includes_protocol_version(self):
    msg = build_pairing_request_message("Client")
    parsed = json.loads(msg)
    assert parsed["protocol_version"] == "1"
```

Also import and test the constant:

```python
from printing.services.protocol import PROTOCOL_VERSION

def test_protocol_version_constant(self):
    assert PROTOCOL_VERSION == "1"
```

**Step 2: Run tests to verify they fail**

Run: `cd src && pytest printing/tests/test_protocol.py::TestBuildMessages::test_build_authenticate_includes_protocol_version printing/tests/test_protocol.py::TestBuildMessages::test_build_pairing_request_includes_protocol_version -v`
Expected: FAIL — `protocol_version` key not present, `PROTOCOL_VERSION` not importable

**Step 3: Implement**

In `src/printing/services/protocol.py`, add constant at top (after imports):

```python
PROTOCOL_VERSION = "1"
```

Update `build_authenticate_message`:

```python
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
```

Update `build_pairing_request_message`:

```python
def build_pairing_request_message(client_name: str) -> str:
    return json.dumps(
        {
            "type": "pairing_request",
            "protocol_version": PROTOCOL_VERSION,
            "client_name": client_name,
        }
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd src && pytest printing/tests/test_protocol.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
cd src && git add printing/services/protocol.py printing/tests/test_protocol.py
git commit -m "feat: add protocol_version to outgoing messages"
```

---

### Task 2: Add `print_ack` message builder

**Files:**
- Modify: `src/printing/services/protocol.py`
- Test: `src/printing/tests/test_protocol.py`

**Step 1: Write failing test**

Add to `TestBuildMessages` in `src/printing/tests/test_protocol.py`:

```python
from printing.services.protocol import build_print_ack_message

def test_build_print_ack(self):
    msg = build_print_ack_message("job-uuid-789")
    parsed = json.loads(msg)
    assert parsed["type"] == "print_ack"
    assert parsed["job_id"] == "job-uuid-789"
```

**Step 2: Run test to verify it fails**

Run: `cd src && pytest printing/tests/test_protocol.py::TestBuildMessages::test_build_print_ack -v`
Expected: FAIL — `build_print_ack_message` cannot be imported

**Step 3: Implement**

Add to `src/printing/services/protocol.py`:

```python
def build_print_ack_message(job_id: str) -> str:
    return json.dumps(
        {
            "type": "print_ack",
            "job_id": job_id,
        }
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd src && pytest printing/tests/test_protocol.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
cd src && git add printing/services/protocol.py printing/tests/test_protocol.py
git commit -m "feat: add print_ack message builder"
```

---

### Task 3: Add new server message types to parser

**Files:**
- Modify: `src/printing/services/protocol.py`
- Test: `src/printing/tests/test_protocol.py`

**Step 1: Write failing tests**

Add to `TestParseMessages` in `src/printing/tests/test_protocol.py`:

```python
def test_parse_pairing_pending(self):
    raw = json.dumps({
        "type": "pairing_pending",
        "client_id": 42,
        "message": "Awaiting admin approval.",
    })
    msg = parse_server_message(raw)
    assert msg.type == MessageType.PAIRING_PENDING
    assert msg.data["client_id"] == 42

def test_parse_error_message(self):
    raw = json.dumps({
        "type": "error",
        "code": "version_mismatch",
        "message": "Unsupported protocol version",
    })
    msg = parse_server_message(raw)
    assert msg.type == MessageType.ERROR
    assert msg.data["code"] == "version_mismatch"

def test_parse_force_disconnect(self):
    raw = json.dumps({"type": "force_disconnect"})
    msg = parse_server_message(raw)
    assert msg.type == MessageType.FORCE_DISCONNECT
```

**Step 2: Run tests to verify they fail**

Run: `cd src && pytest printing/tests/test_protocol.py::TestParseMessages::test_parse_pairing_pending printing/tests/test_protocol.py::TestParseMessages::test_parse_error_message printing/tests/test_protocol.py::TestParseMessages::test_parse_force_disconnect -v`
Expected: FAIL — `MessageType` has no `PAIRING_PENDING`, `ERROR`, or `FORCE_DISCONNECT`

**Step 3: Implement**

Update `MessageType` in `src/printing/services/protocol.py`:

```python
class MessageType(Enum):
    AUTH_RESULT = "auth_result"
    PAIRING_APPROVED = "pairing_approved"
    PAIRING_DENIED = "pairing_denied"
    PAIRING_PENDING = "pairing_pending"
    PRINT = "print"
    ERROR = "error"
    FORCE_DISCONNECT = "force_disconnect"
```

**Step 4: Run tests to verify they pass**

Run: `cd src && pytest printing/tests/test_protocol.py -v`
Expected: ALL PASS

**Step 5: Also update the `test_parse_unknown_type` test**

The existing test uses `"unknown_thing"` which should still fail. Verify it still passes.

**Step 6: Commit**

```bash
cd src && git add printing/services/protocol.py printing/tests/test_protocol.py
git commit -m "feat: add pairing_pending, error, force_disconnect message types"
```

---

### Task 4: Handle token rotation and new message types in WebSocket client

**Files:**
- Modify: `src/printing/services/ws_client.py`
- Test: `src/printing/tests/test_ws_client.py`

**Step 1: Write failing tests**

Add to `src/printing/tests/test_ws_client.py`:

```python
from printing.services.protocol import (
    MessageType,
    ServerMessage,
    build_print_ack_message,
)


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_auth_result_success_rotates_token(self):
        """On auth success with new_token, client updates token and calls callback."""
        token_callback = MagicMock()

        async def async_token_callback(conn_id, token):
            token_callback(conn_id, token)

        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
            pairing_token="old-token",
            on_token_received=async_token_callback,
            on_status_change=MagicMock(side_effect=lambda *a: asyncio.coroutine(lambda: None)()),
        )
        mock_ws = MagicMock()
        message = ServerMessage(
            type=MessageType.AUTH_RESULT,
            data={"success": True, "server_name": "PROPS", "new_token": "rotated-token"},
        )

        # Need async mock for on_status_change
        async def async_status_change(conn_id, status):
            pass

        client.on_status_change = async_status_change
        await client._handle_message(message, mock_ws)

        assert client.pairing_token == "rotated-token"
        token_callback.assert_called_once_with(1, "rotated-token")

    @pytest.mark.asyncio
    async def test_auth_result_success_without_new_token(self):
        """Auth success without new_token still works (no crash)."""
        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
            pairing_token="my-token",
        )
        mock_ws = MagicMock()

        async def async_status_change(conn_id, status):
            pass

        client.on_status_change = async_status_change
        message = ServerMessage(
            type=MessageType.AUTH_RESULT,
            data={"success": True, "server_name": "PROPS"},
        )
        await client._handle_message(message, mock_ws)
        assert client.pairing_token == "my-token"  # unchanged

    @pytest.mark.asyncio
    async def test_print_sends_ack_before_processing(self):
        """Print message handler sends print_ack immediately."""
        sent_messages = []
        mock_ws = MagicMock()
        mock_ws.send = MagicMock(side_effect=lambda m: sent_messages.append(m) or asyncio.coroutine(lambda: None)())

        async def mock_ws_send(m):
            sent_messages.append(m)

        mock_ws.send = mock_ws_send

        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
        )
        message = ServerMessage(
            type=MessageType.PRINT,
            data={
                "job_id": "test-job-1",
                "printer_id": "1",
                "barcode": "ABC123",
                "asset_name": "Mic",
                "category_name": "Audio",
            },
        )
        await client._handle_message(message, mock_ws)

        import json
        # First message should be print_ack
        first_msg = json.loads(sent_messages[0])
        assert first_msg["type"] == "print_ack"
        assert first_msg["job_id"] == "test-job-1"
        # Second should be print_status
        second_msg = json.loads(sent_messages[1])
        assert second_msg["type"] == "print_status"

    @pytest.mark.asyncio
    async def test_pairing_pending_is_handled(self):
        """pairing_pending message does not crash."""
        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
        )
        mock_ws = MagicMock()
        message = ServerMessage(
            type=MessageType.PAIRING_PENDING,
            data={"client_id": 42, "message": "Awaiting approval"},
        )
        # Should not raise
        await client._handle_message(message, mock_ws)

    @pytest.mark.asyncio
    async def test_error_message_sets_error_status(self):
        """error message triggers status change to error."""
        statuses = []

        async def track_status(conn_id, status):
            statuses.append(status)

        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
            on_status_change=track_status,
        )
        mock_ws = MagicMock()
        message = ServerMessage(
            type=MessageType.ERROR,
            data={"code": "version_mismatch", "message": "Unsupported"},
        )
        await client._handle_message(message, mock_ws)
        assert "error" in statuses

    @pytest.mark.asyncio
    async def test_force_disconnect_stops_client(self):
        """force_disconnect stops the client."""
        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
        )
        client._running = True
        mock_ws = MagicMock()
        message = ServerMessage(
            type=MessageType.FORCE_DISCONNECT,
            data={},
        )
        await client._handle_message(message, mock_ws)
        assert client._running is False
```

**Step 2: Run tests to verify they fail**

Run: `cd src && pytest printing/tests/test_ws_client.py::TestHandleMessage -v`
Expected: FAIL — various assertion errors and missing handling

**Step 3: Implement**

Update `src/printing/services/ws_client.py`:

Add import of `build_print_ack_message`:

```python
from printing.services.protocol import (
    MessageType,
    ProtocolError,
    build_authenticate_message,
    build_pairing_request_message,
    build_print_ack_message,
    build_print_status_message,
    parse_server_message,
)
```

Update `_handle_message` method:

```python
async def _handle_message(self, message, ws):
    if message.type == MessageType.AUTH_RESULT:
        if message.data.get("success"):
            new_token = message.data.get("new_token")
            if new_token:
                self.pairing_token = new_token
                if self.on_token_received:
                    await self.on_token_received(self.connection_id, new_token)
            logger.info(
                "Connection %s authenticated with %s",
                self.connection_id,
                message.data.get("server_name"),
            )
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

    elif message.type == MessageType.PAIRING_PENDING:
        logger.info(
            "Connection %s pairing pending: %s",
            self.connection_id,
            message.data.get("message", ""),
        )

    elif message.type == MessageType.PAIRING_DENIED:
        logger.error("Connection %s pairing denied", self.connection_id)
        if self.on_status_change:
            await self.on_status_change(self.connection_id, "error")

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
            "Connection %s server error [%s]: %s",
            self.connection_id,
            message.data.get("code", "unknown"),
            message.data.get("message", ""),
        )
        if self.on_status_change:
            await self.on_status_change(self.connection_id, "error")

    elif message.type == MessageType.FORCE_DISCONNECT:
        logger.warning(
            "Connection %s force disconnected by server",
            self.connection_id,
        )
        self.stop()
```

**Step 4: Run tests to verify they pass**

Run: `cd src && pytest printing/tests/test_ws_client.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
cd src && git add printing/services/ws_client.py printing/tests/test_ws_client.py
git commit -m "feat: handle token rotation, print_ack, and new message types"
```

---

### Task 5: Add `department_name` and `site_short_name` to PrintJob model

**Files:**
- Modify: `src/printing/models.py`
- Test: `src/printing/tests/test_models.py`
- New: migration file (auto-generated)

**Step 1: Write failing test**

Add to `TestPrintJob` in `src/printing/tests/test_models.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd src && pytest printing/tests/test_models.py::TestPrintJob::test_print_job_with_department_and_site -v`
Expected: FAIL — `department_name` is not a valid field

**Step 3: Implement model changes**

Add to `PrintJob` model in `src/printing/models.py`, after `category_name`:

```python
department_name = models.CharField(max_length=200, blank=True, default="")
site_short_name = models.CharField(max_length=50, blank=True, default="")
```

**Step 4: Generate and apply migration**

Run: `cd src && python manage.py makemigrations printing && python manage.py migrate`

**Step 5: Run tests to verify they pass**

Run: `cd src && pytest printing/tests/test_models.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
cd src && git add printing/models.py printing/migrations/ printing/tests/test_models.py
git commit -m "feat: add department_name and site_short_name to PrintJob"
```

---

### Task 6: Add `DEPARTMENT_NAME` and `SITE_SHORT_NAME` element types

**Files:**
- Modify: `src/printing/models.py` (ElementType enum)
- Modify: `src/printing/services/label_renderer.py` (_render_element)
- Test: `src/printing/tests/test_models.py`

**Step 1: Write failing test**

Add to `TestLabelElement` in `src/printing/tests/test_models.py`:

```python
def test_department_name_element_type(self):
    assert ElementType.DEPARTMENT_NAME == "department_name"

def test_site_short_name_element_type(self):
    assert ElementType.SITE_SHORT_NAME == "site_short_name"
```

**Step 2: Run tests to verify they fail**

Run: `cd src && pytest printing/tests/test_models.py::TestLabelElement::test_department_name_element_type -v`
Expected: FAIL — `ElementType` has no `DEPARTMENT_NAME`

**Step 3: Implement**

Add to `ElementType` in `src/printing/models.py`:

```python
class ElementType(models.TextChoices):
    BARCODE_128 = "barcode_128", "Barcode (Code 128)"
    QR_CODE = "qr_code", "QR Code"
    ASSET_NAME = "asset_name", "Asset Name"
    CATEGORY_NAME = "category_name", "Category Name"
    DEPARTMENT_NAME = "department_name", "Department Name"
    SITE_SHORT_NAME = "site_short_name", "Site Short Name"
    BARCODE_TEXT = "barcode_text", "Barcode Text"
    LOGO = "logo", "Logo"
    STATIC_TEXT = "static_text", "Static Text"
```

Update `_render_element` in `src/printing/services/label_renderer.py` to add cases. The `render()` method signature also needs `department_name` and `site_short_name` parameters:

Update `render()` method:

```python
def render(
    self,
    barcode_text: str,
    asset_name: str,
    category_name: str,
    qr_content: str = "",
    quantity: int = 1,
    department_name: str = "",
    site_short_name: str = "",
) -> bytes:
    width = float(self.template.width_mm) * mm
    height = float(self.template.height_mm) * mm
    qr_data = qr_content or barcode_text

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))

    elements = self.template.elements.all()

    for i in range(quantity):
        if i > 0:
            c.showPage()
        for element in elements:
            self._render_element(
                c, height, element, barcode_text, asset_name,
                category_name, qr_data, department_name, site_short_name,
            )

    c.save()
    return buf.getvalue()
```

Update `_render_element()` signature and add cases:

```python
def _render_element(
    self, c, page_height, element, barcode_text, asset_name,
    category_name, qr_data, department_name, site_short_name,
):
    # ... existing coordinate code unchanged ...

    # ... existing cases unchanged ...
    elif element.element_type == ElementType.DEPARTMENT_NAME:
        self._render_text(c, element, department_name, x, rl_y, w, h)
    elif element.element_type == ElementType.SITE_SHORT_NAME:
        self._render_text(c, element, site_short_name, x, rl_y, w, h)
```

**Step 4: Generate migration for element_type choices change**

Run: `cd src && python manage.py makemigrations printing && python manage.py migrate`

**Step 5: Run all tests**

Run: `cd src && pytest -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
cd src && git add printing/models.py printing/services/label_renderer.py printing/migrations/ printing/tests/test_models.py
git commit -m "feat: add department_name and site_short_name element types"
```

---

### Task 7: Wire new fields through job processor and management command

**Files:**
- Modify: `src/printing/services/job_processor.py`
- Modify: `src/printing/management/commands/run_print_client.py`
- Test: `src/printing/tests/test_job_processor.py`
- Test: `src/printing/tests/test_integration.py`

**Step 1: Write failing test for job_processor**

Add test in `src/printing/tests/test_job_processor.py` (read existing file to check patterns, but this is the new test):

```python
def test_process_print_job_passes_department_and_site(self):
    """job_processor passes department_name and site_short_name to renderer."""
    template = LabelTemplate.objects.create(
        name="Test", width_mm=62, height_mm=62
    )
    printer = Printer.objects.create(name="Zebra", ip_address="192.168.1.100")
    job = PrintJob.objects.create(
        printer=printer,
        template=template,
        barcode="TEST-123",
        asset_name="Test Asset",
        category_name="Category",
        department_name="Technical",
        site_short_name="HDM",
    )
    with patch("printing.services.job_processor.LabelRenderer") as MockRenderer:
        mock_instance = MockRenderer.return_value
        mock_instance.render.return_value = b"%PDF-fake"
        with patch("printing.services.job_processor.PrinterService"):
            process_print_job(job)
        mock_instance.render.assert_called_once_with(
            barcode_text="TEST-123",
            asset_name="Test Asset",
            category_name="Category",
            qr_content="",
            quantity=1,
            department_name="Technical",
            site_short_name="HDM",
        )
```

**Step 2: Run test to verify it fails**

Run: `cd src && pytest printing/tests/test_job_processor.py::test_process_print_job_passes_department_and_site -v`
Expected: FAIL — renderer not called with `department_name`/`site_short_name`

**Step 3: Implement job_processor changes**

Update `process_print_job` in `src/printing/services/job_processor.py`:

```python
pdf_bytes = renderer.render(
    barcode_text=job.barcode,
    asset_name=job.asset_name,
    category_name=job.category_name,
    qr_content=job.qr_content or "",
    quantity=job.quantity,
    department_name=job.department_name,
    site_short_name=job.site_short_name,
)
```

**Step 4: Update management command**

In `src/printing/management/commands/run_print_client.py`, update `_on_print_job` to store new fields:

```python
job = PrintJob.objects.create(
    props_connection_id=connection_id,
    printer=printer,
    template=template,
    barcode=data["barcode"],
    asset_name=data["asset_name"],
    category_name=data["category_name"],
    qr_content=data.get("qr_content", ""),
    quantity=data.get("quantity", 1),
    department_name=data.get("department_name", ""),
    site_short_name=data.get("site_short_name", ""),
)
```

**Step 5: Run all tests**

Run: `cd src && pytest -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
cd src && git add printing/services/job_processor.py printing/management/commands/run_print_client.py printing/tests/test_job_processor.py
git commit -m "feat: wire department_name and site_short_name through print pipeline"
```

---

### Task 8: Format, lint, and run full test suite

**Files:**
- All modified files

**Step 1: Format code**

Run: `cd src && black . && isort .`

**Step 2: Lint**

Run: `cd src && flake8`
Expected: No errors

**Step 3: Run full test suite**

Run: `cd src && pytest -v`
Expected: ALL PASS

**Step 4: Commit any formatting changes**

```bash
cd src && git add -A && git status
# If there are formatting changes:
git commit -m "style: format code with black/isort"
```
