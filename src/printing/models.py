from django.core.exceptions import ValidationError
from django.db import models


class FontChoices(models.TextChoices):
    HELVETICA = "helvetica", "Helvetica"
    COURIER = "courier", "Courier"
    LIBERATION_SANS = "liberation_sans", "Liberation Sans"
    LIBERATION_MONO = "liberation_mono", "Liberation Mono"
    DEJAVU_SANS = "dejavu_sans", "DejaVu Sans"
    DEJAVU_MONO = "dejavu_mono", "DejaVu Sans Mono"


class LabelType(models.TextChoices):
    ASSET = "asset", "Asset"
    LOCATION = "location", "Location"


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
    LOCATION_NAME = "location_name", "Location Name"
    LOCATION_DESCRIPTION = "location_description", "Location Description"
    LOCATION_CATEGORIES = "location_categories", "Location Categories"
    LOCATION_DEPARTMENTS = "location_departments", "Location Departments"


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
            LabelTemplate.objects.filter(is_default=True).exclude(pk=self.pk).update(
                is_default=False
            )
        super().save(*args, **kwargs)


class LabelElement(models.Model):
    template = models.ForeignKey(
        LabelTemplate, on_delete=models.CASCADE, related_name="elements"
    )
    element_type = models.CharField(max_length=30, choices=ElementType.choices)
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


class ConnectionStatus(models.TextChoices):
    DISCONNECTED = "disconnected", "Disconnected"
    CONNECTING = "connecting", "Connecting"
    CONNECTED = "connected", "Connected"
    PAIRING = "pairing", "Pairing"
    ERROR = "error", "Error"


class PrinterType(models.TextChoices):
    TCP = "tcp", "TCP (Network Printer)"
    CUPS = "cups", "CUPS (System Printer)"
    VIRTUAL = "virtual", "Virtual (Save PDF)"


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
    WS_PATH = "/ws/print-service/"

    name = models.CharField(max_length=100)
    server_url = models.CharField(
        max_length=200,
        help_text="PROPS server hostname or URL (e.g. props.example.com)",
    )
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

    def clean(self):
        from urllib.parse import urlparse

        url = self.server_url.strip()

        # Already a valid ws/wss URL with the right path
        if url.startswith(("ws://", "wss://")):
            if url.endswith(self.WS_PATH):
                self.server_url = url
                return

        # Has a scheme — extract host:port
        if "://" in url:
            parsed = urlparse(url)
            scheme = "ws" if parsed.scheme == "http" else "wss"
            host = parsed.hostname or ""
            port = f":{parsed.port}" if parsed.port else ""
        else:
            # Bare hostname (or hostname:port)
            scheme = "wss"
            host = url.split("/")[0].split(":")[0]
            port_part = url.split("/")[0].split(":")
            port = f":{port_part[1]}" if len(port_part) > 1 else ""

        self.server_url = f"{scheme}://{host}{port}{self.WS_PATH}"

    @property
    def is_paired(self):
        return bool(self.pairing_token)


class Printer(models.Model):
    name = models.CharField(max_length=100)
    printer_type = models.CharField(
        max_length=20,
        choices=PrinterType.choices,
        default=PrinterType.TCP,
    )
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    port = models.IntegerField(default=9100)
    cups_queue = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="CUPS queue name — must match PRINTER_NAME in dymolp-docker "
        "(e.g. DYMO-5XL)",
    )
    cups_server = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="CUPS server address (e.g. dymo-5xl:631). "
        "Auto-populated by Docker discovery.",
    )
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

    def clean(self):
        if self.printer_type == PrinterType.TCP and not self.ip_address:
            raise ValidationError(
                {"ip_address": "IP address is required for TCP printers."}
            )
        if self.printer_type == PrinterType.CUPS and not self.cups_queue:
            raise ValidationError(
                {"cups_queue": "CUPS queue name is required for CUPS printers."}
            )

    def __str__(self):
        if self.printer_type == PrinterType.VIRTUAL:
            return f"{self.name} (Virtual)"
        if self.printer_type == PrinterType.CUPS:
            server = f" @ {self.cups_server}" if self.cups_server else ""
            return f"{self.name} (CUPS: {self.cups_queue}{server})"
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
    label_type = models.CharField(
        max_length=20, choices=LabelType.choices, default=LabelType.ASSET
    )
    barcode = models.CharField(max_length=100, blank=True, default="")
    asset_name = models.CharField(max_length=200, blank=True, default="")
    category_name = models.CharField(max_length=200, blank=True, default="")
    department_name = models.CharField(max_length=200, blank=True, default="")
    site_short_name = models.CharField(max_length=50, blank=True, default="")
    location_name = models.CharField(max_length=200, blank=True, default="")
    location_description = models.TextField(blank=True, default="")
    location_categories = models.TextField(blank=True, default="")
    location_departments = models.TextField(blank=True, default="")
    qr_content = models.URLField(
        blank=True,
        null=True,
        help_text="URL to encode in QR code. If blank, uses the barcode string.",
    )
    quantity = models.IntegerField(default=1)
    output_file = models.FileField(
        upload_to="labels/",
        blank=True,
        null=True,
        help_text="PDF output file (populated for virtual printer jobs).",
    )
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.barcode} - {self.status}"
