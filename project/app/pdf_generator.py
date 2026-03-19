from __future__ import annotations

import io
import os
from datetime import datetime
from typing import List

import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    Image,
    Flowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader

from .schemas import (
    CuttingRequest,
    BoardLayout,
    OptimizationSummary,
    EdgingSummary,
    BOQSummary,
    StickerLabel,
    StockImpactItem,
)
from .config import COMPANY_LOGO_PATH, COMPANY_NAME

LOGO_PATH = COMPANY_LOGO_PATH


def _styles():
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="Small",
            fontSize=8,
            leading=10,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            fontSize=14,
            leading=18,
            spaceAfter=8,
            textColor=colors.HexColor("#1f2937"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="NormalWrap",
            fontSize=9,
            leading=11,
        )
    )

    return styles


def _safe_text(value) -> str:
    return "" if value is None else str(value)


def _draw_logo_if_exists(width=40 * mm, height=20 * mm):
    if os.path.exists(LOGO_PATH):
        try:
            return Image(LOGO_PATH, width=width, height=height)
        except Exception:
            return None
    return None


def _table(data, col_widths=None, header_bg=colors.HexColor("#e5e7eb")):
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), header_bg),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return tbl


class BoardLayoutDrawing(Flowable):
    def __init__(self, layout: BoardLayout, width=170 * mm, height=110 * mm):
        super().__init__()
        self.layout = layout
        self.draw_width = width
        self.draw_height = height
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv

        board_w = self.layout.board_width
        board_h = self.layout.board_length

        if board_w <= 0 or board_h <= 0:
            return

        margin = 6
        scale_x = (self.draw_width - margin * 2) / board_w
        scale_y = (self.draw_height - margin * 2) / board_h
        scale = min(scale_x, scale_y)

        actual_w = board_w * scale
        actual_h = board_h * scale

        origin_x = margin
        origin_y = self.draw_height - actual_h - margin

        c.setStrokeColor(colors.black)
        c.setLineWidth(1)
        c.rect(origin_x, origin_y, actual_w, actual_h, stroke=1, fill=0)

        c.setFont("Helvetica", 7)
        c.drawString(origin_x, origin_y + actual_h + 4, f"{int(board_w)} x {int(board_h)} mm")

        for p in self.layout.panels:
            px = origin_x + p.x * scale
            py = origin_y + actual_h - ((p.y + p.length) * scale)
            pw = p.width * scale
            ph = p.length * scale

            fill_color = colors.HexColor("#fff7ed") if not p.rotated else colors.HexColor("#eff6ff")
            stroke_color = colors.HexColor("#f97316") if not p.rotated else colors.HexColor("#2563eb")

            c.setStrokeColor(stroke_color)
            c.setFillColor(fill_color)
            c.rect(px, py, pw, ph, stroke=1, fill=1)

            c.setFillColor(colors.black)
            font_size = 6 if min(pw, ph) > 20 else 4
            c.setFont("Helvetica", font_size)

            label = _safe_text(p.label) or f"P{p.panel_index + 1}"
            c.drawString(px + 2, py + max(ph - 8, 2), label[:18])

            if ph > 12:
                c.drawString(px + 2, py + max(ph - 15, 2), f"{int(p.width)}x{int(p.length)}")

        if self.layout.cuts:
            c.setStrokeColor(colors.HexColor("#6b7280"))
            c.setLineWidth(0.4)
            for cut in self.layout.cuts:
                x1 = origin_x + cut.x1 * scale
                y1 = origin_y + actual_h - (cut.y1 * scale)
                x2 = origin_x + cut.x2 * scale
                y2 = origin_y + actual_h - (cut.y2 * scale)
                c.line(x1, y1, x2, y2)


def _make_qr_image(value: str, box_size: int = 4):
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=1,
    )
    qr.add_data(value)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    return ImageReader(img_buffer)


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
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )

    styles = _styles()
    story = []

    logo = _draw_logo_if_exists()
    if logo:
        story.append(logo)
        story.append(Spacer(1, 6))

    story.append(Paragraph(f"<b>{_safe_text(COMPANY_NAME)}</b>", styles["Normal"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Production Optimization Report</b>", styles["Title"]))
    story.append(Spacer(1, 6))

    story.append(
        Paragraph(
            f"<b>Report ID:</b> {report_id}<br/>"
            f"<b>Date:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
            f"<b>Project:</b> {_safe_text(request.project_name)}<br/>"
            f"<b>Customer:</b> {_safe_text(request.customer_name)}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("Optimization Summary", styles["SectionTitle"]))
    summary_data = [
        ["Metric", "Value"],
        ["Boards Used", _safe_text(optimization.total_boards)],
        ["Total Panels", _safe_text(optimization.total_panels)],
        ["Unique Panel Types", _safe_text(optimization.unique_panel_types)],
        ["Total Waste (%)", f"{optimization.total_waste_percent:.2f}%"],
        ["Total Waste (mm²)", f"{optimization.total_waste_mm2:.0f}"],
        ["Total Edging (m)", f"{optimization.total_edging_meters:.2f}"],
        ["Guide Cuts", _safe_text(optimization.total_cuts)],
        ["Guide Cut Length", f"{optimization.total_cut_length:.2f} mm"],
        ["Board Size", f"{optimization.board_width} × {optimization.board_length} mm"],
    ]
    story.append(_table(summary_data, col_widths=[70 * mm, 90 * mm]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Stock Impact", styles["SectionTitle"]))
    if stock_impact:
        stock_data = [["Board", "Current", "Required", "Projected Balance", "Price/Board", "Status"]]
        for item in stock_impact:
            stock_data.append(
                [
                    item.board_label,
                    str(item.current_quantity),
                    str(item.required_quantity),
                    str(item.projected_balance),
                    f"{item.price_per_board:.2f}",
                    item.stock_status,
                ]
            )
        story.append(_table(stock_data, col_widths=[70 * mm, 20 * mm, 20 * mm, 30 * mm, 25 * mm, 25 * mm]))
    else:
        story.append(Paragraph("No stock impact data available.", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Edging Summary", styles["SectionTitle"]))
    edging_data = [["Panel", "Qty", "Edge / Panel (m)", "Total Edge (m)", "Applied Edges"]]
    for detail in edging.details:
        edging_data.append(
            [
                detail.panel_label,
                str(detail.quantity),
                f"{detail.edge_per_panel_m:.2f}",
                f"{detail.total_edge_m:.2f}",
                detail.edges_applied,
            ]
        )
    story.append(_table(edging_data, col_widths=[50 * mm, 15 * mm, 35 * mm, 35 * mm, 35 * mm]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("BOQ Items", styles["SectionTitle"]))
    boq_items_data = [["#", "Description", "Size", "Qty", "Unit", "Edges", "Material"]]
    for item in boq.items:
        boq_items_data.append(
            [
                str(item.item_no),
                item.description,
                item.size,
                str(item.quantity),
                item.unit,
                item.edges,
                f"{_safe_text(item.board_type)} {_safe_text(item.thickness_mm)}mm {_safe_text(item.company)} {_safe_text(item.colour)}",
            ]
        )
    story.append(
        _table(
            boq_items_data,
            col_widths=[10 * mm, 35 * mm, 28 * mm, 14 * mm, 14 * mm, 20 * mm, 55 * mm],
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("Pricing Summary", styles["SectionTitle"]))
    pricing_data = [["Item", "Description", "Qty", "Unit", "Unit Price", "Amount"]]
    for line in boq.pricing.lines:
        pricing_data.append(
            [
                line.item,
                line.description,
                str(line.quantity),
                line.unit,
                f"{line.unit_price:.2f}",
                f"{line.amount:.2f}",
            ]
        )

    pricing_data.extend(
        [
            ["", "", "", "", "Subtotal", f"{boq.pricing.subtotal:.2f}"],
            ["", "", "", "", f"{boq.pricing.tax_name} ({boq.pricing.tax_rate}%)", f"{boq.pricing.tax_amount:.2f}"],
            ["", "", "", "", "Total", f"{boq.pricing.total:.2f}"],
        ]
    )

    story.append(
        _table(
            pricing_data,
            col_widths=[25 * mm, 60 * mm, 18 * mm, 18 * mm, 30 * mm, 25 * mm],
        )
    )
    story.append(Spacer(1, 10))

    story.append(PageBreak())
    story.append(Paragraph("Board Layout Details", styles["SectionTitle"]))

    for layout in layouts:
        story.append(
            Paragraph(
                f"<b>Board #{layout.board_number}</b> - "
                f"{layout.board_width} × {layout.board_length} mm - "
                f"Efficiency: {layout.efficiency_percent:.2f}% - "
                f"Waste: {layout.waste_area_mm2:.0f} mm²",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 4))

        panel_data = [["#", "Label", "Position", "Actual Size", "Footprint", "Rotated", "Notes"]]
        for i, p in enumerate(layout.panels, start=1):
            panel_data.append(
                [
                    str(i),
                    _safe_text(p.label),
                    f"({p.x:.0f}, {p.y:.0f})",
                    f"{p.width:.0f} × {p.length:.0f}",
                    f"{p.footprint_width:.0f} × {p.footprint_length:.0f}",
                    "Yes" if p.rotated else "No",
                    _safe_text(p.notes),
                ]
            )

        story.append(
            _table(
                panel_data,
                col_widths=[10 * mm, 35 * mm, 28 * mm, 28 * mm, 30 * mm, 16 * mm, 40 * mm],
            )
        )
        story.append(Spacer(1, 8))

        if layout.cuts:
            cut_data = [["Seq", "Orientation", "Start", "End", "Length (mm)"]]
            for cut in layout.cuts:
                cut_data.append(
                    [
                        str(cut.sequence or cut.id),
                        cut.orientation,
                        f"({cut.x1:.0f}, {cut.y1:.0f})",
                        f"({cut.x2:.0f}, {cut.y2:.0f})",
                        f"{cut.length:.0f}",
                    ]
                )
            story.append(_table(cut_data, col_widths=[15 * mm, 25 * mm, 40 * mm, 40 * mm, 30 * mm]))
            story.append(Spacer(1, 12))

    if layouts:
        story.append(PageBreak())
        story.append(Paragraph("Printable Cutting Layouts", styles["SectionTitle"]))
        story.append(Spacer(1, 6))

        for layout in layouts:
            story.append(
                Paragraph(
                    f"<b>Board #{layout.board_number}</b> - {layout.board_width} × {layout.board_length} mm",
                    styles["Normal"],
                )
            )
            story.append(Spacer(1, 4))
            story.append(BoardLayoutDrawing(layout, width=170 * mm, height=110 * mm))
            story.append(Spacer(1, 12))

    if stickers:
        story.append(PageBreak())
        story.append(Paragraph("Sticker / Panel Label Summary", styles["SectionTitle"]))

        sticker_data = [["Serial", "Panel", "Board", "Size", "Rotated", "Material", "Notes"]]
        for s in stickers:
            sticker_data.append(
                [
                    s.serial_number,
                    s.panel_label,
                    str(s.board_number),
                    f"{s.width:.0f} × {s.length:.0f}",
                    "Yes" if s.rotated else "No",
                    f"{_safe_text(s.board_type)} {_safe_text(s.thickness_mm)}mm {_safe_text(s.company)} {_safe_text(s.color_name)}",
                    _safe_text(s.notes),
                ]
            )

        story.append(
            _table(
                sticker_data,
                col_widths=[30 * mm, 35 * mm, 15 * mm, 26 * mm, 16 * mm, 50 * mm, 30 * mm],
            )
        )

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def _make_qr_image(value: str, box_size: int = 4):
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=1,
    )
    qr.add_data(value)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    return ImageReader(img_buffer)


def generate_labels_pdf(stickers: List[StickerLabel]) -> bytes:
    """
    Premium industrial warehouse sticker label
    - company strip with logo + phone
    - strong panel title bar
    - serial badge
    - board badge
    - compact details block
    - QR code block
    - project/client footer
    """
    buffer = io.BytesIO()

    label_width = 70 * mm
    label_height = 45 * mm

    c = canvas.Canvas(buffer, pagesize=(label_width, label_height))

    ORANGE = colors.HexColor("#f97316")
    DARK = colors.HexColor("#111827")
    LIGHT_BG = colors.HexColor("#f8fafc")
    HEADER_BG = colors.HexColor("#fff7ed")
    MUTED = colors.HexColor("#475569")
    BLUE = colors.HexColor("#dbeafe")
    GREEN = colors.HexColor("#dcfce7")

    def draw_badge(x, y, w, h, text, bg, fg=colors.black, bold=True, center=True, size=5.8):
        c.setFillColor(bg)
        c.setStrokeColor(DARK)
        c.setLineWidth(0.4)
        c.roundRect(x, y, w, h, 1.6 * mm, stroke=1, fill=1)
        c.setFillColor(fg)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        if center:
            c.drawCentredString(x + w / 2, y + h / 2 - 1.8, str(text))
        else:
            c.drawString(x + 2, y + h / 2 - 1.8, str(text))

    def draw_label(sticker: StickerLabel):
        c.setStrokeColor(DARK)
        c.setLineWidth(1.1)
        c.rect(1 * mm, 1 * mm, label_width - 2 * mm, label_height - 2 * mm, stroke=1, fill=0)

        # Top company strip
        header_x = 2 * mm
        header_y = label_height - 7.5 * mm
        header_w = label_width - 4 * mm
        header_h = 5.5 * mm

        c.setFillColor(HEADER_BG)
        c.setStrokeColor(DARK)
        c.rect(header_x, header_y, header_w, header_h, stroke=1, fill=1)

        if os.path.exists(LOGO_PATH):
            try:
                c.drawImage(
                    LOGO_PATH,
                    header_x + 1 * mm,
                    header_y + 0.5 * mm,
                    width=6.2 * mm,
                    height=4.3 * mm,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            except Exception:
                pass

        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 6.7)
        c.drawString(header_x + 8.4 * mm, header_y + 3.2 * mm, _safe_text(sticker.company_name or COMPANY_NAME)[:18])

        c.setFont("Helvetica", 5)
        if getattr(sticker, "company_phone", None):
            c.drawRightString(header_x + header_w - 1 * mm, header_y + 3.2 * mm, _safe_text(sticker.company_phone))

        # Title bar
        title_x = 2.5 * mm
        title_y = label_height - 14.5 * mm
        title_w = 42 * mm
        title_h = 5.7 * mm

        c.setFillColor(ORANGE)
        c.rect(title_x, title_y, title_w, title_h, stroke=0, fill=1)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8.2)
        c.drawString(title_x + 1.6 * mm, title_y + 1.8 * mm, _safe_text(sticker.panel_label)[:16])

        # Rotation badge
        draw_badge(
            title_x + 28 * mm,
            title_y + 0.7 * mm,
            12 * mm,
            4 * mm,
            "ROT" if sticker.rotated else "STD",
            BLUE if sticker.rotated else GREEN,
            fg=DARK,
            size=5.2,
        )

        # Left details table
        table_x = 2.5 * mm
        table_y = 8.4 * mm
        label_col_w = 10.5 * mm
        value_col_w = 31.5 * mm
        row_h = 4.6 * mm

        rows = [
            ("SIZE", f"{int(sticker.width)} x {int(sticker.length)}"),
            ("PRJ", _safe_text(sticker.project_name)[:18]),
            ("CLIENT", _safe_text(sticker.customer_name)[:16]),
        ]

        current_y = table_y + row_h * len(rows)
        for k, v in rows:
            current_y -= row_h

            c.setFillColor(LIGHT_BG)
            c.setStrokeColor(DARK)
            c.setLineWidth(0.45)
            c.rect(table_x, current_y, label_col_w, row_h, stroke=1, fill=1)

            c.setFillColor(DARK)
            c.setFont("Helvetica-Bold", 5.7)
            c.drawString(table_x + 1.0 * mm, current_y + 1.5 * mm, k)

            c.setFillColor(colors.white)
            c.rect(table_x + label_col_w, current_y, value_col_w, row_h, stroke=1, fill=1)
            c.setFillColor(DARK)
            c.setFont("Helvetica", 5.9)
            c.drawString(table_x + label_col_w + 1.0 * mm, current_y + 1.5 * mm, v[:25])

        # Serial + board badges
        draw_badge(
            2.8 * mm,
            4.7 * mm,
            27 * mm,
            3.6 * mm,
            _safe_text(sticker.serial_number)[:18],
            colors.HexColor("#e5e7eb"),
            fg=DARK,
            size=5.2,
        )

        draw_badge(
            31 * mm,
            4.7 * mm,
            13 * mm,
            3.6 * mm,
            f"B-{_safe_text(sticker.board_number)}",
            colors.HexColor("#e0f2fe"),
            fg=DARK,
            size=5.2,
        )

        # QR block
        qr_x = 47 * mm
        qr_y = 6 * mm
        qr_w = 20 * mm
        qr_h = 28 * mm

        c.setStrokeColor(DARK)
        c.setLineWidth(0.8)
        c.rect(qr_x, qr_y, qr_w, qr_h, stroke=1, fill=0)

        c.setFillColor(LIGHT_BG)
        c.rect(qr_x + 0.5 * mm, qr_y + qr_h - 5 * mm, qr_w - 1 * mm, 4.5 * mm, stroke=0, fill=1)
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 5.8)
        c.drawCentredString(qr_x + qr_w / 2, qr_y + qr_h - 3.4 * mm, "SCAN")

        if getattr(sticker, "qr_url", None):
            try:
                qr_img = _make_qr_image(sticker.qr_url)
                c.drawImage(
                    qr_img,
                    qr_x + 1.5 * mm,
                    qr_y + 4.5 * mm,
                    width=17 * mm,
                    height=17 * mm,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            except Exception:
                pass

        # Footer strip
        footer_x = 2.5 * mm
        footer_y = 2.0 * mm
        footer_w = label_width - 5 * mm
        footer_h = 2.8 * mm

        c.setFillColor(LIGHT_BG)
        c.setStrokeColor(DARK)
        c.rect(footer_x, footer_y, footer_w, footer_h, stroke=1, fill=1)

        c.setFillColor(MUTED)
        c.setFont("Helvetica", 5.0)
        c.drawString(footer_x + 1.3 * mm, footer_y + 0.75 * mm, "Factory Production Label")

    for idx, sticker in enumerate(stickers):
        draw_label(sticker)
        if idx < len(stickers) - 1:
            c.showPage()

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf