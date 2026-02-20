from decimal import Decimal

import pytest

from printing.models import (
    ElementType,
    FontChoices,
    LabelElement,
    LabelTemplate,
    TextAlign,
)
from printing.services.label_renderer import LabelRenderer


@pytest.mark.django_db
class TestLabelRenderer:
    def _create_template_with_elements(self):
        """Helper: creates a square template with QR, name, and barcode text."""
        template = LabelTemplate.objects.create(
            name="Square 62x62mm", width_mm=62, height_mm=62
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.QR_CODE,
            x_mm=6,
            y_mm=6,
            width_mm=50,
            height_mm=50,
            sort_order=1,
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.ASSET_NAME,
            x_mm=2,
            y_mm=2,
            width_mm=58,
            height_mm=5,
            font_name=FontChoices.HELVETICA,
            font_size_pt=8,
            font_bold=True,
            text_align=TextAlign.CENTER,
            max_chars=20,
            sort_order=2,
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.BARCODE_TEXT,
            x_mm=2,
            y_mm=57,
            width_mm=58,
            height_mm=4,
            font_name=FontChoices.COURIER,
            font_size_pt=6,
            text_align=TextAlign.CENTER,
            sort_order=3,
        )
        return template

    def test_render_returns_pdf_bytes(self):
        template = self._create_template_with_elements()
        renderer = LabelRenderer(template)
        pdf_bytes = renderer.render(
            barcode_text="BEAMS-A1B2C3D4",
            asset_name="Wireless Microphone",
            category_name="Audio Equipment",
        )
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_render_with_quantity(self):
        template = self._create_template_with_elements()
        renderer = LabelRenderer(template)
        pdf_bytes = renderer.render(
            barcode_text="BEAMS-A1B2C3D4",
            asset_name="Test Asset",
            category_name="Test Category",
            quantity=3,
        )
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_render_truncates_long_name(self):
        template = self._create_template_with_elements()
        renderer = LabelRenderer(template)
        pdf_bytes = renderer.render(
            barcode_text="BEAMS-12345678",
            asset_name="This Is An Extremely Long Asset Name That Exceeds Max Chars",
            category_name="Category",
        )
        assert isinstance(pdf_bytes, bytes)

    def test_render_with_barcode_element(self):
        template = LabelTemplate.objects.create(
            name="With Barcode", width_mm=62, height_mm=29
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.BARCODE_128,
            x_mm=2,
            y_mm=5,
            width_mm=40,
            height_mm=15,
            sort_order=1,
        )
        renderer = LabelRenderer(template)
        pdf_bytes = renderer.render(
            barcode_text="BEAMS-DEADBEEF",
            asset_name="Test",
            category_name="Test",
        )
        assert pdf_bytes[:5] == b"%PDF-"

    def test_render_with_static_text(self):
        template = LabelTemplate.objects.create(
            name="With Static", width_mm=62, height_mm=62
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.STATIC_TEXT,
            x_mm=2,
            y_mm=55,
            width_mm=58,
            height_mm=5,
            font_name=FontChoices.HELVETICA,
            font_size_pt=6,
            static_content="Property of BeaMS",
            text_align=TextAlign.CENTER,
            sort_order=1,
        )
        renderer = LabelRenderer(template)
        pdf_bytes = renderer.render(
            barcode_text="BEAMS-12345678",
            asset_name="Test",
            category_name="Test",
        )
        assert pdf_bytes[:5] == b"%PDF-"

    def test_render_with_category_name(self):
        template = LabelTemplate.objects.create(
            name="With Category", width_mm=62, height_mm=62
        )
        LabelElement.objects.create(
            template=template,
            element_type=ElementType.CATEGORY_NAME,
            x_mm=2,
            y_mm=55,
            width_mm=58,
            height_mm=5,
            font_name=FontChoices.HELVETICA,
            font_size_pt=6,
            text_align=TextAlign.CENTER,
            sort_order=1,
        )
        renderer = LabelRenderer(template)
        pdf_bytes = renderer.render(
            barcode_text="BEAMS-12345678",
            asset_name="Test",
            category_name="Audio Equipment",
        )
        assert pdf_bytes[:5] == b"%PDF-"
