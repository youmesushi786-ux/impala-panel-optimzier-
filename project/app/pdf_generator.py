from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger("panelpro")

try:
    from fpdf import FPDF
    _HAS_FPDF = True
except ImportError:
    _HAS_FPDF = False


def _fallback_pdf() -> bytes:
    lines = [
        "%PDF-1.4",
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj",
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj",
        "3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj",
        "xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n206\n%%EOF"
    ]
    return "\n".join(lines).encode("latin-1")


def generate_report_pdf(*, request, layouts, optimization, edging, boq, stickers, stock_impact, report_id: str) -> bytes:
    if not _HAS_FPDF: return _fallback_pdf()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title & Metadata
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "PanelPro - Factory Production & Cutting Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Report ID: {report_id}  |  Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ln=True)
    pdf.cell(0, 5, f"Project: {request.project_name}  |  Customer: {request.customer_name}", ln=True)
    pdf.ln(4)

    # Key Performance Summary
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Optimization KPIs", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, f"Total Boards: {optimization.total_boards} (Full Sheets: {getattr(optimization, 'total_full_sheets', optimization.total_boards)}, Offcuts Reused: {getattr(optimization, 'total_offcuts_used', 0)})", ln=True)
    pdf.cell(0, 5, f"Yield Efficiency: {optimization.overall_efficiency_percent:.1f}%  |  Waste: {optimization.total_waste_percent:.1f}%", ln=True)
    pdf.cell(0, 5, f"New Remnants Generated: {getattr(optimization, 'total_offcuts_created', 0)}  |  Total Edging: {edging.total_meters:.2f} m", ln=True)
    pdf.ln(4)

    # Layouts
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Board Cutting Layouts", ln=True)
    for layout in layouts:
        src = f" [REUSED OFFCUT {layout.offcut_code}]" if getattr(layout, "source", "") == "offcut" else " [FULL SHEET]"
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, f"Board #{layout.board_number} ({layout.board_width:.0f}x{layout.board_length:.0f} mm) - Eff: {layout.efficiency_percent:.1f}%{src}", ln=True)
        pdf.set_font("Helvetica", "", 8)
        for p in layout.panels:
            rot = " [R]" if p.rotated else ""
            pdf.cell(0, 4, f"   - {p.label}: {p.width:.0f}x{p.length:.0f} mm at ({p.x:.0f},{p.y:.0f}){rot}", ln=True)
        if getattr(layout, "remnant_width_mm", 0) > 0:
            pdf.cell(0, 4, f"   * Reusable Waste Rectangle: {layout.remnant_width_mm:.0f}x{layout.remnant_length_mm:.0f} mm", ln=True)

    # BOQ & Pricing
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Bill of Quantities (BOQ)", ln=True)
    pdf.set_font("Helvetica", "", 9)
    for item in boq.items:
        pdf.cell(0, 5, f"{item.item_no}. {item.description} ({item.size}) x{item.quantity} - Edges: {item.edges}", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Financial Summary", ln=True)
    pdf.set_font("Helvetica", "", 9)
    for line in boq.pricing.lines:
        pdf.cell(0, 5, f"   {line.item}: {line.description} = {line.amount:.2f}", ln=True)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, f"   TOTAL AMOUNT: {boq.pricing.total:.2f}", ln=True)

    return bytes(pdf.output())


def generate_labels_pdf(stickers) -> bytes:
    if not _HAS_FPDF: return _fallback_pdf()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "Printable Factory Panel Labels", ln=True)
    pdf.ln(2)

    for i, s in enumerate(stickers):
        if i > 0 and i % 6 == 0: pdf.add_page()

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 5, f"Serial: {s.serial_number}  |  Board #{s.board_number}", ln=True)
        pdf.set_font("Helvetica", "", 8)
        src = f"Offcut ({s.offcut_code})" if getattr(s, "source", "") == "offcut" else "Full Sheet"
        pdf.cell(0, 4, f"Panel: {s.panel_label} ({s.width:.0f}x{s.length:.0f} mm)  |  Source: {src}", ln=True)
        pdf.cell(0, 4, f"Material: {s.board_type} {s.thickness_mm:.0f}mm {s.company} {s.color_name}", ln=True)
        pdf.cell(0, 4, f"QR Code: {s.qr_url}", ln=True)
        pdf.ln(3)

    return bytes(pdf.output())
