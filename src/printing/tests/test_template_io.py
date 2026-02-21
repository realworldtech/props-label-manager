import json

import pytest

from printing.models import (
    ElementType,
    FontChoices,
    LabelElement,
    LabelTemplate,
    TextAlign,
)
from printing.services.template_io import (
    FORMAT_VERSION,
    TemplateImportError,
    export_template,
    export_template_json,
    import_template,
    import_template_json,
)


@pytest.mark.django_db
class TestExportTemplate:
    def _make_template(self):
        template = LabelTemplate.objects.create(
            name="Test Label", width_mm=62, height_mm=25, background_color="#F0F0F0"
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.BARCODE_TEXT,
            x_mm=2,
            y_mm=18,
            width_mm=58,
            height_mm=5,
            font_name=FontChoices.COURIER,
            font_size_pt=8,
            text_align=TextAlign.CENTER,
            sort_order=1,
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.ASSET_NAME,
            x_mm=2,
            y_mm=2,
            width_mm=58,
            height_mm=10,
            font_name=FontChoices.HELVETICA,
            font_size_pt=12,
            font_bold=True,
            text_align=TextAlign.LEFT,
            max_chars=30,
            sort_order=0,
        )
        return template

    def test_export_has_format_version(self):
        template = self._make_template()
        data = export_template(template)
        assert data["format_version"] == FORMAT_VERSION

    def test_export_template_fields(self):
        template = self._make_template()
        data = export_template(template)
        tpl = data["template"]
        assert tpl["name"] == "Test Label"
        assert tpl["width_mm"] == 62.0
        assert tpl["height_mm"] == 25.0
        assert tpl["background_color"] == "#F0F0F0"

    def test_export_elements_sorted(self):
        template = self._make_template()
        data = export_template(template)
        elements = data["elements"]
        assert len(elements) == 2
        assert elements[0]["sort_order"] == 0
        assert elements[1]["sort_order"] == 1

    def test_export_element_fields(self):
        template = self._make_template()
        data = export_template(template)
        el = data["elements"][1]  # barcode_text at sort_order=1
        assert el["element_type"] == "barcode_text"
        assert el["x_mm"] == 2.0
        assert el["font_name"] == "courier"
        assert el["font_size_pt"] == 8.0
        assert el["text_align"] == "center"

    def test_export_json_is_valid_json(self):
        template = self._make_template()
        json_str = export_template_json(template)
        data = json.loads(json_str)
        assert data["format_version"] == FORMAT_VERSION

    def test_export_excludes_logo_and_is_default(self):
        template = self._make_template()
        data = export_template(template)
        assert "logo" not in data["template"]
        assert "is_default" not in data["template"]


@pytest.mark.django_db
class TestImportTemplate:
    def _make_export_data(self):
        return {
            "format_version": FORMAT_VERSION,
            "template": {
                "name": "Imported Label",
                "width_mm": 50.0,
                "height_mm": 30.0,
                "background_color": "#FFFFFF",
            },
            "elements": [
                {
                    "element_type": "barcode_128",
                    "x_mm": 5.0,
                    "y_mm": 5.0,
                    "width_mm": 40.0,
                    "height_mm": 15.0,
                    "rotation": 0,
                    "font_name": None,
                    "font_size_pt": None,
                    "font_bold": False,
                    "text_align": "left",
                    "max_chars": None,
                    "static_content": None,
                    "sort_order": 0,
                },
                {
                    "element_type": "asset_name",
                    "x_mm": 5.0,
                    "y_mm": 22.0,
                    "width_mm": 40.0,
                    "height_mm": 6.0,
                    "rotation": 0,
                    "font_name": "helvetica",
                    "font_size_pt": 10.0,
                    "font_bold": True,
                    "text_align": "center",
                    "max_chars": 20,
                    "static_content": None,
                    "sort_order": 1,
                },
            ],
        }

    def test_import_creates_template(self):
        data = self._make_export_data()
        template = import_template(data)
        assert template.pk is not None
        assert template.name == "Imported Label"
        assert float(template.width_mm) == 50.0
        assert float(template.height_mm) == 30.0

    def test_import_creates_elements(self):
        data = self._make_export_data()
        template = import_template(data)
        elements = template.elements.all().order_by("sort_order")
        assert len(elements) == 2
        assert elements[0].element_type == "barcode_128"
        assert elements[1].element_type == "asset_name"
        assert elements[1].font_bold is True
        assert elements[1].max_chars == 20

    def test_import_rejects_wrong_version(self):
        data = self._make_export_data()
        data["format_version"] = 999
        with pytest.raises(TemplateImportError, match="Unsupported format version"):
            import_template(data)

    def test_import_rejects_missing_template(self):
        data = {"format_version": FORMAT_VERSION}
        with pytest.raises(TemplateImportError, match="Missing 'template' key"):
            import_template(data)

    def test_import_rejects_missing_name(self):
        data = {
            "format_version": FORMAT_VERSION,
            "template": {"width_mm": 50, "height_mm": 30},
        }
        with pytest.raises(TemplateImportError, match="Missing required.*name"):
            import_template(data)

    def test_import_json_string(self):
        data = self._make_export_data()
        json_str = json.dumps(data)
        template = import_template_json(json_str)
        assert template.name == "Imported Label"

    def test_import_json_invalid(self):
        with pytest.raises(TemplateImportError, match="Invalid JSON"):
            import_template_json("{bad json")


@pytest.mark.django_db
class TestRoundTrip:
    def test_export_then_import_produces_equivalent_template(self):
        original = LabelTemplate.objects.create(
            name="Round Trip", width_mm=62, height_mm=25
        )
        LabelElement.objects.create(
            template=original,
            element_type=ElementType.QR_CODE,
            x_mm=1,
            y_mm=1,
            width_mm=23,
            height_mm=23,
            sort_order=0,
        )
        LabelElement.objects.create(
            template=original,
            element_type=ElementType.STATIC_TEXT,
            x_mm=26,
            y_mm=10,
            width_mm=34,
            height_mm=5,
            font_name=FontChoices.DEJAVU_SANS,
            font_size_pt=9,
            static_content="Hello World",
            sort_order=1,
        )

        exported = export_template(original)
        imported = import_template(exported)

        assert imported.name == original.name
        assert float(imported.width_mm) == float(original.width_mm)
        assert float(imported.height_mm) == float(original.height_mm)

        orig_elements = list(original.elements.all().order_by("sort_order"))
        new_elements = list(imported.elements.all().order_by("sort_order"))
        assert len(new_elements) == len(orig_elements)

        for orig, new in zip(orig_elements, new_elements):
            assert new.element_type == orig.element_type
            assert float(new.x_mm) == float(orig.x_mm)
            assert float(new.y_mm) == float(orig.y_mm)
            assert float(new.width_mm) == float(orig.width_mm)
            assert float(new.height_mm) == float(orig.height_mm)
            assert new.font_name == orig.font_name
            assert new.static_content == orig.static_content
