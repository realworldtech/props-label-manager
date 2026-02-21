import json
from decimal import Decimal
from typing import Any

from printing.models import LabelElement, LabelTemplate

FORMAT_VERSION = 1


class TemplateImportError(Exception):
    pass


def _decimal_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def export_template(template: LabelTemplate) -> dict:
    """Serialize a LabelTemplate and its elements to a portable dict."""
    elements = template.elements.all().order_by("sort_order")
    return {
        "format_version": FORMAT_VERSION,
        "template": {
            "name": template.name,
            "width_mm": float(template.width_mm),
            "height_mm": float(template.height_mm),
            "background_color": template.background_color,
        },
        "elements": [
            {
                "element_type": el.element_type,
                "x_mm": float(el.x_mm),
                "y_mm": float(el.y_mm),
                "width_mm": float(el.width_mm),
                "height_mm": float(el.height_mm),
                "rotation": el.rotation,
                "font_name": el.font_name,
                "font_size_pt": float(el.font_size_pt) if el.font_size_pt else None,
                "font_bold": el.font_bold,
                "text_align": el.text_align,
                "max_chars": el.max_chars,
                "static_content": el.static_content,
                "sort_order": el.sort_order,
            }
            for el in elements
        ],
    }


def export_template_json(template: LabelTemplate) -> str:
    """Serialize a LabelTemplate to a JSON string."""
    return json.dumps(export_template(template), indent=2, default=_decimal_default)


def import_template(data: dict) -> LabelTemplate:
    """Create a LabelTemplate and its elements from a portable dict.

    Returns the created template.
    """
    version = data.get("format_version")
    if version != FORMAT_VERSION:
        raise TemplateImportError(
            f"Unsupported format version: {version} (expected {FORMAT_VERSION})"
        )

    tpl_data = data.get("template")
    if not tpl_data:
        raise TemplateImportError("Missing 'template' key in import data")

    required_fields = ["name", "width_mm", "height_mm"]
    for field in required_fields:
        if field not in tpl_data:
            raise TemplateImportError(f"Missing required template field: {field}")

    template = LabelTemplate.objects.create(
        name=tpl_data["name"],
        width_mm=Decimal(str(tpl_data["width_mm"])),
        height_mm=Decimal(str(tpl_data["height_mm"])),
        background_color=tpl_data.get("background_color", "#FFFFFF"),
    )

    element_fields = [
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

    for el_data in data.get("elements", []):
        kwargs = {}
        for field in element_fields:
            if field in el_data:
                value = el_data[field]
                if (
                    field in ("x_mm", "y_mm", "width_mm", "height_mm")
                    and value is not None
                ):
                    value = Decimal(str(value))
                elif field == "font_size_pt" and value is not None:
                    value = Decimal(str(value))
                kwargs[field] = value
        LabelElement.objects.create(template=template, **kwargs)

    return template


def import_template_json(json_str: str) -> LabelTemplate:
    """Create a LabelTemplate from a JSON string."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise TemplateImportError(f"Invalid JSON: {e}")
    return import_template(data)
