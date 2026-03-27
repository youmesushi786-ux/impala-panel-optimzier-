import io
import logging
from typing import List

from app.schemas import (
    BOQSummary,
    BoardLayout,
    CuttingRequest,
    EdgingSummary,
    OptimizationSummary,
    StockImpactItem,
    StickerLabel,
)

logger = logging.getLogger("panelpro.pdf")

_HAS_REPORTLAB = False
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas

    _HAS_REPORTLAB = True
except ImportError:
    logger.info("reportlab not installed - PDF output will be minimal plain-text")


# ------------------------------------------------------------------ #
#  Report PDF                                                         #
# ------------------------------------------------------------------ #

def generate_report_pdf(
    request: CuttingRequest,
    layouts: List[BoardLayout],
    optimization: OptimizationSummary,
    edging: EdgingSummary,
    boq: BOQSummary,
    stickers: List[StickerLabel],
    stock_impact: List[StockImpactItem],
    report_id: str,
) -> bytes:
    if _HAS_REPORTLAB:
        return _report_reportlab(
            request, layouts, optimization, edging, boq,
            stickers, stock_impact, report_id,
        )
    return _report_fallback(request, optimization, edging, report_id)


def _report_reportlab(
    request, layouts, optimization, edging, boq,
    stickers, stock_impact, report_id,
) -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 50

    def _check(needed=60):
        nonlocal y
        if y < needed:
            c.showPage()
            y = h - 50

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, "PanelPro Cutting Report")
    y -= 30

    c.setFont("Helvetica", 11)
    for line in [
        f"Report ID: {report_id}",
        f"Project:   {request.project_name}",
        f"Customer:  {request.customer_name}",
        "",
        f"Boards used:      {optimization.total_boards}",
        f"Panels cut:       {optimization.total_panels}",
        f"Efficiency:       {optimization.overall_efficiency_percent:.1f}%",
        f"Total waste:      {optimization.total_waste_percent:.1f}%",
        f"Total edging:     {edging.total_meters:.2f} m",
    ]:
        c.drawString(50, y, line)
        y -= 16

    y -= 10
    for layout in layouts:
        _check(100)
        mat = layout.material or {}
        btype = mat.get("board_type", "")
        color = mat.get("color_name", "")

        c.setFont("Helvetica-Bold", 12)
        c.drawString(
            50, y,
            f"Board {layout.board_number}  "
            f"({layout.board_width:.0f} x {layout.board_length:.0f} mm)  "
            f"{btype} {color}",
        )
        y -= 16
        c.setFont("Helvetica", 10)
        c.drawString(
            70, y,
            f"Panels: {layout.panel_count}   "
            f"Efficiency: {layout.efficiency_percent:.1f}%   "
            f"Waste: {layout.waste_area_mm2:.0f} mm2",
        )
        y -= 14
        for p in layout.panels:
            _check()
            rot = " [rotated]" if p.rotated else ""
            c.drawString(
                90, y,
                f"- {p.label}: {p.width:.0f} x {p.length:.0f} mm  "
                f"@ ({p.x:.0f},{p.y:.0f}){rot}",
            )
            y -= 13
        y -= 6

    if boq and boq.pricing:
        _check(120)
        y -= 6
        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, y, "Pricing")
        y -= 18
        c.setFont("Helvetica", 11)
        for ln in boq.pricing.lines:
            c.drawString(50, y, f"{ln.item}: {ln.description}  =  {ln.amount:.2f}")
            y -= 16
        y -= 4
        c.drawString(50, y, f"Subtotal: {boq.pricing.subtotal:.2f}")
        y -= 16
        c.drawString(50, y, f"Tax:      {boq.pricing.tax:.2f}")
        y -= 16
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"TOTAL:    {boq.pricing.total:.2f}")

    c.save()
    buf.seek(0)
    return buf.read()


def _report_fallback(request, optimization, edging, report_id) -> bytes:
    lines = "\n".join([
        "PanelPro Cutting Report",
        f"Report: {report_id}",
        f"Project: {request.project_name}",
        f"Customer: {request.customer_name}",
        f"Boards: {optimization.total_boards}",
        f"Panels: {optimization.total_panels}",
        f"Efficiency: {optimization.overall_efficiency_percent:.1f}%",
        f"Edging: {edging.total_meters:.2f} m",
    ])
    return _text_to_minimal_pdf(lines)


# ------------------------------------------------------------------ #
#  Labels PDF                                                         #
# ------------------------------------------------------------------ #

def generate_labels_pdf(stickers: List[StickerLabel]) -> bytes:
    if _HAS_REPORTLAB:
        return _labels_reportlab(stickers)
    return _labels_fallback(stickers)


def _labels_reportlab(stickers) -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    label_w, label_h = 250, 90
    margin_x, margin_y = 50, 50
    col_gap, row_gap = 20, 15
    cols = 2
    x_positions = [margin_x, margin_x + label_w + col_gap]

    row = col = 0
    for sticker in stickers:
        x = x_positions[col]
        y = h - margin_y - (row + 1) * (label_h + row_gap)
        if y < margin_y:
            c.showPage()
            row = 0
            y = h - margin_y - (row + 1) * (label_h + row_gap)

        c.rect(x, y, label_w, label_h)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 8, y + label_h - 14, f"SN: {sticker.serial_number}")
        c.setFont("Helvetica", 8)
        c.drawString(x + 8, y + label_h - 27, f"Panel: {sticker.panel_label}")
        c.drawString(
            x + 8, y + label_h - 39,
            f"Size: {sticker.width:.0f} x {sticker.length:.0f} mm",
        )
        c.drawString(x + 8, y + label_h - 51, f"Board: #{sticker.board_number}")
        c.drawString(
            x + 8, y + label_h - 63,
            f"Material: {sticker.board_type} {sticker.color_name}",
        )
        if sticker.notes:
            c.drawString(x + 8, y + label_h - 75, f"Notes: {sticker.notes}")

        col += 1
        if col >= cols:
            col = 0
            row += 1

    c.save()
    buf.seek(0)
    return buf.read()


def _labels_fallback(stickers) -> bytes:
    lines = ["LABELS", ""]
    for s in stickers:
        lines.append(
            f"SN:{s.serial_number}  {s.panel_label}  "
            f"{s.width:.0f}x{s.length:.0f}mm  Board#{s.board_number}  "
            f"{s.board_type} {s.color_name}"
        )
    return _text_to_minimal_pdf("\n".join(lines))


# ------------------------------------------------------------------ #
#  Minimal PDF builder (no reportlab)                                 #
# ------------------------------------------------------------------ #

def _text_to_minimal_pdf(text: str) -> bytes:
    text_lines = text.split("\n")
    stream_parts = ["BT", "/F1 11 Tf", "50 750 Td"]
    for line in text_lines:
        safe = (
            line.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        stream_parts.append(f"({safe}) Tj")
        stream_parts.append("0 -16 Td")
    stream_parts.append("ET")
    stream = "\n".join(stream_parts)

    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj",
        (
            "3 0 obj\n<< /Type /Page /Parent 2 0 R "
            "/MediaBox [0 0 612 792] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>\nendobj"
        ),
        f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n{stream}\nendstream\nendobj",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj",
    ]

    body = "\n".join(objects)
    xref_offset = len("%PDF-1.4\n") + len(body) + 1
    pdf = (
        "%PDF-1.4\n"
        + body
        + "\nxref\n0 6\n"
        + "trailer\n<< /Size 6 /Root 1 0 R >>\n"
        + f"startxref\n{xref_offset}\n%%EOF"
    )
    return pdf.encode("latin-1")
