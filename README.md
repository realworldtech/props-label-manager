# PROPS Label Manager

A Django-based print client for [PROPS](https://github.com/realworldtech) (Physical Resource Operations and Properties System). It connects to PROPS servers via WebSocket, receives print requests, renders asset labels as PDFs, and sends them to thermal printers over TCP.

## How It Works

```
PROPS Server ──WebSocket──▶ Print Client ──render──▶ PDF ──TCP:9100──▶ Thermal Printer
```

1. The print client connects to one or more PROPS servers via WebSocket
2. On first connection, a pairing flow exchanges a token for future authentication
3. When PROPS dispatches a print job, the client receives it as a JSON message
4. A label PDF is rendered from a configurable template using ReportLab
5. The PDF is sent to the assigned thermal printer over a raw TCP socket

## Features

- **Template-driven labels** — design labels in the admin with positioned elements (barcodes, QR codes, text, logos) specified in millimetres
- **Code 128 barcodes and QR codes** — QR codes can encode a custom URL or fall back to the barcode string
- **Multi-copy printing** — render multiple copies in a single PDF
- **WebSocket auto-reconnect** — exponential backoff reconnection to PROPS servers
- **Pairing flow** — secure token-based pairing with PROPS servers
- **Admin interface** — [django-unfold](https://github.com/unfoldadmin/django-unfold) admin for managing printers, templates, connections, and job history
- **Docker ready** — development and production Docker Compose profiles

## Quick Start

### Local Development

```bash
# Clone and install
git clone https://github.com/realworldtech/props-label-manager.git
cd props-label-manager
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your settings

# Set up database and run
cd src
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then open http://localhost:8000/admin/ to configure printers, templates, and PROPS connections.

### Start the Print Client

In a separate terminal:

```bash
cd src
python manage.py run_print_client --client-name 'My Print Station'
```

This starts WebSocket connections to all active PROPS connections and listens for print jobs.

### Docker

```bash
cp .env.example .env
# Edit .env

docker compose up
```

This starts both the admin web server and the print client.

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Yes | — | Django secret key |
| `DEBUG` | No | `True` | Debug mode |
| `ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | Comma-separated hostnames |
| `CLIENT_NAME` | No | `PROPS Print Client` | How this client identifies to PROPS servers |
| `TIME_ZONE` | No | `Australia/Sydney` | Timezone |
| `GUNICORN_WORKERS` | No | `2` | Production worker count |

### Setting Up a Label Template

1. Go to **Admin > Label Templates** and create a template (e.g. 62x62mm for a square label)
2. Add elements to the template — position each element by specifying X/Y coordinates and dimensions in millimetres
3. Available element types: **Barcode (Code 128)**, **QR Code**, **Asset Name**, **Category Name**, **Barcode Text**, **Logo**, **Static Text**
4. Assign the template as a printer's default or select it per job

### Connecting to PROPS

1. Go to **Admin > PROPS Connections** and add your server's WebSocket URL
2. Start the print client — it will initiate pairing automatically
3. Approve the pairing request on the PROPS server
4. The connection is now authenticated and ready to receive print jobs

## Running Tests

```bash
cd src
pytest
```

## Tech Stack

- **Python 3.13** / **Django 5.2**
- **ReportLab** — PDF rendering
- **python-barcode** — Code 128 barcodes
- **qrcode** — QR code generation
- **websockets** — async WebSocket client
- **django-unfold** — admin interface
- **WhiteNoise** — static file serving
- **Gunicorn** — production WSGI server

## License

Proprietary — Real World Technology Solutions Pty Ltd.
