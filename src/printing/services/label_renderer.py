import io
import tempfile

import barcode
import qrcode
from barcode.writer import ImageWriter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from printing.models import ElementType, LabelTemplate

FONT_MAP = {
    "helvetica": "Helvetica",
    "courier": "Courier",
    "liberation_sans": "Helvetica",
    "liberation_mono": "Courier",
    "dejavu_sans": "Helvetica",
    "dejavu_mono": "Courier",
}


class LabelRenderer:
    """Renders a LabelTemplate with asset data to PDF bytes using ReportLab."""

    def __init__(self, template: LabelTemplate):
        self.template = template

    def render(
        self,
        barcode_text: str,
        asset_name: str,
        category_name: str,
        qr_content: str = "",
        quantity: int = 1,
    ) -> bytes:
        width = float(self.template.width_mm) * mm
        height = float(self.template.height_mm) * mm
        qr_data = qr_content or barcode_text

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(width, height))

        elements = self.template.elements.all()

        for i in range(quantity):
            if i > 0:
                c.showPage()
            for element in elements:
                self._render_element(
                    c, height, element, barcode_text, asset_name, category_name, qr_data
                )

        c.save()
        return buf.getvalue()

    def _render_element(
        self, c, page_height, element, barcode_text, asset_name, category_name, qr_data
    ):
        x = float(element.x_mm) * mm
        y = float(element.y_mm) * mm
        w = float(element.width_mm) * mm
        h = float(element.height_mm) * mm

        # ReportLab origin is bottom-left; convert from top-left coordinates
        rl_y = page_height - y - h

        if element.element_type == ElementType.BARCODE_128:
            self._render_barcode(c, barcode_text, x, rl_y, w, h)
        elif element.element_type == ElementType.QR_CODE:
            self._render_qr(c, qr_data, x, rl_y, w, h)
        elif element.element_type == ElementType.ASSET_NAME:
            self._render_text(c, element, asset_name, x, rl_y, w, h)
        elif element.element_type == ElementType.CATEGORY_NAME:
            self._render_text(c, element, category_name, x, rl_y, w, h)
        elif element.element_type == ElementType.BARCODE_TEXT:
            self._render_text(c, element, barcode_text, x, rl_y, w, h)
        elif element.element_type == ElementType.LOGO:
            self._render_logo(c, x, rl_y, w, h)
        elif element.element_type == ElementType.STATIC_TEXT:
            self._render_text(c, element, element.static_content or "", x, rl_y, w, h)

    def _render_barcode(self, c, text, x, y, w, h):
        code128 = barcode.get("code128", text, writer=ImageWriter())
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            code128.write(tmp, options={"write_text": False})
            tmp.flush()
            c.drawImage(tmp.name, x, y, width=w, height=h)

    def _render_qr(self, c, text, x, y, w, h):
        qr = qrcode.make(text, box_size=10, border=1)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            qr.save(tmp)
            tmp.flush()
            c.drawImage(tmp.name, x, y, width=w, height=h)

    def _render_text(self, c, element, text, x, y, w, h):
        if element.max_chars and len(text) > element.max_chars:
            text = text[: element.max_chars]

        font_name = FONT_MAP.get(element.font_name, "Helvetica")
        if element.font_bold:
            font_name += "-Bold"
        size = float(element.font_size_pt) if element.font_size_pt else 10

        c.setFont(font_name, size)

        # Position text vertically centered in the element box
        text_y = y + (h - size) / 2

        if element.text_align == "center":
            c.drawCentredString(x + w / 2, text_y, text)
        elif element.text_align == "right":
            c.drawRightString(x + w, text_y, text)
        else:
            c.drawString(x, text_y, text)

    def _render_logo(self, c, x, y, w, h):
        if self.template.logo:
            c.drawImage(self.template.logo.path, x, y, width=w, height=h)
