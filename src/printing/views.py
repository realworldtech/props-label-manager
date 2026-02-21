import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from printing.models import (
    ElementType,
    FontChoices,
    LabelElement,
    LabelTemplate,
    TextAlign,
)
from printing.services.label_renderer import LabelRenderer
from printing.services.template_io import export_template


@login_required
def designer(request, pk):
    template = get_object_or_404(LabelTemplate, pk=pk)
    template_data = export_template(template)

    context = {
        "template": template,
        "template_json": json.dumps(template_data),
        "element_type_choices": ElementType.choices,
        "font_choices": FontChoices.choices,
        "text_align_choices": TextAlign.choices,
    }
    return render(request, "printing/designer.html", context)


@login_required
@require_POST
def designer_save(request, pk):
    template = get_object_or_404(LabelTemplate, pk=pk)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    tpl_data = data.get("template", {})
    elements_data = data.get("elements", [])

    try:
        with transaction.atomic():
            if "name" in tpl_data:
                template.name = tpl_data["name"]
            if "width_mm" in tpl_data:
                template.width_mm = Decimal(str(tpl_data["width_mm"]))
            if "height_mm" in tpl_data:
                template.height_mm = Decimal(str(tpl_data["height_mm"]))
            if "background_color" in tpl_data:
                template.background_color = tpl_data["background_color"]
            template.save()

            template.elements.all().delete()

            for i, el_data in enumerate(elements_data):
                LabelElement.objects.create(
                    template=template,
                    element_type=el_data.get("element_type", ElementType.STATIC_TEXT),
                    x_mm=Decimal(str(el_data.get("x_mm", 0))),
                    y_mm=Decimal(str(el_data.get("y_mm", 0))),
                    width_mm=Decimal(str(el_data.get("width_mm", 10))),
                    height_mm=Decimal(str(el_data.get("height_mm", 5))),
                    rotation=el_data.get("rotation", 0),
                    font_name=el_data.get("font_name") or None,
                    font_size_pt=(
                        Decimal(str(el_data["font_size_pt"]))
                        if el_data.get("font_size_pt")
                        else None
                    ),
                    font_bold=el_data.get("font_bold", False),
                    text_align=el_data.get("text_align", TextAlign.LEFT),
                    max_chars=el_data.get("max_chars") or None,
                    static_content=el_data.get("static_content") or None,
                    sort_order=el_data.get("sort_order", i),
                )
    except (InvalidOperation, ValueError, KeyError) as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"status": "ok"})


@login_required
def designer_preview(request, pk):
    template = get_object_or_404(LabelTemplate, pk=pk)
    renderer = LabelRenderer(template)
    pdf_bytes = renderer.render(
        barcode_text="SAMPLE-001",
        asset_name="Sample Asset",
        category_name="Sample Category",
        department_name="Sample Department",
        site_short_name="HQ",
    )
    return HttpResponse(pdf_bytes, content_type="application/pdf")
