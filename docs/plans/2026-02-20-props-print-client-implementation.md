# PROPS Label Print Client - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Django-based label printing client that receives print jobs from PROPS servers via WebSocket and renders PDF labels to network thermal printers.

**Architecture:** Django project with Unfold admin for UI, a `printing` app for all models/services, asyncio management command for WebSocket client connections, and FPDF2 for PDF label generation from element-based templates.

**Tech Stack:** Django 5.2, django-unfold 0.78, FPDF2, python-barcode, qrcode, websockets (asyncio), pytest-django

---

### Task 1: Project Scaffolding

**Files:**
- Create: `src/manage.py`
- Create: `src/printclient/__init__.py`
- Create: `src/printclient/settings.py`
- Create: `src/printclient/urls.py`
- Create: `src/printclient/wsgi.py`
- Create: `src/printing/__init__.py`
- Create: `src/printing/admin.py`
- Create: `src/printing/models.py`
- Create: `src/printing/apps.py`
- Create: `requirements.txt`
- Create: `pyproject.toml`
- Create: `pytest.ini`

**Step 1: Create requirements.txt**

```
Django==5.2.11
django-unfold==0.78.1
fpdf2==2.8.3
python-barcode[images]==0.16.1
qrcode[pil]==8.2
websockets==15.0.1
Pillow==12.1.1
whitenoise==6.11.0
gunicorn==25.0.2
black==26.1.0
flake8==7.3.0
isort==7.0.0
pytest==8.3.5
pytest-django==4.11.1
pytest-asyncio==0.25.3
factory-boy==3.3.3
coverage==7.13.3
```

**Step 2: Create pyproject.toml**

```toml
[tool.black]
line-length = 88
target-version = ["py312"]

[tool.isort]
profile = "black"

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "printclient.settings"
python_files = ["tests.py", "test_*.py", "*_tests.py"]
python_paths = ["src"]
```

**Step 3: Create Django project structure**

Create `src/printclient/settings.py` with:
- `INSTALLED_APPS` with `unfold` first, then `unfold.contrib.filters`, then Django builtins, then `printing`
- `UNFOLD` config with `SITE_TITLE = "PROPS Print Client"`, `SITE_SYMBOL = "print"`, sidebar navigation for Dashboard, Connections, Printers, Templates, Print Jobs
- SQLite as default database
- `STATIC_URL`, `MEDIA_URL`, `MEDIA_ROOT` configuration
- WhiteNoise middleware for static files

Create `src/printclient/urls.py` with admin URL and media serving in debug.

Create `src/printclient/wsgi.py` with standard WSGI application.

Create `src/manage.py` with standard Django manage.py.

Create `src/printing/apps.py` with `PrintingConfig` class.

Create empty `src/printing/models.py`, `src/printing/admin.py`.

**Step 4: Create virtual environment and install dependencies**

Run: `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`

**Step 5: Verify Django starts**

Run: `cd src && python manage.py check`
Expected: `System check identified no issues.`

**Step 6: Commit**

```bash
git add requirements.txt pyproject.toml src/
git commit -m "feat: scaffold Django project with Unfold admin"
```

---

### Task 2: Data Models - LabelTemplate and LabelElement

**Files:**
- Modify: `src/printing/models.py`
- Create: `src/printing/tests/__init__.py`
- Create: `src/printing/tests/test_models.py`

**Step 1: Write the failing tests**

```python
# src/printing/tests/test_models.py
import pytest
from printing.models import LabelTemplate, LabelElement, FontChoices, ElementType, TextAlign


@pytest.mark.django_db
class TestLabelTemplate:
    def test_create_template(self):
        template = LabelTemplate.objects.create(
            name="Square 62x62mm",
            width_mm=62,
            height_mm=62,
        )
        assert template.name == "Square 62x62mm"
        assert template.width_mm == 62
        assert template.height_mm == 62
        assert template.background_color == "#FFFFFF"
        assert template.is_default is False
        assert str(template) == "Square 62x62mm (62x62mm)"

    def test_only_one_default(self):
        t1 = LabelTemplate.objects.create(
            name="Template 1", width_mm=62, height_mm=62, is_default=True
        )
        t2 = LabelTemplate.objects.create(
            name="Template 2", width_mm=62, height_mm=29, is_default=True
        )
        t1.refresh_from_db()
        assert t1.is_default is False
        assert t2.is_default is True


@pytest.mark.django_db
class TestLabelElement:
    def test_create_element(self):
        template = LabelTemplate.objects.create(
            name="Test", width_mm=62, height_mm=62
        )
        element = LabelElement.objects.create(
            template=template,
            element_type=ElementType.BARCODE_128,
            x_mm=5,
            y_mm=10,
            width_mm=50,
            height_mm=15,
            sort_order=1,
        )
        assert element.element_type == "barcode_128"
        assert element.rotation == 0
        assert element.font_bold is False

    def test_text_element_with_font(self):
        template = LabelTemplate.objects.create(
            name="Test", width_mm=62, height_mm=62
        )
        element = LabelElement.objects.create(
            template=template,
            element_type=ElementType.ASSET_NAME,
            x_mm=5,
            y_mm=40,
            width_mm=50,
            height_mm=10,
            font_name=FontChoices.HELVETICA,
            font_size_pt=12,
            font_bold=True,
            text_align=TextAlign.CENTER,
            max_chars=20,
            sort_order=2,
        )
        assert element.font_name == "helvetica"
        assert element.text_align == "center"

    def test_element_ordering(self):
        template = LabelTemplate.objects.create(
            name="Test", width_mm=62, height_mm=62
        )
        e2 = LabelElement.objects.create(
            template=template, element_type=ElementType.QR_CODE,
            x_mm=0, y_mm=0, width_mm=10, height_mm=10, sort_order=2
        )
        e1 = LabelElement.objects.create(
            template=template, element_type=ElementType.BARCODE_128,
            x_mm=0, y_mm=0, width_mm=10, height_mm=10, sort_order=1
        )
        elements = list(template.elements.all())
        assert elements[0] == e1
        assert elements[1] == e2
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest printing/tests/test_models.py -v`
Expected: ImportError (models don't exist yet)

**Step 3: Implement the models**

In `src/printing/models.py`:

```python
from django.db import models


class FontChoices(models.TextChoices):
    HELVETICA = "helvetica", "Helvetica"
    COURIER = "courier", "Courier"
    LIBERATION_SANS = "liberation_sans", "Liberation Sans"
    LIBERATION_MONO = "liberation_mono", "Liberation Mono"
    DEJAVU_SANS = "dejavu_sans", "DejaVu Sans"
    DEJAVU_MONO = "dejavu_mono", "DejaVu Sans Mono"


class ElementType(models.TextChoices):
    BARCODE_128 = "barcode_128", "Barcode (Code 128)"
    QR_CODE = "qr_code", "QR Code"
    ASSET_NAME = "asset_name", "Asset Name"
    CATEGORY_NAME = "category_name", "Category Name"
    BARCODE_TEXT = "barcode_text", "Barcode Text"
    LOGO = "logo", "Logo"
    STATIC_TEXT = "static_text", "Static Text"


class TextAlign(models.TextChoices):
    LEFT = "left", "Left"
    CENTER = "center", "Centre"
    RIGHT = "right", "Right"


class LabelTemplate(models.Model):
    name = models.CharField(max_length=100)
    width_mm = models.DecimalField(max_digits=6, decimal_places=2)
    height_mm = models.DecimalField(max_digits=6, decimal_places=2)
    background_color = models.CharField(max_length=7, default="#FFFFFF")
    logo = models.ImageField(upload_to="logos/", blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.width_mm}x{self.height_mm}mm)"

    def save(self, *args, **kwargs):
        if self.is_default:
            LabelTemplate.objects.filter(is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)


class LabelElement(models.Model):
    template = models.ForeignKey(
        LabelTemplate, on_delete=models.CASCADE, related_name="elements"
    )
    element_type = models.CharField(max_length=20, choices=ElementType.choices)
    x_mm = models.DecimalField(max_digits=6, decimal_places=2)
    y_mm = models.DecimalField(max_digits=6, decimal_places=2)
    width_mm = models.DecimalField(max_digits=6, decimal_places=2)
    height_mm = models.DecimalField(max_digits=6, decimal_places=2)
    rotation = models.IntegerField(default=0)
    font_name = models.CharField(
        max_length=20, choices=FontChoices.choices, blank=True, null=True
    )
    font_size_pt = models.DecimalField(
        max_digits=5, decimal_places=1, blank=True, null=True
    )
    font_bold = models.BooleanField(default=False)
    text_align = models.CharField(
        max_length=10, choices=TextAlign.choices, default=TextAlign.LEFT
    )
    max_chars = models.IntegerField(blank=True, null=True)
    static_content = models.TextField(blank=True, null=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return f"{self.get_element_type_display()} at ({self.x_mm}, {self.y_mm})"
```

**Step 4: Make and run migrations**

Run: `cd src && python manage.py makemigrations printing && python manage.py migrate`

**Step 5: Run tests to verify they pass**

Run: `cd src && python -m pytest printing/tests/test_models.py -v`
Expected: All 5 tests PASS

**Step 6: Commit**

```bash
git add src/printing/models.py src/printing/tests/ src/printing/migrations/
git commit -m "feat: add LabelTemplate and LabelElement models with tests"
```

---

### Task 3: Data Models - Printer, PropsConnection, PrintJob

**Files:**
- Modify: `src/printing/models.py`
- Modify: `src/printing/tests/test_models.py`

**Step 1: Write the failing tests**

Append to `src/printing/tests/test_models.py`:

```python
from printing.models import (
    Printer, PropsConnection, PrintJob,
    ConnectionStatus, PrinterStatus, JobStatus,
)


@pytest.mark.django_db
class TestPrinter:
    def test_create_printer(self):
        printer = Printer.objects.create(
            name="Warehouse Zebra",
            ip_address="192.168.1.100",
        )
        assert printer.port == 9100
        assert printer.is_active is True
        assert printer.status == "unknown"
        assert str(printer) == "Warehouse Zebra (192.168.1.100:9100)"

    def test_printer_with_default_template(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(
            name="Office", ip_address="10.0.0.50",
            default_template=template,
        )
        assert printer.default_template == template


@pytest.mark.django_db
class TestPropsConnection:
    def test_create_connection(self):
        conn = PropsConnection.objects.create(
            name="BeaMS Production",
            server_url="wss://beams.example.com/ws/print-service/",
        )
        assert conn.is_active is True
        assert conn.status == "disconnected"
        assert conn.pairing_token is None
        assert str(conn) == "BeaMS Production"

    def test_connection_with_token(self):
        conn = PropsConnection.objects.create(
            name="BeaMS",
            server_url="wss://beams.example.com/ws/print-service/",
            pairing_token="secret-token-123",
        )
        assert conn.pairing_token == "secret-token-123"
        assert conn.is_paired is True

    def test_unpaired_connection(self):
        conn = PropsConnection.objects.create(
            name="BeaMS",
            server_url="wss://beams.example.com/ws/print-service/",
        )
        assert conn.is_paired is False


@pytest.mark.django_db
class TestPrintJob:
    def test_create_print_job(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(
            name="Zebra", ip_address="192.168.1.100"
        )
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            barcode="BEAMS-A1B2C3D4",
            asset_name="Wireless Mic",
            category_name="Audio",
        )
        assert job.status == "queued"
        assert job.quantity == 1
        assert job.props_connection is None
        assert job.completed_at is None
        assert str(job) == "BEAMS-A1B2C3D4 - queued"

    def test_print_job_with_connection(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        printer = Printer.objects.create(
            name="Zebra", ip_address="192.168.1.100"
        )
        conn = PropsConnection.objects.create(
            name="BeaMS", server_url="wss://beams.example.com/ws/print-service/"
        )
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            props_connection=conn,
            barcode="BEAMS-DEADBEEF",
            asset_name="Camera",
            category_name="Video",
            quantity=3,
        )
        assert job.props_connection == conn
        assert job.quantity == 3
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest printing/tests/test_models.py -v`
Expected: ImportError for new model classes

**Step 3: Add remaining models to `src/printing/models.py`**

```python
class ConnectionStatus(models.TextChoices):
    DISCONNECTED = "disconnected", "Disconnected"
    CONNECTING = "connecting", "Connecting"
    CONNECTED = "connected", "Connected"
    PAIRING = "pairing", "Pairing"
    ERROR = "error", "Error"


class PrinterStatus(models.TextChoices):
    UNKNOWN = "unknown", "Unknown"
    ONLINE = "online", "Online"
    OFFLINE = "offline", "Offline"
    ERROR = "error", "Error"


class JobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RENDERING = "rendering", "Rendering"
    SENDING = "sending", "Sending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class PropsConnection(models.Model):
    name = models.CharField(max_length=100)
    server_url = models.URLField()
    pairing_token = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.DISCONNECTED,
    )
    last_connected_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_paired(self):
        return bool(self.pairing_token)


class Printer(models.Model):
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField(default=9100)
    is_active = models.BooleanField(default=True)
    default_template = models.ForeignKey(
        LabelTemplate, on_delete=models.SET_NULL, blank=True, null=True
    )
    status = models.CharField(
        max_length=20,
        choices=PrinterStatus.choices,
        default=PrinterStatus.UNKNOWN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.ip_address}:{self.port})"


class PrintJob(models.Model):
    props_connection = models.ForeignKey(
        PropsConnection, on_delete=models.SET_NULL, blank=True, null=True
    )
    printer = models.ForeignKey(Printer, on_delete=models.CASCADE)
    template = models.ForeignKey(LabelTemplate, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=JobStatus.choices, default=JobStatus.QUEUED
    )
    barcode = models.CharField(max_length=100)
    asset_name = models.CharField(max_length=200)
    category_name = models.CharField(max_length=200)
    quantity = models.IntegerField(default=1)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.barcode} - {self.status}"
```

**Step 4: Make and run migrations**

Run: `cd src && python manage.py makemigrations printing && python manage.py migrate`

**Step 5: Run tests to verify they pass**

Run: `cd src && python -m pytest printing/tests/test_models.py -v`
Expected: All 12 tests PASS

**Step 6: Commit**

```bash
git add src/printing/models.py src/printing/tests/test_models.py src/printing/migrations/
git commit -m "feat: add Printer, PropsConnection, and PrintJob models with tests"
```

---

### Task 4: Unfold Admin Registration

**Files:**
- Modify: `src/printing/admin.py`
- Modify: `src/printclient/settings.py` (UNFOLD sidebar config)

**Step 1: Write the admin classes**

Following the PROPS patterns from `beamsassethandler/src/assets/admin.py`:

```python
# src/printing/admin.py
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import ChoicesDropdownFilter
from unfold.decorators import action, display

from printing.models import (
    LabelElement,
    LabelTemplate,
    Printer,
    PrintJob,
    PropsConnection,
)


class LabelElementInline(TabularInline):
    model = LabelElement
    extra = 1
    fields = [
        "element_type",
        "x_mm",
        "y_mm",
        "width_mm",
        "height_mm",
        "rotation",
        "font_name",
        "font_size_pt",
        "font_bold",
        "text_align",
        "max_chars",
        "static_content",
        "sort_order",
    ]


@admin.register(LabelTemplate)
class LabelTemplateAdmin(ModelAdmin):
    list_display = ["name", "display_dimensions", "display_default", "display_element_count"]
    list_filter = ["is_default"]
    search_fields = ["name"]
    inlines = [LabelElementInline]
    fieldsets = (
        (None, {"fields": ("name", "width_mm", "height_mm", "background_color", "logo", "is_default")}),
    )

    @display(description="Dimensions")
    def display_dimensions(self, obj):
        return f"{obj.width_mm} x {obj.height_mm} mm"

    @display(description="Default", boolean=True)
    def display_default(self, obj):
        return obj.is_default

    @display(description="Elements")
    def display_element_count(self, obj):
        return obj.elements.count()


@admin.register(Printer)
class PrinterAdmin(ModelAdmin):
    list_display = ["name", "ip_address", "port", "display_status", "display_active"]
    list_filter = [("status", ChoicesDropdownFilter), "is_active"]
    search_fields = ["name", "ip_address"]
    autocomplete_fields = ["default_template"]
    fieldsets = (
        (None, {"fields": ("name", "ip_address", "port", "is_active", "default_template")}),
        ("Status", {"fields": ("status",), "classes": ["tab"]}),
    )

    @display(
        description="Status",
        label={
            "unknown": "default",
            "online": "success",
            "offline": "warning",
            "error": "danger",
        },
    )
    def display_status(self, obj):
        return obj.status

    @display(description="Active", boolean=True)
    def display_active(self, obj):
        return obj.is_active


@admin.register(PropsConnection)
class PropsConnectionAdmin(ModelAdmin):
    list_display = ["name", "server_url", "display_status", "display_paired", "last_connected_at"]
    list_filter = [("status", ChoicesDropdownFilter), "is_active"]
    search_fields = ["name", "server_url"]
    readonly_fields = ["status", "last_connected_at", "last_error", "pairing_token"]
    fieldsets = (
        (None, {"fields": ("name", "server_url", "is_active")}),
        ("Connection Status", {"fields": ("status", "pairing_token", "last_connected_at", "last_error"), "classes": ["tab"]}),
    )

    @display(
        description="Status",
        label={
            "disconnected": "default",
            "connecting": "info",
            "connected": "success",
            "pairing": "warning",
            "error": "danger",
        },
    )
    def display_status(self, obj):
        return obj.status

    @display(description="Paired", boolean=True)
    def display_paired(self, obj):
        return obj.is_paired


@admin.register(PrintJob)
class PrintJobAdmin(ModelAdmin):
    list_display = ["barcode", "asset_name", "display_status", "printer", "props_connection", "created_at"]
    list_filter = [
        ("status", ChoicesDropdownFilter),
        ("printer", ChoicesDropdownFilter),
        ("props_connection", ChoicesDropdownFilter),
    ]
    list_filter_submit = True
    search_fields = ["barcode", "asset_name", "category_name"]
    readonly_fields = ["created_at", "completed_at"]
    fieldsets = (
        (None, {"fields": ("barcode", "asset_name", "category_name", "quantity")}),
        ("Routing", {"fields": ("printer", "template", "props_connection")}),
        ("Status", {"fields": ("status", "error_message", "created_at", "completed_at"), "classes": ["tab"]}),
    )

    @display(
        description="Status",
        label={
            "queued": "info",
            "rendering": "info",
            "sending": "warning",
            "completed": "success",
            "failed": "danger",
        },
    )
    def display_status(self, obj):
        return obj.status
```

**Step 2: Update UNFOLD sidebar in settings.py**

Add sidebar navigation with sections for Printing (Connections, Printers, Templates, Print Jobs).

**Step 3: Create superuser and verify admin loads**

Run: `cd src && python manage.py createsuperuser --username admin --email admin@test.com`
Run: `cd src && python manage.py runserver`
Visit: `http://localhost:8000/admin/` - verify all models appear with Unfold styling

**Step 4: Commit**

```bash
git add src/printing/admin.py src/printclient/settings.py
git commit -m "feat: register all models with Unfold admin and sidebar navigation"
```

---

### Task 5: Print Engine - PDF Label Rendering

**Files:**
- Create: `src/printing/services/__init__.py`
- Create: `src/printing/services/label_renderer.py`
- Create: `src/printing/tests/test_label_renderer.py`

**Step 1: Write the failing tests**

```python
# src/printing/tests/test_label_renderer.py
import pytest
from decimal import Decimal
from unittest.mock import patch
from printing.models import LabelTemplate, LabelElement, ElementType, FontChoices, TextAlign
from printing.services.label_renderer import LabelRenderer


@pytest.mark.django_db
class TestLabelRenderer:
    def _create_template_with_elements(self):
        """Helper: creates a square template with barcode, QR, name, category."""
        template = LabelTemplate.objects.create(
            name="Square 62x62mm", width_mm=62, height_mm=62
        )
        LabelElement.objects.create(
            template=template, element_type=ElementType.QR_CODE,
            x_mm=6, y_mm=6, width_mm=50, height_mm=50, sort_order=1
        )
        LabelElement.objects.create(
            template=template, element_type=ElementType.ASSET_NAME,
            x_mm=2, y_mm=2, width_mm=58, height_mm=5,
            font_name=FontChoices.HELVETICA, font_size_pt=8,
            font_bold=True, text_align=TextAlign.CENTER,
            max_chars=20, sort_order=2
        )
        LabelElement.objects.create(
            template=template, element_type=ElementType.BARCODE_TEXT,
            x_mm=2, y_mm=57, width_mm=58, height_mm=4,
            font_name=FontChoices.COURIER, font_size_pt=6,
            text_align=TextAlign.CENTER, sort_order=3
        )
        return template

    def test_render_returns_pdf_bytes(self):
        template = self._create_template_with_elements()
        renderer = LabelRenderer(template)
        pdf_bytes = renderer.render(
            barcode="BEAMS-A1B2C3D4",
            asset_name="Wireless Microphone",
            category_name="Audio Equipment",
        )
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_render_with_quantity(self):
        template = self._create_template_with_elements()
        renderer = LabelRenderer(template)
        pdf_bytes = renderer.render(
            barcode="BEAMS-A1B2C3D4",
            asset_name="Test Asset",
            category_name="Test Category",
            quantity=3,
        )
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_render_truncates_long_name(self):
        template = self._create_template_with_elements()
        renderer = LabelRenderer(template)
        # Should not raise even with a very long name
        pdf_bytes = renderer.render(
            barcode="BEAMS-12345678",
            asset_name="This Is An Extremely Long Asset Name That Exceeds Max Chars",
            category_name="Category",
        )
        assert isinstance(pdf_bytes, bytes)

    def test_render_with_barcode_element(self):
        template = LabelTemplate.objects.create(
            name="With Barcode", width_mm=62, height_mm=29
        )
        LabelElement.objects.create(
            template=template, element_type=ElementType.BARCODE_128,
            x_mm=2, y_mm=5, width_mm=40, height_mm=15, sort_order=1
        )
        renderer = LabelRenderer(template)
        pdf_bytes = renderer.render(
            barcode="BEAMS-DEADBEEF",
            asset_name="Test",
            category_name="Test",
        )
        assert pdf_bytes[:5] == b"%PDF-"

    def test_render_with_static_text(self):
        template = LabelTemplate.objects.create(
            name="With Static", width_mm=62, height_mm=62
        )
        LabelElement.objects.create(
            template=template, element_type=ElementType.STATIC_TEXT,
            x_mm=2, y_mm=55, width_mm=58, height_mm=5,
            font_name=FontChoices.HELVETICA, font_size_pt=6,
            static_content="Property of BeaMS",
            text_align=TextAlign.CENTER, sort_order=1
        )
        renderer = LabelRenderer(template)
        pdf_bytes = renderer.render(
            barcode="BEAMS-12345678",
            asset_name="Test",
            category_name="Test",
        )
        assert pdf_bytes[:5] == b"%PDF-"
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest printing/tests/test_label_renderer.py -v`
Expected: ImportError

**Step 3: Implement the label renderer**

```python
# src/printing/services/label_renderer.py
import io
import tempfile
from decimal import Decimal

import barcode
from barcode.writer import ImageWriter
import qrcode
from fpdf import FPDF

from printing.models import ElementType, LabelTemplate


# Map model font names to FPDF built-in font names
FONT_MAP = {
    "helvetica": "helvetica",
    "courier": "courier",
    "liberation_sans": "helvetica",  # FPDF built-in fallback
    "liberation_mono": "courier",
    "dejavu_sans": "helvetica",
    "dejavu_mono": "courier",
}


class LabelRenderer:
    def __init__(self, template: LabelTemplate):
        self.template = template

    def render(self, barcode_text: str, asset_name: str, category_name: str, quantity: int = 1) -> bytes:
        width = float(self.template.width_mm)
        height = float(self.template.height_mm)
        orientation = "L" if width > height else "P"

        pdf = FPDF(orientation=orientation, unit="mm", format=(width, height))
        pdf.set_auto_page_break(auto=False)

        elements = self.template.elements.all()

        for _ in range(quantity):
            pdf.add_page()
            for element in elements:
                self._render_element(pdf, element, barcode_text, asset_name, category_name)

        return pdf.output()

    def _render_element(self, pdf: FPDF, element, barcode_text: str, asset_name: str, category_name: str):
        x = float(element.x_mm)
        y = float(element.y_mm)
        w = float(element.width_mm)
        h = float(element.height_mm)

        if element.element_type == ElementType.BARCODE_128:
            self._render_barcode(pdf, barcode_text, x, y, w, h)
        elif element.element_type == ElementType.QR_CODE:
            self._render_qr(pdf, barcode_text, x, y, w, h)
        elif element.element_type == ElementType.ASSET_NAME:
            self._render_text(pdf, element, asset_name, x, y, w, h)
        elif element.element_type == ElementType.CATEGORY_NAME:
            self._render_text(pdf, element, category_name, x, y, w, h)
        elif element.element_type == ElementType.BARCODE_TEXT:
            self._render_text(pdf, element, barcode_text, x, y, w, h)
        elif element.element_type == ElementType.LOGO:
            self._render_logo(pdf, x, y, w, h)
        elif element.element_type == ElementType.STATIC_TEXT:
            self._render_text(pdf, element, element.static_content or "", x, y, w, h)

    def _render_barcode(self, pdf: FPDF, text: str, x: float, y: float, w: float, h: float):
        code128 = barcode.get("code128", text, writer=ImageWriter())
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            code128.write(tmp, options={"write_text": False})
            tmp.flush()
            pdf.image(tmp.name, x=x, y=y, w=w, h=h)

    def _render_qr(self, pdf: FPDF, text: str, x: float, y: float, w: float, h: float):
        qr = qrcode.make(text, box_size=10, border=1)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            qr.save(tmp)
            tmp.flush()
            pdf.image(tmp.name, x=x, y=y, w=w, h=h)

    def _render_text(self, pdf: FPDF, element, text: str, x: float, y: float, w: float, h: float):
        if element.max_chars and len(text) > element.max_chars:
            text = text[: element.max_chars]

        font_name = FONT_MAP.get(element.font_name, "helvetica")
        style = "B" if element.font_bold else ""
        size = float(element.font_size_pt) if element.font_size_pt else 10

        pdf.set_font(font_name, style, size)

        align_map = {"left": "L", "center": "C", "right": "R"}
        align = align_map.get(element.text_align, "L")

        pdf.set_xy(x, y)
        pdf.cell(w=w, h=h, text=text, align=align)

    def _render_logo(self, pdf: FPDF, x: float, y: float, w: float, h: float):
        if self.template.logo:
            pdf.image(self.template.logo.path, x=x, y=y, w=w, h=h)
```

**Step 4: Run tests to verify they pass**

Run: `cd src && python -m pytest printing/tests/test_label_renderer.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/printing/services/ src/printing/tests/test_label_renderer.py
git commit -m "feat: implement PDF label renderer with template-driven element positioning"
```

---

### Task 6: Printer Communication Service

**Files:**
- Create: `src/printing/services/printer.py`
- Create: `src/printing/tests/test_printer_service.py`

**Step 1: Write the failing tests**

```python
# src/printing/tests/test_printer_service.py
import pytest
from unittest.mock import patch, MagicMock
from printing.services.printer import PrinterService, PrintError


class TestPrinterService:
    def test_send_to_printer_success(self):
        mock_socket = MagicMock()
        with patch("printing.services.printer.socket.socket", return_value=mock_socket):
            service = PrinterService("192.168.1.100", 9100)
            service.send(b"%PDF-fake-data")
            mock_socket.connect.assert_called_once_with(("192.168.1.100", 9100))
            mock_socket.sendall.assert_called_once_with(b"%PDF-fake-data")
            mock_socket.close.assert_called_once()

    def test_send_to_printer_connection_error(self):
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = ConnectionRefusedError("refused")
        with patch("printing.services.printer.socket.socket", return_value=mock_socket):
            service = PrinterService("192.168.1.100", 9100)
            with pytest.raises(PrintError, match="Failed to connect"):
                service.send(b"%PDF-fake-data")

    def test_send_to_printer_timeout(self):
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = TimeoutError("timed out")
        with patch("printing.services.printer.socket.socket", return_value=mock_socket):
            service = PrinterService("192.168.1.100", 9100)
            with pytest.raises(PrintError, match="Failed to connect"):
                service.send(b"%PDF-fake-data")

    def test_send_sets_timeout(self):
        mock_socket = MagicMock()
        with patch("printing.services.printer.socket.socket", return_value=mock_socket):
            service = PrinterService("192.168.1.100", 9100, timeout=10)
            service.send(b"data")
            mock_socket.settimeout.assert_called_once_with(10)
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest printing/tests/test_printer_service.py -v`
Expected: ImportError

**Step 3: Implement the printer service**

```python
# src/printing/services/printer.py
import socket


class PrintError(Exception):
    pass


class PrinterService:
    def __init__(self, ip_address: str, port: int = 9100, timeout: int = 8):
        self.ip_address = ip_address
        self.port = port
        self.timeout = timeout

    def send(self, data: bytes) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.ip_address, self.port))
            sock.sendall(data)
        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            raise PrintError(f"Failed to connect to {self.ip_address}:{self.port}: {e}")
        finally:
            sock.close()
```

**Step 4: Run tests to verify they pass**

Run: `cd src && python -m pytest printing/tests/test_printer_service.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/printing/services/printer.py src/printing/tests/test_printer_service.py
git commit -m "feat: implement printer TCP socket service with error handling"
```

---

### Task 7: Print Job Processor

**Files:**
- Create: `src/printing/services/job_processor.py`
- Create: `src/printing/tests/test_job_processor.py`

**Step 1: Write the failing tests**

```python
# src/printing/tests/test_job_processor.py
import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone
from printing.models import (
    LabelTemplate, LabelElement, ElementType, FontChoices, TextAlign,
    Printer, PrintJob, JobStatus,
)
from printing.services.job_processor import process_print_job
from printing.services.printer import PrintError


@pytest.mark.django_db
class TestJobProcessor:
    def _setup(self):
        template = LabelTemplate.objects.create(
            name="Square", width_mm=62, height_mm=62
        )
        LabelElement.objects.create(
            template=template, element_type=ElementType.BARCODE_TEXT,
            x_mm=2, y_mm=50, width_mm=58, height_mm=5,
            font_name=FontChoices.COURIER, font_size_pt=8,
            text_align=TextAlign.CENTER, sort_order=1
        )
        printer = Printer.objects.create(
            name="Test", ip_address="192.168.1.100"
        )
        return template, printer

    @patch("printing.services.job_processor.PrinterService")
    @patch("printing.services.job_processor.LabelRenderer")
    def test_successful_job(self, MockRenderer, MockPrinterService):
        template, printer = self._setup()
        MockRenderer.return_value.render.return_value = b"%PDF-fake"
        job = PrintJob.objects.create(
            printer=printer, template=template,
            barcode="BEAMS-12345678", asset_name="Test", category_name="Cat"
        )
        process_print_job(job)
        job.refresh_from_db()
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None

    @patch("printing.services.job_processor.PrinterService")
    @patch("printing.services.job_processor.LabelRenderer")
    def test_render_failure(self, MockRenderer, MockPrinterService):
        template, printer = self._setup()
        MockRenderer.return_value.render.side_effect = Exception("render error")
        job = PrintJob.objects.create(
            printer=printer, template=template,
            barcode="BEAMS-12345678", asset_name="Test", category_name="Cat"
        )
        process_print_job(job)
        job.refresh_from_db()
        assert job.status == JobStatus.FAILED
        assert "render error" in job.error_message

    @patch("printing.services.job_processor.PrinterService")
    @patch("printing.services.job_processor.LabelRenderer")
    def test_print_failure(self, MockRenderer, MockPrinterService):
        template, printer = self._setup()
        MockRenderer.return_value.render.return_value = b"%PDF-fake"
        MockPrinterService.return_value.send.side_effect = PrintError("connection refused")
        job = PrintJob.objects.create(
            printer=printer, template=template,
            barcode="BEAMS-12345678", asset_name="Test", category_name="Cat"
        )
        process_print_job(job)
        job.refresh_from_db()
        assert job.status == JobStatus.FAILED
        assert "connection refused" in job.error_message

    @patch("printing.services.job_processor.PrinterService")
    @patch("printing.services.job_processor.LabelRenderer")
    def test_job_passes_quantity(self, MockRenderer, MockPrinterService):
        template, printer = self._setup()
        MockRenderer.return_value.render.return_value = b"%PDF-fake"
        job = PrintJob.objects.create(
            printer=printer, template=template,
            barcode="BEAMS-12345678", asset_name="Test", category_name="Cat",
            quantity=5,
        )
        process_print_job(job)
        MockRenderer.return_value.render.assert_called_once_with(
            barcode_text="BEAMS-12345678",
            asset_name="Test",
            category_name="Cat",
            quantity=5,
        )
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest printing/tests/test_job_processor.py -v`
Expected: ImportError

**Step 3: Implement the job processor**

```python
# src/printing/services/job_processor.py
import logging
from django.utils import timezone
from printing.models import PrintJob, JobStatus
from printing.services.label_renderer import LabelRenderer
from printing.services.printer import PrinterService, PrintError

logger = logging.getLogger(__name__)


def process_print_job(job: PrintJob) -> None:
    try:
        job.status = JobStatus.RENDERING
        job.save(update_fields=["status"])

        renderer = LabelRenderer(job.template)
        pdf_bytes = renderer.render(
            barcode_text=job.barcode,
            asset_name=job.asset_name,
            category_name=job.category_name,
            quantity=job.quantity,
        )
    except Exception as e:
        logger.error("Failed to render job %s: %s", job.pk, e)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.save(update_fields=["status", "error_message"])
        return

    try:
        job.status = JobStatus.SENDING
        job.save(update_fields=["status"])

        service = PrinterService(job.printer.ip_address, job.printer.port)
        service.send(pdf_bytes)
    except PrintError as e:
        logger.error("Failed to print job %s: %s", job.pk, e)
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.save(update_fields=["status", "error_message"])
        return

    job.status = JobStatus.COMPLETED
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "completed_at"])
    logger.info("Print job %s completed successfully", job.pk)
```

**Step 4: Run tests to verify they pass**

Run: `cd src && python -m pytest printing/tests/test_job_processor.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/printing/services/job_processor.py src/printing/tests/test_job_processor.py
git commit -m "feat: implement print job processor orchestrating render and send"
```

---

### Task 8: WebSocket Protocol Message Handling

**Files:**
- Create: `src/printing/services/protocol.py`
- Create: `src/printing/tests/test_protocol.py`

**Step 1: Write the failing tests**

```python
# src/printing/tests/test_protocol.py
import json
import pytest
from printing.services.protocol import (
    build_authenticate_message,
    build_pairing_request_message,
    build_print_status_message,
    parse_server_message,
    MessageType,
    ProtocolError,
)


class TestBuildMessages:
    def test_build_authenticate(self):
        printers = [
            {"id": 1, "name": "Zebra", "status": "online", "templates": ["square-62x62"]}
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

    def test_build_print_status_completed(self):
        msg = build_print_status_message("job-uuid-123", "completed")
        parsed = json.loads(msg)
        assert parsed["type"] == "print_status"
        assert parsed["job_id"] == "job-uuid-123"
        assert parsed["status"] == "completed"
        assert parsed["error"] is None

    def test_build_print_status_failed(self):
        msg = build_print_status_message("job-uuid-123", "failed", "printer offline")
        parsed = json.loads(msg)
        assert parsed["status"] == "failed"
        assert parsed["error"] == "printer offline"


class TestParseMessages:
    def test_parse_auth_result_success(self):
        raw = json.dumps({"type": "auth_result", "success": True, "server_name": "BeaMS"})
        msg = parse_server_message(raw)
        assert msg.type == MessageType.AUTH_RESULT
        assert msg.data["success"] is True
        assert msg.data["server_name"] == "BeaMS"

    def test_parse_auth_result_failure(self):
        raw = json.dumps({"type": "auth_result", "success": False, "server_name": "BeaMS"})
        msg = parse_server_message(raw)
        assert msg.data["success"] is False

    def test_parse_pairing_approved(self):
        raw = json.dumps({
            "type": "pairing_approved",
            "token": "new-token-xyz",
            "server_name": "BeaMS Production",
        })
        msg = parse_server_message(raw)
        assert msg.type == MessageType.PAIRING_APPROVED
        assert msg.data["token"] == "new-token-xyz"

    def test_parse_print_request(self):
        raw = json.dumps({
            "type": "print",
            "job_id": "uuid-123",
            "printer_id": "1",
            "barcode": "BEAMS-A1B2C3D4",
            "asset_name": "Wireless Mic",
            "category_name": "Audio",
            "quantity": 2,
        })
        msg = parse_server_message(raw)
        assert msg.type == MessageType.PRINT
        assert msg.data["barcode"] == "BEAMS-A1B2C3D4"
        assert msg.data["quantity"] == 2

    def test_parse_invalid_json(self):
        with pytest.raises(ProtocolError, match="Invalid JSON"):
            parse_server_message("not json{{{")

    def test_parse_missing_type(self):
        with pytest.raises(ProtocolError, match="Missing 'type'"):
            parse_server_message(json.dumps({"data": "no type field"}))

    def test_parse_unknown_type(self):
        with pytest.raises(ProtocolError, match="Unknown message type"):
            parse_server_message(json.dumps({"type": "unknown_thing"}))

    def test_parse_print_missing_required_fields(self):
        raw = json.dumps({"type": "print", "job_id": "123"})
        with pytest.raises(ProtocolError, match="Missing required field"):
            parse_server_message(raw)
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest printing/tests/test_protocol.py -v`
Expected: ImportError

**Step 3: Implement the protocol module**

```python
# src/printing/services/protocol.py
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


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


PRINT_REQUIRED_FIELDS = ["job_id", "printer_id", "barcode", "asset_name", "category_name"]


def build_authenticate_message(
    token: str, client_name: str, printers: list[dict]
) -> str:
    return json.dumps({
        "type": "authenticate",
        "token": token,
        "client_name": client_name,
        "printers": printers,
    })


def build_pairing_request_message(client_name: str) -> str:
    return json.dumps({
        "type": "pairing_request",
        "client_name": client_name,
    })


def build_print_status_message(
    job_id: str, status: str, error: Optional[str] = None
) -> str:
    return json.dumps({
        "type": "print_status",
        "job_id": job_id,
        "status": status,
        "error": error,
    })


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
                raise ProtocolError(f"Missing required field '{field}' in print message")

    return ServerMessage(type=msg_type, data=data)
```

**Step 4: Run tests to verify they pass**

Run: `cd src && python -m pytest printing/tests/test_protocol.py -v`
Expected: All 11 tests PASS

**Step 5: Commit**

```bash
git add src/printing/services/protocol.py src/printing/tests/test_protocol.py
git commit -m "feat: implement WebSocket protocol message builder and parser"
```

---

### Task 9: WebSocket Client Connection Manager

**Files:**
- Create: `src/printing/services/ws_client.py`
- Create: `src/printing/tests/test_ws_client.py`

**Step 1: Write the failing tests**

```python
# src/printing/tests/test_ws_client.py
import asyncio
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from printing.services.ws_client import PropsWebSocketClient


class TestPropsWebSocketClient:
    def test_init(self):
        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://beams.example.com/ws/print-service/",
            pairing_token="token-123",
            client_name="Test Printer",
        )
        assert client.connection_id == 1
        assert client.server_url == "wss://beams.example.com/ws/print-service/"
        assert client.pairing_token == "token-123"

    def test_backoff_calculation(self):
        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
        )
        assert client._get_backoff_delay(0) == 1
        assert client._get_backoff_delay(1) == 2
        assert client._get_backoff_delay(2) == 4
        assert client._get_backoff_delay(10) == 60  # capped at 60

    @pytest.mark.asyncio
    async def test_build_printer_info(self):
        client = PropsWebSocketClient(
            connection_id=1,
            server_url="wss://example.com/ws/",
            client_name="Test",
        )
        with patch("printing.services.ws_client.Printer") as MockPrinter:
            mock_qs = MagicMock()
            mock_printer = MagicMock()
            mock_printer.pk = 1
            mock_printer.name = "Zebra"
            mock_printer.status = "online"
            mock_printer.default_template = MagicMock()
            mock_printer.default_template.name = "Square"
            mock_qs.filter.return_value.select_related.return_value = [mock_printer]
            MockPrinter.objects = mock_qs
            info = await client._build_printer_info()
            assert len(info) == 1
            assert info[0]["name"] == "Zebra"
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest printing/tests/test_ws_client.py -v`
Expected: ImportError

**Step 3: Implement the WebSocket client**

```python
# src/printing/services/ws_client.py
import asyncio
import json
import logging
from typing import Optional

import websockets

from printing.services.protocol import (
    MessageType,
    ProtocolError,
    build_authenticate_message,
    build_pairing_request_message,
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
        from printing.models import Printer

        printers = Printer.objects.filter(is_active=True).select_related(
            "default_template"
        )
        result = []
        for p in printers:
            templates = []
            if p.default_template:
                templates.append(p.default_template.name)
            result.append({
                "id": str(p.pk),
                "name": p.name,
                "status": p.status,
                "templates": templates,
            })
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
                logger.warning(
                    "Connection %s lost: %s", self.connection_id, e
                )
            except Exception as e:
                logger.error(
                    "Connection %s error: %s", self.connection_id, e
                )

            if not self._running:
                break

            if self.on_status_change:
                await self.on_status_change(self.connection_id, "disconnected")

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
                if self.on_status_change:
                    await self.on_status_change(self.connection_id, "connected")
            else:
                logger.error(
                    "Connection %s authentication failed",
                    self.connection_id,
                )
                if self.on_status_change:
                    await self.on_status_change(self.connection_id, "error")

        elif message.type == MessageType.PAIRING_APPROVED:
            token = message.data["token"]
            self.pairing_token = token
            if self.on_token_received:
                await self.on_token_received(self.connection_id, token)
            logger.info("Connection %s paired successfully", self.connection_id)
            # Reconnect with token
            printer_info = await self._build_printer_info()
            await ws.send(
                build_authenticate_message(token, self.client_name, printer_info)
            )

        elif message.type == MessageType.PAIRING_DENIED:
            logger.error("Connection %s pairing denied", self.connection_id)
            if self.on_status_change:
                await self.on_status_change(self.connection_id, "error")

        elif message.type == MessageType.PRINT:
            job_id = message.data["job_id"]
            try:
                if self.on_print_job:
                    await self.on_print_job(self.connection_id, message.data)
                await ws.send(build_print_status_message(job_id, "completed"))
            except Exception as e:
                logger.error("Print job %s failed: %s", job_id, e)
                await ws.send(
                    build_print_status_message(job_id, "failed", str(e))
                )

    def stop(self):
        self._running = False
```

**Step 4: Run tests to verify they pass**

Run: `cd src && python -m pytest printing/tests/test_ws_client.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add src/printing/services/ws_client.py src/printing/tests/test_ws_client.py
git commit -m "feat: implement WebSocket client with auto-reconnect and pairing flow"
```

---

### Task 10: Management Command - run_print_client

**Files:**
- Create: `src/printing/management/__init__.py`
- Create: `src/printing/management/commands/__init__.py`
- Create: `src/printing/management/commands/run_print_client.py`
- Create: `src/printing/tests/test_management_command.py`

**Step 1: Write the failing tests**

```python
# src/printing/tests/test_management_command.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from django.core.management import call_command
from io import StringIO
from printing.models import PropsConnection


@pytest.mark.django_db
class TestRunPrintClientCommand:
    def test_no_active_connections(self):
        out = StringIO()
        with patch("printing.management.commands.run_print_client.asyncio") as mock_asyncio:
            mock_asyncio.run = MagicMock()
            call_command("run_print_client", stdout=out)
            output = out.getvalue()
            assert "No active connections" in output or mock_asyncio.run.called

    def test_lists_active_connections(self):
        PropsConnection.objects.create(
            name="BeaMS Test",
            server_url="wss://beams.example.com/ws/print-service/",
            pairing_token="test-token",
            is_active=True,
        )
        out = StringIO()
        with patch("printing.management.commands.run_print_client.asyncio") as mock_asyncio:
            mock_asyncio.run = MagicMock()
            call_command("run_print_client", stdout=out)
            output = out.getvalue()
            assert "BeaMS Test" in output
```

**Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest printing/tests/test_management_command.py -v`
Expected: CommandError (command doesn't exist)

**Step 3: Implement the management command**

```python
# src/printing/management/commands/run_print_client.py
import asyncio
import logging

from django.core.management.base import BaseCommand
from django.conf import settings

from printing.models import PropsConnection, Printer, PrintJob, LabelTemplate
from printing.services.ws_client import PropsWebSocketClient
from printing.services.job_processor import process_print_job

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
                f"Starting print client '{client_name}' with {connections.count()} connection(s)..."
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
        conn = await asyncio.to_thread(
            PropsConnection.objects.get, pk=connection_id
        )
        conn.pairing_token = token
        await asyncio.to_thread(
            conn.save, update_fields=["pairing_token"]
        )
        logger.info("Stored pairing token for connection %s", connection_id)

    async def _on_status_change(self, connection_id: int, status: str):
        from django.utils import timezone

        conn = await asyncio.to_thread(
            PropsConnection.objects.get, pk=connection_id
        )
        conn.status = status
        fields = ["status"]
        if status == "connected":
            conn.last_connected_at = timezone.now()
            fields.append("last_connected_at")
        await asyncio.to_thread(conn.save, update_fields=fields)

    async def _on_print_job(self, connection_id: int, data: dict):
        printer_id = data.get("printer_id")
        printer = await asyncio.to_thread(Printer.objects.get, pk=int(printer_id))
        template = printer.default_template
        if not template:
            template = await asyncio.to_thread(
                LabelTemplate.objects.filter(is_default=True).first
            )
        if not template:
            raise Exception("No template available for printer")

        job = await asyncio.to_thread(
            PrintJob.objects.create,
            props_connection_id=connection_id,
            printer=printer,
            template=template,
            barcode=data["barcode"],
            asset_name=data["asset_name"],
            category_name=data["category_name"],
            quantity=data.get("quantity", 1),
        )

        await asyncio.to_thread(process_print_job, job)
```

**Step 4: Run tests to verify they pass**

Run: `cd src && python -m pytest printing/tests/test_management_command.py -v`
Expected: All 2 tests PASS

**Step 5: Verify command shows up**

Run: `cd src && python manage.py help run_print_client`
Expected: Shows help text for the command

**Step 6: Commit**

```bash
git add src/printing/management/ src/printing/tests/test_management_command.py
git commit -m "feat: add run_print_client management command for WebSocket connections"
```

---

### Task 11: Run Full Test Suite and Format Code

**Step 1: Run all tests**

Run: `cd src && python -m pytest printing/tests/ -v --tb=short`
Expected: All tests PASS (approximately 26 tests)

**Step 2: Check coverage**

Run: `cd src && python -m pytest printing/tests/ --cov=printing --cov-report=term-missing`
Review: Check for any untested critical paths

**Step 3: Format and lint**

Run: `cd src && black . && isort . && flake8 printing/ --max-line-length=88`
Expected: No lint errors (or fix any that appear)

**Step 4: Commit formatting fixes if any**

```bash
git add -u
git commit -m "style: format code with black and isort"
```

---

### Task 12: Create Default Square Label Template via Data Migration

**Files:**
- Create: `src/printing/migrations/XXXX_create_default_square_template.py`

**Step 1: Write the data migration**

Run: `cd src && python manage.py makemigrations printing --empty -n create_default_square_template`

Edit the generated migration to create a default square template matching the existing PHP app's layout:

```python
from django.db import migrations


def create_default_template(apps, schema_editor):
    LabelTemplate = apps.get_model("printing", "LabelTemplate")
    LabelElement = apps.get_model("printing", "LabelElement")

    template = LabelTemplate.objects.create(
        name="Square 62x62mm",
        width_mm=62,
        height_mm=62,
        background_color="#FFFFFF",
        is_default=True,
    )

    # Asset name at top, centred
    LabelElement.objects.create(
        template=template,
        element_type="asset_name",
        x_mm=2, y_mm=1, width_mm=58, height_mm=5,
        font_name="helvetica", font_size_pt=7,
        font_bold=True, text_align="center",
        max_chars=20, sort_order=1,
    )

    # QR code centred in middle
    LabelElement.objects.create(
        template=template,
        element_type="qr_code",
        x_mm=6, y_mm=7, width_mm=50, height_mm=50,
        sort_order=2,
    )

    # Barcode text at bottom, centred
    LabelElement.objects.create(
        template=template,
        element_type="barcode_text",
        x_mm=2, y_mm=57, width_mm=58, height_mm=4,
        font_name="courier", font_size_pt=5,
        text_align="center", sort_order=3,
    )


def remove_default_template(apps, schema_editor):
    LabelTemplate = apps.get_model("printing", "LabelTemplate")
    LabelTemplate.objects.filter(name="Square 62x62mm").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("printing", "0002_..."),  # previous migration
    ]

    operations = [
        migrations.RunPython(create_default_template, remove_default_template),
    ]
```

**Step 2: Run the migration**

Run: `cd src && python manage.py migrate`

**Step 3: Verify via Django shell**

Run: `cd src && python manage.py shell -c "from printing.models import LabelTemplate; t = LabelTemplate.objects.get(is_default=True); print(t, t.elements.count())"`
Expected: `Square 62x62mm (62x62mm) 3`

**Step 4: Commit**

```bash
git add src/printing/migrations/
git commit -m "feat: add default square 62x62mm label template via data migration"
```

---

### Task 13: Final Integration Test

**Files:**
- Create: `src/printing/tests/test_integration.py`

**Step 1: Write an integration test for the full flow**

```python
# src/printing/tests/test_integration.py
import pytest
from unittest.mock import patch, MagicMock
from printing.models import (
    LabelTemplate, LabelElement, ElementType, FontChoices, TextAlign,
    Printer, PrintJob, PropsConnection, JobStatus,
)
from printing.services.job_processor import process_print_job


@pytest.mark.django_db
class TestFullPrintFlow:
    def test_end_to_end_print_job(self):
        """Test complete flow: create job -> render PDF -> send to printer."""
        # Setup template
        template = LabelTemplate.objects.create(
            name="Integration Test", width_mm=62, height_mm=62
        )
        LabelElement.objects.create(
            template=template, element_type=ElementType.QR_CODE,
            x_mm=6, y_mm=7, width_mm=50, height_mm=50, sort_order=1
        )
        LabelElement.objects.create(
            template=template, element_type=ElementType.ASSET_NAME,
            x_mm=2, y_mm=1, width_mm=58, height_mm=5,
            font_name=FontChoices.HELVETICA, font_size_pt=7,
            font_bold=True, text_align=TextAlign.CENTER,
            max_chars=20, sort_order=2
        )
        LabelElement.objects.create(
            template=template, element_type=ElementType.BARCODE_TEXT,
            x_mm=2, y_mm=57, width_mm=58, height_mm=4,
            font_name=FontChoices.COURIER, font_size_pt=5,
            text_align=TextAlign.CENTER, sort_order=3
        )

        # Setup printer and connection
        printer = Printer.objects.create(
            name="Test Printer", ip_address="192.168.1.100"
        )
        connection = PropsConnection.objects.create(
            name="Test Server",
            server_url="wss://test.example.com/ws/print-service/",
        )

        # Create job
        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            props_connection=connection,
            barcode="BEAMS-TESTTEST",
            asset_name="Test Microphone",
            category_name="Audio Equipment",
            quantity=2,
        )

        # Process with mocked printer
        with patch("printing.services.job_processor.PrinterService") as MockPS:
            process_print_job(job)

            # Verify PDF was sent to printer
            MockPS.assert_called_once_with("192.168.1.100", 9100)
            send_call = MockPS.return_value.send
            send_call.assert_called_once()
            pdf_data = send_call.call_args[0][0]
            assert pdf_data[:5] == b"%PDF-"

        # Verify job completed
        job.refresh_from_db()
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        assert job.error_message is None
```

**Step 2: Run the integration test**

Run: `cd src && python -m pytest printing/tests/test_integration.py -v`
Expected: PASS

**Step 3: Run full suite one final time**

Run: `cd src && python -m pytest printing/tests/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add src/printing/tests/test_integration.py
git commit -m "test: add end-to-end integration test for print flow"
```

---

## Summary

| Task | Component | Tests | Key Files |
|------|-----------|-------|-----------|
| 1 | Project scaffolding | - | `src/printclient/`, `requirements.txt` |
| 2 | LabelTemplate + LabelElement models | 5 | `src/printing/models.py` |
| 3 | Printer + PropsConnection + PrintJob models | 7 | `src/printing/models.py` |
| 4 | Unfold admin registration | manual | `src/printing/admin.py` |
| 5 | PDF label renderer | 5 | `src/printing/services/label_renderer.py` |
| 6 | Printer TCP service | 4 | `src/printing/services/printer.py` |
| 7 | Print job processor | 4 | `src/printing/services/job_processor.py` |
| 8 | WebSocket protocol | 11 | `src/printing/services/protocol.py` |
| 9 | WebSocket client | 3 | `src/printing/services/ws_client.py` |
| 10 | Management command | 2 | `src/printing/management/commands/run_print_client.py` |
| 11 | Full suite + formatting | - | - |
| 12 | Default template migration | - | `src/printing/migrations/` |
| 13 | Integration test | 1 | `src/printing/tests/test_integration.py` |

**Total: ~42 tests across 13 tasks**
