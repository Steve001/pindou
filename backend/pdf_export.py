import base64
import io
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# Register Chinese font
try:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
except Exception:
    pass

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm


def generate_bead_pdf(
    image_base64: str,
    grid_width: int,
    grid_height: int,
    colors_used: List[dict],
    palette_name: str,
) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    font = "STSong-Light"

    # --- Page 1: Pattern Grid ---
    c.setFont(font, 18)
    c.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN - 10 * mm, f"拼豆图纸 - {palette_name}")

    # Decode and draw image
    img_data = base64.b64decode(image_base64)
    img_buf = io.BytesIO(img_data)
    from reportlab.lib.utils import ImageReader
    img = ImageReader(img_buf)

    # Scale image to fit within page
    img_w, img_h = img.getSize()
    max_w = PAGE_W - 2 * MARGIN
    max_h = PAGE_H - 2 * MARGIN - 30 * mm
    scale = min(max_w / img_w, max_h / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale
    x = (PAGE_W - draw_w) / 2
    y = PAGE_H - MARGIN - 20 * mm - draw_h
    c.drawImage(img, x, y, draw_w, draw_h)

    # Info below image
    c.setFont(font, 10)
    info_y = y - 8 * mm
    total = sum(cu["count"] for cu in colors_used)
    c.drawCentredString(PAGE_W / 2, info_y, f"网格尺寸: {grid_width} x {grid_height}  |  总珠数: {total}  |  颜色数: {len(colors_used)}")

    c.showPage()

    # --- Page 2: Color Legend / Material List ---
    c.setFont(font, 16)
    c.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN - 8 * mm, "颜色图例 & 采购清单")

    # Table header
    table_y = PAGE_H - MARGIN - 22 * mm
    col_x = [MARGIN, MARGIN + 20 * mm, MARGIN + 45 * mm, MARGIN + 100 * mm, PAGE_W - MARGIN - 30 * mm]
    headers = ["色块", "色号", "颜色名称", "所需数量"]
    c.setFont(font, 10)
    c.setFillColor(colors.HexColor("#333333"))
    for i, h in enumerate(headers):
        c.drawString(col_x[i], table_y, h)

    # Divider line
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.line(MARGIN, table_y - 3 * mm, PAGE_W - MARGIN, table_y - 3 * mm)

    # Table rows
    row_h = 7 * mm
    row_y = table_y - 3 * mm - row_h
    c.setFont(font, 9)

    for cu in colors_used:
        if row_y < MARGIN + 15 * mm:
            c.showPage()
            c.setFont(font, 16)
            c.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN - 8 * mm, "颜色图例 & 采购清单 (续)")
            c.setFont(font, 10)
            table_y = PAGE_H - MARGIN - 22 * mm
            c.setFillColor(colors.HexColor("#333333"))
            for i, h in enumerate(headers):
                c.drawString(col_x[i], table_y, h)
            c.setStrokeColor(colors.HexColor("#CCCCCC"))
            c.line(MARGIN, table_y - 3 * mm, PAGE_W - MARGIN, table_y - 3 * mm)
            c.setFont(font, 9)
            row_y = table_y - 3 * mm - row_h

        # Color swatch
        hex_color = cu["hex"]
        c.setFillColor(colors.HexColor(hex_color))
        c.rect(col_x[0], row_y + 1 * mm, 5 * mm, 5 * mm, fill=1, stroke=1)

        # Text
        c.setFillColor(colors.HexColor("#333333"))
        c.drawString(col_x[1], row_y + 1.5 * mm, cu["code"])
        c.drawString(col_x[2], row_y + 1.5 * mm, cu["name"])
        c.drawRightString(col_x[4], row_y + 1.5 * mm, str(cu["count"]))

        # Row separator
        c.setStrokeColor(colors.HexColor("#EEEEEE"))
        c.line(MARGIN, row_y, PAGE_W - MARGIN, row_y)

        row_y -= row_h

    # Total row
    row_y -= 3 * mm
    c.setStrokeColor(colors.HexColor("#333333"))
    c.line(MARGIN, row_y + row_h, PAGE_W - MARGIN, row_y + row_h)
    c.setFont(font, 10)
    c.setFillColor(colors.HexColor("#333333"))
    c.drawString(col_x[0], row_y + 1.5 * mm, "合计")
    c.drawRightString(col_x[4], row_y + 1.5 * mm, str(total))

    c.showPage()
    c.save()
    return buf.getvalue()
