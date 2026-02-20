import tempfile

import barcode
import qrcode
from barcode.writer import ImageWriter
from fpdf import FPDF

from printing.models import ElementType, LabelTemplate

FONT_MAP = {
    "helvetica": "helvetica",
    "courier": "courier",
    "liberation_sans": "helvetica",
    "liberation_mono": "courier",
    "dejavu_sans": "helvetica",
    "dejavu_mono": "courier",
}


class LabelRenderer:
    """Renders a LabelTemplate with asset data to PDF bytes using FPDF2."""

    def __init__(self, template: LabelTemplate):
        self.template = template

    def render(
        self,
        barcode_text: str,
        asset_name: str,
        category_name: str,
        quantity: int = 1,
    ) -> bytes:
        """Render the label template to PDF bytes.

        Args:
            barcode_text: The barcode/identifier string (used for Code128 and QR).
            asset_name: The human-readable asset name.
            category_name: The asset category name.
            quantity: Number of copies of the label to include.

        Returns:
            PDF file content as bytes.
        """
        width = float(self.template.width_mm)
        height = float(self.template.height_mm)
        orientation = "L" if width > height else "P"

        pdf = FPDF(orientation=orientation, unit="mm", format=(width, height))
        pdf.set_auto_page_break(auto=False)

        elements = self.template.elements.all()

        for _ in range(quantity):
            pdf.add_page()
            for element in elements:
                self._render_element(
                    pdf, element, barcode_text, asset_name, category_name
                )

        return bytes(pdf.output())

    def _render_element(self, pdf, element, barcode_text, asset_name, category_name):
        """Dispatch rendering to the appropriate method based on element type."""
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

    def _render_barcode(self, pdf, text, x, y, w, h):
        """Render a Code 128 barcode image onto the PDF."""
        code128 = barcode.get("code128", text, writer=ImageWriter())
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            code128.write(tmp, options={"write_text": False})
            tmp.flush()
            pdf.image(tmp.name, x=x, y=y, w=w, h=h)

    def _render_qr(self, pdf, text, x, y, w, h):
        """Render a QR code image onto the PDF."""
        qr = qrcode.make(text, box_size=10, border=1)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            qr.save(tmp)
            tmp.flush()
            pdf.image(tmp.name, x=x, y=y, w=w, h=h)

    def _render_text(self, pdf, element, text, x, y, w, h):
        """Render a text cell onto the PDF, with optional truncation."""
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

    def _render_logo(self, pdf, x, y, w, h):
        """Render the template logo image onto the PDF, if one exists."""
        if self.template.logo:
            pdf.image(self.template.logo.path, x=x, y=y, w=w, h=h)
