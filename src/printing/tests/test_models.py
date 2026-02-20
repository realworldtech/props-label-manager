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
