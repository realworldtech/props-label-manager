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
