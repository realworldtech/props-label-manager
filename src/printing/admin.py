from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import ChoicesDropdownFilter
from unfold.decorators import display

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
    list_display = [
        "name",
        "display_dimensions",
        "display_default",
        "display_element_count",
    ]
    list_filter = ["is_default"]
    search_fields = ["name"]
    inlines = [LabelElementInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "width_mm",
                    "height_mm",
                    "background_color",
                    "logo",
                    "is_default",
                )
            },
        ),
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
    list_display = [
        "name",
        "ip_address",
        "port",
        "display_status",
        "display_active",
    ]
    list_filter = [("status", ChoicesDropdownFilter), "is_active"]
    search_fields = ["name", "ip_address"]
    autocomplete_fields = ["default_template"]
    fieldsets = (
        (
            None,
            {"fields": ("name", "ip_address", "port", "is_active", "default_template")},
        ),
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
    list_display = [
        "name",
        "server_url",
        "display_status",
        "display_paired",
        "last_connected_at",
    ]
    list_filter = [("status", ChoicesDropdownFilter), "is_active"]
    search_fields = ["name", "server_url"]
    readonly_fields = ["status", "last_connected_at", "last_error", "pairing_token"]
    fieldsets = (
        (None, {"fields": ("name", "server_url", "is_active")}),
        (
            "Connection Status",
            {
                "fields": (
                    "status",
                    "pairing_token",
                    "last_connected_at",
                    "last_error",
                ),
                "classes": ["tab"],
            },
        ),
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
    list_display = [
        "barcode",
        "asset_name",
        "display_status",
        "printer",
        "props_connection",
        "created_at",
    ]
    list_filter = [
        ("status", ChoicesDropdownFilter),
    ]
    list_filter_submit = True
    search_fields = ["barcode", "asset_name", "category_name"]
    readonly_fields = ["created_at", "completed_at"]
    fieldsets = (
        (None, {"fields": ("barcode", "asset_name", "category_name", "quantity")}),
        ("Routing", {"fields": ("printer", "template", "props_connection")}),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "error_message",
                    "created_at",
                    "completed_at",
                ),
                "classes": ["tab"],
            },
        ),
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
