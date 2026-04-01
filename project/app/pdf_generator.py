from __future__ import annotations

import io
import logging
from datetime import datetime

logger = logging.getLogger("panelpro")

try:
    from fpdf import FPDF

    _HAS_FPDF = True
except ImportError:
    _HAS_FPDF = False
    logger.warning("fpdf2 not installed – PDF export will return a placeholder.")


# ── helpers ──────────────────────────────────────────────
def _fallback_pdf(title: str = "PDF export unavailable") -> bytes:
    """Minimal valid PDF when fpdf2 is missing."""
    lines = [
        "%PDF-1.4",
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj",
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj",
        "3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj",
        "xref", "0 4",
        "0000000000 65535 f ",
        "0000000009 00000 n ",
        "0000000058 00000 n ",
        "0000000115 00000 n ",
        "trailer<</Size 4/Root 1 0 R>>",
        "startxref", "206", "%%EOF",
    ]
    return "\n".join(lines).encode("latin-1")


# ── Report PDF ───────────────────────────────────────────
def generate_report_pdf(
    *,
    request,
    layouts,
    optimization,
    edging,
    boq,
    stickers,
    stock_impact,
    report_id: str,
) -> bytes:
    if not _HAS_FPDF:
        return _fallback_pdf()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Title page ───────────────────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "PanelPro - Cutting Optimization Report", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Report ID:  {report_id}", ln=True)
    pdf.cell(0, 7, f"Date:       {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ln=True)
    pdf.cell(0, 7, f"Project:    {request.project_name}", ln=True)
    pdf.cell(0, 7, f"Customer:   {request.customer_name}", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Summary", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Boards used:      {optimization.total_boards}", ln=True)
    pdf.cell(0, 7, f"Total panels:     {optimization.total_panels}", ln=True)
    pdf.cell(0, 7, f"Efficiency:       {optimization.overall_efficiency_percent:.1f}%", ln=True)
    pdf.cell(0, 7, f"Waste:            {optimization.total_waste_percent:.1f}%", ln=True)
    pdf.cell(0, 7, f"Edging:           {edging.total_meters:.2f} m", ln=True)
    pdf.cell(0, 7, f"Kerf:             {optimization.kerf_mm} mm", ln=True)

    # ── Board layouts ────────────────────────────────────
    for layout in layouts:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(
            0, 10,
            f"Board {layout.board_number}  "
            f"({layout.board_width:.0f} x {layout.board_length:.0f} mm)  "
            f"Eff: {layout.efficiency_percent:.1f}%",
            ln=True,
        )
        pdf.set_font("Helvetica", "", 9)
        for p in layout.panels:
            rot_tag = " [R]" if p.rotated else ""
            pdf.cell(
                0, 5,
                f"  {p.label}: {p.width:.0f}x{p.length:.0f} mm  "
                f"at ({p.x:.0f},{p.y:.0f}){rot_tag}",
                ln=True,
            )

    # ── BOQ ──────────────────────────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Bill of Quantities", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for item in boq.items:
        pdf.cell(
            0, 6,
            f"{item.item_no}. {item.description}  {item.size}  "
            f"x{item.quantity}  edges={item.edges}",
            ln=True,
        )

    # ── Pricing ──────────────────────────────────────────
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Pricing", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for line in boq.pricing.lines:
        pdf.cell(0, 6, f"  {line.item}: {line.amount:.2f}", ln=True)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"  TOTAL: {boq.pricing.total:.2f}", ln=True)

    # ── Stock impact ─────────────────────────────────────
    if stock_impact:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, "Stock Impact", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for si in stock_impact:
            pdf.cell(
                0, 6,
                f"  {si.get('company','')} {si.get('color_name','')} "
                f"{si.get('thickness_mm','')}mm — "
                f"need {si.get('quantity_needed',0)}, "
                f"stock {si.get('current_stock',0)} → {si.get('after_stock',0)}"
                f"{'  ✓' if si.get('sufficient') else '  ✗ INSUFFICIENT'}",
                ln=True,
            )

    return bytes(pdf.output())


# ── Labels PDF ───────────────────────────────────────────
def generate_labels_pdf(stickers) -> bytes:
    if not _HAS_FPDF:
        return _fallback_pdf()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Panel Labels / Stickers", ln=True)
    pdf.ln(2)

    for i, s in enumerate(stickers):
        if i > 0 and i % 6 == 0:
            pdf.add_page()

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, s.serial_number, ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(
            0, 5,
            f"{s.panel_label}  |  {s.width:.0f}x{s.length:.0f} mm  |  "
            f"Board #{s.board_number}",
            ln=True,
        )
        pdf.cell(
            0, 5,
            f"{s.project_name} / {s.customer_name}  |  "
            f"{s.board_type} {s.thickness_mm}mm {s.company} {s.color_name}",
            ln=True,
        )
        pdf.cell(0, 5, f"QR: {s.qr_url}", ln=True)
        pdf.ln(4)

    return bytes(pdf.output())
