import json

from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.contrib.filters.admin import ChoicesDropdownFilter
from unfold.decorators import action, display

from printing.models import (
    LabelElement,
    LabelTemplate,
    Printer,
    PrinterType,
    PrintJob,
    PropsConnection,
)


class LabelElementInline(StackedInline):
    model = LabelElement
    extra = 0
    tab = True
    fieldsets = (
        (
            None,
            {
                "fields": (
                    ("element_type", "sort_order"),
                    ("x_mm", "y_mm", "width_mm", "height_mm"),
                    "rotation",
                ),
            },
        ),
        (
            "Text Options",
            {
                "fields": (
                    ("font_name", "font_size_pt"),
                    ("font_bold", "text_align"),
                    "max_chars",
                    "static_content",
                ),
                "classes": ["collapse"],
            },
        ),
    )


@admin.register(LabelTemplate)
class LabelTemplateAdmin(ModelAdmin):
    actions = ["export_templates"]
    actions_detail = ["export_single_template", "open_designer"]
    list_display = [
        "name",
        "display_dimensions",
        "display_default",
        "display_element_count",
        "display_designer_link",
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

    @admin.action(description="Export selected templates as JSON")
    def export_templates(self, request, queryset):
        from printing.services.template_io import export_template

        if queryset.count() == 1:
            template = queryset.first()
            data = export_template(template)
            response = HttpResponse(
                json.dumps(data, indent=2),
                content_type="application/json",
            )
            slug = template.name.lower().replace(" ", "_")
            response["Content-Disposition"] = (
                f'attachment; filename="{slug}.label.json"'
            )
            return response

        templates = [export_template(t) for t in queryset]
        response = HttpResponse(
            json.dumps(templates, indent=2),
            content_type="application/json",
        )
        response["Content-Disposition"] = 'attachment; filename="label_templates.json"'
        return response

    @action(description="Export as JSON", url_path="export-json")
    def export_single_template(self, request, object_id):
        from printing.services.template_io import export_template

        template = self.get_object(request, object_id)
        data = export_template(template)
        response = HttpResponse(
            json.dumps(data, indent=2),
            content_type="application/json",
        )
        slug = template.name.lower().replace(" ", "_")
        response["Content-Disposition"] = f'attachment; filename="{slug}.label.json"'
        return response

    @display(description="Dimensions")
    def display_dimensions(self, obj):
        return f"{obj.width_mm} x {obj.height_mm} mm"

    @display(description="Default", boolean=True)
    def display_default(self, obj):
        return obj.is_default

    @display(description="Elements")
    def display_element_count(self, obj):
        return obj.elements.count()

    @action(description="Open Designer", url_path="designer")
    def open_designer(self, request, object_id):
        url = reverse("label-designer", kwargs={"pk": object_id})
        return redirect(url)

    @display(description="Designer")
    def display_designer_link(self, obj):
        url = reverse("label-designer", kwargs={"pk": obj.pk})
        return format_html('<a href="{}">Design</a>', url)


@admin.register(Printer)
class PrinterAdmin(ModelAdmin):
    actions_detail = ["send_test_print"]
    list_display = [
        "name",
        "printer_type",
        "display_address",
        "display_status",
        "display_active",
    ]
    list_filter = [("status", ChoicesDropdownFilter), "is_active", "printer_type"]
    search_fields = ["name", "ip_address", "cups_queue"]
    readonly_fields = ["cups_server"]
    autocomplete_fields = ["default_template"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "printer_type",
                    "ip_address",
                    "port",
                    "cups_queue",
                    "cups_server",
                    "is_active",
                    "default_template",
                )
            },
        ),
        ("Status", {"fields": ("status",), "classes": ["tab"]}),
    )

    @action(description="Send Test Print", url_path="test-print")
    def send_test_print(self, request, object_id):
        from printing.services.job_processor import process_print_job

        printer = self.get_object(request, object_id)

        template = printer.default_template
        if template is None:
            template = LabelTemplate.objects.filter(is_default=True).first()
        if template is None:
            template = LabelTemplate.objects.first()
        if template is None:
            messages.error(
                request,
                "Cannot send test print: no label templates exist.",
            )
            return redirect(reverse("admin:printing_printer_change", args=[object_id]))

        job = PrintJob.objects.create(
            printer=printer,
            template=template,
            barcode="TEST-001",
            asset_name="Test Print",
            category_name="Test Category",
            department_name="Test Department",
            site_short_name="TST",
        )

        process_print_job(job)
        job.refresh_from_db()

        if job.status == "completed":
            messages.success(request, "Test print completed successfully.")
        else:
            messages.error(
                request,
                f"Test print failed: {job.error_message or 'Unknown error'}",
            )

        return redirect(reverse("admin:printing_printjob_change", args=[job.pk]))

    @display(description="Address")
    def display_address(self, obj):
        if obj.printer_type == PrinterType.CUPS:
            server = f" @ {obj.cups_server}" if obj.cups_server else ""
            return f"{obj.cups_queue}{server}" if obj.cups_queue else "-"
        if obj.printer_type == PrinterType.VIRTUAL:
            return "Virtual"
        if obj.ip_address:
            return f"{obj.ip_address}:{obj.port}"
        return "-"

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
        "label_type",
        "display_status",
        "printer",
        "props_connection",
        "display_output_file",
        "created_at",
    ]
    list_filter = [
        ("status", ChoicesDropdownFilter),
        ("label_type", ChoicesDropdownFilter),
    ]
    list_filter_submit = True
    search_fields = ["barcode", "asset_name", "category_name"]
    readonly_fields = ["created_at", "completed_at"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "label_type",
                    "barcode",
                    "asset_name",
                    "category_name",
                    "qr_content",
                    "quantity",
                )
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "location_name",
                    "location_description",
                    "location_categories",
                    "location_departments",
                ),
                "classes": ["tab"],
            },
        ),
        ("Routing", {"fields": ("printer", "template", "props_connection")}),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "error_message",
                    "output_file",
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

    @display(description="PDF")
    def display_output_file(self, obj):
        if obj.output_file:
            return format_html(
                '<a href="{}" target="_blank">View</a>', obj.output_file.url
            )
        return "-"
