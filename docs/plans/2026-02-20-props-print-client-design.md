# PROPS Label Print Client - Design Document

**Date:** 2026-02-20
**Project:** label-manager2 (PROPS Print Client)
**Status:** Approved

## Overview

A Django-based label printing client that connects to one or more PROPS (Physical Resource Operations and Properties System) servers via WebSocket. PROPS pushes print jobs to the client, which renders PDF labels from configurable templates and sends them to network thermal printers.

This replaces the existing PHP label-manager (which required manual barcode entry against CurrentRMS) with a push-based architecture where PROPS initiates prints directly.

## Architecture

```
PROPS Server(s)                     Print Client (this project)
┌──────────────┐                   ┌──────────────────────────────┐
│ Django       │  WebSocket (wss)  │ Management Command           │
│ Channels     │◄──────────────────│ (run_print_client)           │
│ /ws/print/   │──────────────────►│ - N async WebSocket clients  │
└──────────────┘                   │ - Auto-reconnect w/ backoff  │
                                   ├──────────────────────────────┤
                                   │ Print Engine                 │
                                   │ - PDF generation (FPDF2)     │
                                   │ - Barcode/QR rendering       │
                                   │ - Template-driven layout     │
                                   ├──────────────────────────────┤
                                   │ Django + Unfold Admin        │
                                   │ - Connection management      │
                                   │ - Printer configuration      │
                                   │ - Template editor            │
                                   │ - Print queue & history      │
                                   ├──────────────────────────────┤
                                   │ TCP Socket (port 9100)       │
                                   └──────────┬───────────────────┘
                                              │
                                   ┌──────────┴───────────┐
                                   │ Thermal Printer(s)   │
                                   └──────────────────────┘
```

**Key design decision:** The client initiates outbound WebSocket connections to PROPS servers. This means the client can run behind NAT/firewalls on a local network with printer access, without needing a public IP or port forwarding.

## Technology Stack

- **Framework:** Django 5.x with django-unfold admin
- **WebSocket client:** `websockets` library (asyncio-based)
- **PDF generation:** FPDF2 (lightweight, no system dependencies)
- **Barcode:** `python-barcode` (Code128)
- **QR codes:** `qrcode` library
- **Database:** SQLite (single-client deployment) or PostgreSQL
- **Process management:** Django management command for WebSocket client

## Data Models

### PropsConnection

A configured link to a PROPS server instance.

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField | Friendly name, e.g. "BeaMS Production" |
| `server_url` | URLField | WebSocket URL, e.g. `wss://beams.example.com/ws/print-service/` |
| `pairing_token` | CharField (nullable) | Long-lived token obtained during pairing |
| `is_active` | BooleanField | Whether to maintain the connection |
| `status` | CharField (choices) | `disconnected`, `connecting`, `connected`, `pairing`, `error` |
| `last_connected_at` | DateTimeField (nullable) | Last successful connection time |
| `last_error` | TextField (nullable) | Last error message |

### Printer

A configured network thermal printer.

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField | Friendly name, e.g. "Warehouse Zebra" |
| `ip_address` | GenericIPAddressField | Printer IP address |
| `port` | IntegerField (default 9100) | Printer port |
| `is_active` | BooleanField | Whether printer is available for jobs |
| `default_template` | ForeignKey(LabelTemplate, nullable) | Default label template |
| `status` | CharField (choices) | `unknown`, `online`, `offline`, `error` |

### LabelTemplate

Defines a label layout with dimensions and background.

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField | e.g. "Square 62x62mm" |
| `width_mm` | DecimalField | Label width in millimetres |
| `height_mm` | DecimalField | Label height in millimetres |
| `background_color` | CharField (default "#FFFFFF") | Background colour |
| `logo` | ImageField (nullable) | Optional logo image |
| `is_default` | BooleanField | Whether this is the default template |

### LabelElement

Individual elements positioned on a label template. Inline to LabelTemplate.

| Field | Type | Description |
|-------|------|-------------|
| `template` | ForeignKey(LabelTemplate) | Parent template |
| `element_type` | CharField (choices) | `barcode_128`, `qr_code`, `asset_name`, `category_name`, `barcode_text`, `logo`, `static_text` |
| `x_mm` | DecimalField | X position from left edge |
| `y_mm` | DecimalField | Y position from top edge |
| `width_mm` | DecimalField | Element width |
| `height_mm` | DecimalField | Element height |
| `rotation` | IntegerField (default 0) | Rotation: 0, 90, 180, 270 degrees |
| `font_name` | CharField (choices, nullable) | From bundled font set |
| `font_size_pt` | DecimalField (nullable) | Font size in points |
| `font_bold` | BooleanField (default False) | Bold text |
| `text_align` | CharField (choices) | `left`, `center`, `right` |
| `max_chars` | IntegerField (nullable) | Truncate text to this length |
| `static_content` | TextField (nullable) | Content for `static_text` type |
| `sort_order` | IntegerField | Render order (z-index) |

**Available fonts** (bundled, freely licensed):

| Font | Style | Use case |
|------|-------|----------|
| Helvetica | Sans-serif | General text, names |
| Courier | Monospace | Barcode text, IDs |
| Liberation Sans | Sans-serif | Cross-platform Helvetica alternative |
| Liberation Mono | Monospace | Cross-platform Courier alternative |
| DejaVu Sans | Sans-serif | Wide Unicode support |
| DejaVu Sans Mono | Monospace | Wide Unicode + monospace |

### PrintJob

A record of each print request.

| Field | Type | Description |
|-------|------|-------------|
| `props_connection` | ForeignKey(PropsConnection, nullable) | Source server (null for manual prints) |
| `printer` | ForeignKey(Printer) | Target printer |
| `template` | ForeignKey(LabelTemplate) | Label template used |
| `status` | CharField (choices) | `queued`, `rendering`, `sending`, `completed`, `failed` |
| `barcode` | CharField | Asset barcode string |
| `asset_name` | CharField | Asset name |
| `category_name` | CharField | Category name |
| `quantity` | IntegerField (default 1) | Number of copies |
| `error_message` | TextField (nullable) | Error details if failed |
| `created_at` | DateTimeField (auto) | When job was created |
| `completed_at` | DateTimeField (nullable) | When job finished |

## WebSocket Protocol (Contract)

All messages are JSON over WebSocket. This is the contract between PROPS and the print client.

### Authentication

**Client -> PROPS** (on connect):
```json
{
  "type": "authenticate",
  "token": "pairing-token-here",
  "client_name": "Office Print Station",
  "printers": [
    {
      "id": "printer-1",
      "name": "Warehouse Zebra",
      "status": "online",
      "templates": ["square-62x62", "rect-62x29"]
    }
  ]
}
```

**PROPS -> Client** (auth response):
```json
{
  "type": "auth_result",
  "success": true,
  "server_name": "BeaMS Production"
}
```

### Pairing Flow

1. User creates a PropsConnection in the print client admin with the PROPS server URL
2. Client connects and sends a `pairing_request`:
```json
{
  "type": "pairing_request",
  "client_name": "Office Print Station"
}
```
3. PROPS shows the pending printer client in its admin UI
4. PROPS admin approves, PROPS sends:
```json
{
  "type": "pairing_approved",
  "token": "long-lived-token-here",
  "server_name": "BeaMS Production"
}
```
5. Client stores the token and reconnects as authenticated

### Print Job

**PROPS -> Client** (print request):
```json
{
  "type": "print",
  "job_id": "uuid-from-props",
  "printer_id": "printer-1",
  "barcode": "BEAMS-A1B2C3D4",
  "asset_name": "Wireless Microphone",
  "category_name": "Audio Equipment",
  "quantity": 1
}
```

**Client -> PROPS** (status update):
```json
{
  "type": "print_status",
  "job_id": "uuid-from-props",
  "status": "completed",
  "error": null
}
```

### Keepalive

Standard WebSocket ping/pong frames for connection health monitoring.

## Print Engine

The PDF rendering pipeline:

1. Create blank PDF page at template dimensions (`width_mm` x `height_mm`)
2. Iterate `LabelElement` records ordered by `sort_order`
3. Render each element at its configured position:
   - `barcode_128` -> Generate Code128 PNG via `python-barcode`, place at x/y/width/height
   - `qr_code` -> Generate QR PNG via `qrcode` library, place at position
   - `asset_name` / `category_name` / `barcode_text` -> Render text from print job data with configured font/size/alignment, truncated to `max_chars`
   - `logo` -> Place template's logo image at position
   - `static_text` -> Render `static_content` with configured font
4. Repeat for `quantity` copies (one page per copy)
5. Send raw PDF bytes to printer via TCP socket

## Management Command

`python manage.py run_print_client` - long-running process:

- On startup: query all active PropsConnection records
- For each: spawn an async WebSocket client task (asyncio + websockets library)
- Each connection handles:
  - Connect and authenticate (or initiate pairing if no token)
  - Receive print jobs, create PrintJob records, render and send to printer, report status
  - Auto-reconnect with exponential backoff on disconnection
  - Heartbeat via WebSocket ping/pong
- Periodically re-check database for new/changed/deactivated connections

## Admin UI (Unfold)

| Section | Features |
|---------|----------|
| **Dashboard** | Connection status overview, recent print jobs, printer health |
| **PROPS Connections** | Add/edit/remove servers, trigger pairing, see live status |
| **Printers** | Configure IP/port, set default template, test print button |
| **Label Templates** | Create/edit templates with inline LabelElement editor, preview |
| **Print Jobs** | Filterable list with status, timestamps, errors. Manual reprint |

## Testing Strategy

- **Unit tests:** Print engine (PDF generation), template rendering, WebSocket message parsing
- **Integration tests:** WebSocket client connection/reconnection, printer communication (mocked socket)
- **Contract tests:** Validate WebSocket message schemas match the protocol spec
- **Manual tests:** End-to-end with real printer and PROPS dev instance

## Future Considerations

- Electron desktop wrapper (bundle Django + management command)
- USB printer support (direct USB instead of network TCP)
- ZPL output format (in addition to PDF)
- Replicating CurrentRMS manual barcode lookup (legacy support)
- Label preview in admin UI (render PDF to image)
