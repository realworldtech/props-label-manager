# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PROPS Label Manager is a Django-based label printing client that connects to PROPS (Physical Resource Operations and Properties System) servers via WebSocket. It renders label PDFs using ReportLab and sends them to thermal printers over TCP (port 9100). The admin interface uses django-unfold.

## Common Commands

```bash
# All commands run from the src/ directory
cd src

# Run all tests
pytest

# Run a single test file
pytest printing/tests/test_models.py

# Run a specific test
pytest printing/tests/test_models.py::TestLabelTemplate::test_create_label_template

# Run with coverage
coverage run -m pytest && coverage report

# Format code
black .
isort .

# Lint
flake8

# Run Django dev server
python manage.py runserver

# Run the WebSocket print client
python manage.py run_print_client --client-name 'My Client'

# Django migrations
python manage.py makemigrations
python manage.py migrate

# Docker (dev)
docker compose --profile dev up

# Docker (prod)
docker compose --profile prod up
```

## Architecture

### Data Flow

PROPS Server → WebSocket (JSON protocol) → `run_print_client` command → `process_print_job()` → `LabelRenderer.render()` → PDF bytes → `PrinterService.send()` → Thermal printer (TCP:9100)

### Key Components

- **`src/printclient/`** — Django project settings. Uses Unfold admin, WhiteNoise for static files, SQLite by default.
- **`src/printing/models.py`** — Five models: `LabelTemplate` (layout definition), `LabelElement` (positioned elements on a template), `PropsConnection` (WebSocket server link with pairing), `Printer` (thermal printer config), `PrintJob` (job tracking with status lifecycle: QUEUED→RENDERING→SENDING→COMPLETED/FAILED).
- **`src/printing/services/label_renderer.py`** — `LabelRenderer` takes a `LabelTemplate` + print data and produces PDF bytes via ReportLab. Elements positioned in mm, converted to points.
- **`src/printing/services/job_processor.py`** — `process_print_job()` orchestrates the full lifecycle: renders PDF, sends to printer, updates job status at each stage.
- **`src/printing/services/ws_client.py`** — Async WebSocket client with exponential backoff reconnection. Handles pairing flow and authenticated connections. Callback-driven.
- **`src/printing/services/printer.py`** — `PrinterService` sends raw PDF bytes via TCP socket.
- **`src/printing/services/protocol.py`** — JSON WebSocket message builders/parsers for PROPS protocol.
- **`src/printing/management/commands/run_print_client.py`** — Long-running async management command. Creates WebSocket clients for each active `PropsConnection`, bridges async callbacks to Django ORM via `asyncio.to_thread()`.

### Label Element Types

BARCODE_128, QR_CODE, ASSET_NAME, CATEGORY_NAME, BARCODE_TEXT, LOGO, STATIC_TEXT

## Configuration

Environment variables (see `.env.example`): `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CLIENT_NAME`, `TIME_ZONE` (default: Australia/Sydney), `GUNICORN_WORKERS`.

## Testing

- pytest with pytest-django and pytest-asyncio (asyncio_mode = "auto")
- factory-boy for test fixtures
- Tests mirror service structure: `test_models.py`, `test_label_renderer.py`, `test_job_processor.py`, `test_protocol.py`, `test_ws_client.py`, `test_printer_service.py`, `test_integration.py`
- `DJANGO_SETTINGS_MODULE = "printclient.settings"` and `pythonpath = ["src"]` configured in `pyproject.toml`

## Code Style

- **black** (line-length 88, target py312), **isort** (black profile), **flake8**
- Format and lint before committing
