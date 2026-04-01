import io
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("panelpro.pdf")

_HAS_REPORTLAB = False
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas
    _HAS_REPORTLAB = True
except ImportError:
    logger.info("reportlab not installed - PDF output will be minimal plain-text")


# ------------------------------------------------------------------ #
#  Report PDF  (accepts both models and dicts)                        #
# ------------------------------------------------------------------ #

def generate_report_pdf(
    request=None,
    layouts=None,
    optimization=None,
    edging=None,
    boq=None,
    stickers=None,
    stock_impact=None,
    report_id: str = "",
    *,
    payload: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Generate report PDF.
    Can be called with individual typed args OR with payload=dict.
    """
    if payload is not None:
        return _report_from_dict(payload)

    if _HAS_REPORTLAB:
        return _report_reportlab(
            request, layouts or [], optimization, edging, boq,
            stickers or [], stock_impact or [], report_id,
        )
    return _report_fallback(request, optimization, edging, report_id)


def _safe_get(obj, key, default=""):
    """Get attribute from model or key from dict."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _safe_list(obj, key):
    """Get list attribute from model or key from dict."""
    if obj is None:
        return []
    if isinstance(obj, dict):
        return obj.get(key, [])
    return getattr(obj, key, [])


def _report_from_dict(payload: Dict[str, Any]) -> bytes:
    """Generate report PDF from the full response dict."""
    if _HAS_REPORTLAB:
        return _report_reportlab_dict(payload)
    return _report_fallback_dict(payload)


def _report_reportlab_dict(payload: Dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 50

    def _check(needed=60):
        nonlocal y
        if y < needed:
            c.showPage()
            y = h - 50

    report_id = payload.get("report_id", "N/A")
    summary = payload.get("request_summary", {})
    optimization = payload.get("optimization", {})
    edging = payload.get("edging", {})
    layouts = payload.get("layouts", [])
    pricing_data = payload.get("pricing", {})
    boq = payload.get("boq", {})

    # ---- Title ----
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, y, "PanelPro Cutting Report")
    y -= 8
    c.setLineWidth(2)
    c.line(50, y, w - 50, y)
    y -= 25

    # ---- Project info ----
    c.setFont("Helvetica", 11)
    info_lines = [
        f"Report ID:    {report_id}",
        f"Project:      {summary.get('project_name', 'N/A')}",
        f"Customer:     {summary.get('customer_name', 'N/A')}",
        f"Date:         {payload.get('generated_at', '')[:10]}",
        "",
        f"Board:        {summary.get('board_type', '')} - {summary.get('board_color', '')} ({summary.get('board_company', '')})",
        f"Board Size:   {summary.get('board_size', 'N/A')}",
        f"Thickness:    {summary.get('thickness_mm', '')} mm",
        f"Kerf:         {summary.get('kerf', 3)} mm",
    ]

    for line in info_lines:
        c.drawString(50, y, line)
        y -= 16

    # ---- Optimization summary ----
    y -= 10
    _check(120)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Optimization Summary")
    y -= 5
    c.setLineWidth(0.5)
    c.line(50, y, w - 50, y)
    y -= 18

    c.setFont("Helvetica", 11)
    opt_lines = [
        f"Total Boards:     {optimization.get('total_boards', 0)}",
        f"Total Panels:     {optimization.get('total_panels', 0)}",
        f"Efficiency:       {optimization.get('overall_efficiency_percent', 0):.1f}%",
        f"Total Waste:      {optimization.get('total_waste_percent', 0):.1f}%",
        f"Total Edging:     {edging.get('total_meters', 0):.2f} m",
        f"Total Cuts:       {optimization.get('total_cuts', 0)}",
    ]

    for line in opt_lines:
        c.drawString(50, y, line)
        y -= 16

    # ---- Board layouts ----
    y -= 10
    for layout in layouts:
        _check(120)
        material = layout.get("material", {}) if isinstance(layout, dict) else {}
        btype = material.get("board_type", "")
        color = material.get("color_name", "")

        board_num = layout.get("board_number", 0) if isinstance(layout, dict) else getattr(layout, "board_number", 0)
        board_w = layout.get("board_width", 0) if isinstance(layout, dict) else getattr(layout, "board_width", 0)
        board_l = layout.get("board_length", 0) if isinstance(layout, dict) else getattr(layout, "board_length", 0)
        panel_count = layout.get("panel_count", 0) if isinstance(layout, dict) else getattr(layout, "panel_count", 0)
        efficiency = layout.get("efficiency_percent", 0) if isinstance(layout, dict) else getattr(layout, "efficiency_percent", 0)
        waste = layout.get("waste_area_mm2", 0) if isinstance(layout, dict) else getattr(layout, "waste_area_mm2", 0)
        panels = layout.get("panels", []) if isinstance(layout, dict) else getattr(layout, "panels", [])

        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"Board #{board_num}  ({board_w:.0f} x {board_l:.0f} mm)  {btype} {color}")
        y -= 16

        c.setFont("Helvetica", 10)
        c.drawString(70, y, f"Panels: {panel_count}   Efficiency: {efficiency:.1f}%   Waste: {waste:.0f} mm\u00b2")
        y -= 14

        c.setFont("Helvetica", 9)
        for p in panels:
            _check()
            if isinstance(p, dict):
                label = p.get("label", "Panel")
                pw = p.get("width", 0)
                pl = p.get("length", 0)
                px = p.get("x", 0)
                py_val = p.get("y", 0)
                rot = " [rotated]" if p.get("rotated") else ""
            else:
                label = getattr(p, "label", "Panel")
                pw = getattr(p, "width", 0)
                pl = getattr(p, "length", 0)
                px = getattr(p, "x", 0)
                py_val = getattr(p, "y", 0)
                rot = " [rotated]" if getattr(p, "rotated", False) else ""

            c.drawString(90, y, f"- {label}: {pw:.0f} x {pl:.0f} mm  @ ({px:.0f}, {py_val:.0f}){rot}")
            y -= 13

        y -= 8

    # ---- Edging details ----
    edging_details = edging.get("details", []) if isinstance(edging, dict) else getattr(edging, "details", [])
    if edging_details:
        _check(100)
        y -= 6
        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, y, "Edging Details")
        y -= 5
        c.line(50, y, w - 50, y)
        y -= 16

        c.setFont("Helvetica", 10)
        for ed in edging_details:
            if isinstance(ed, dict):
                elabel = ed.get("panel_label", "")
                eqty = ed.get("quantity", 0)
                etotal = ed.get("total_edge_m", 0)
                eapplied = ed.get("edges_applied", "")
            else:
                elabel = getattr(ed, "panel_label", "")
                eqty = getattr(ed, "quantity", 0)
                etotal = getattr(ed, "total_edge_m", 0)
                eapplied = getattr(ed, "edges_applied", "")

            _check()
            c.drawString(70, y, f"{elabel} x{eqty}: {etotal:.2f} m  Edges: {eapplied}")
            y -= 14

    # ---- Pricing ----
    if pricing_data:
        pricing_lines = []
        subtotal = 0
        tax = 0
        total = 0

        if isinstance(pricing_data, dict):
            pricing_lines = pricing_data.get("lines", [])
            subtotal = pricing_data.get("subtotal", 0)
            tax = pricing_data.get("tax", 0)
            total = pricing_data.get("total", 0)
        elif hasattr(pricing_data, "lines"):
            pricing_lines = pricing_data.lines
            subtotal = pricing_data.subtotal
            tax = pricing_data.tax
            total = pricing_data.total

        if pricing_lines:
            _check(120)
            y -= 10
            c.setFont("Helvetica-Bold", 13)
            c.drawString(50, y, "Pricing Summary")
            y -= 5
            c.line(50, y, w - 50, y)
            y -= 18

            c.setFont("Helvetica", 11)
            for ln in pricing_lines:
                if isinstance(ln, dict):
                    item = ln.get("item", "")
                    desc = ln.get("description", "")
                    amt = ln.get("amount", 0)
                else:
                    item = getattr(ln, "item", "")
                    desc = getattr(ln, "description", "")
                    amt = getattr(ln, "amount", 0)

                _check()
                c.drawString(70, y, f"{item}: {desc}")
                c.drawRightString(w - 70, y, f"R {amt:.2f}")
                y -= 16

            y -= 4
            c.line(70, y + 8, w - 70, y + 8)
            c.drawString(70, y, f"Subtotal:")
            c.drawRightString(w - 70, y, f"R {subtotal:.2f}")
            y -= 16
            c.drawString(70, y, f"Tax:")
            c.drawRightString(w - 70, y, f"R {tax:.2f}")
            y -= 16
            c.setFont("Helvetica-Bold", 12)
            c.drawString(70, y, f"TOTAL:")
            c.drawRightString(w - 70, y, f"R {total:.2f}")

    # ---- Footer ----
    c.setFont("Helvetica", 8)
    c.drawString(50, 30, f"Generated by PanelPro Cutting Optimizer | {payload.get('generated_at', '')}")

    c.save()
    buf.seek(0)
    return buf.read()


def _report_reportlab(
    request, layouts, optimization, edging, boq,
    stickers, stock_impact, report_id,
) -> bytes:
    """Generate report from typed Pydantic models."""
    # Convert to dict and use the dict-based generator
    payload = {
        "report_id": report_id,
        "request_summary": {
            "project_name": _safe_get(request, "project_name", "N/A"),
            "customer_name": _safe_get(request, "customer_name", "N/A"),
            "board_type": _safe_get(_safe_get(request, "board"), "board_type", ""),
            "board_company": _safe_get(_safe_get(request, "board"), "company", ""),
            "board_color": _safe_get(_safe_get(request, "board"), "color_name", ""),
            "board_size": f"{_safe_get(_safe_get(request, 'board'), 'width_mm', 0):.0f} x {_safe_get(_safe_get(request, 'board'), 'length_mm', 0):.0f} mm",
            "thickness_mm": _safe_get(_safe_get(request, "board"), "thickness_mm", 0),
        },
        "optimization": optimization.model_dump(mode="python") if hasattr(optimization, "model_dump") else optimization,
        "edging": edging.model_dump(mode="python") if hasattr(edging, "model_dump") else edging,
        "layouts": [l.model_dump(mode="python") if hasattr(l, "model_dump") else l for l in (layouts or [])],
        "pricing": boq.pricing.model_dump(mode="python") if boq and hasattr(boq, "pricing") and boq.pricing and hasattr(boq.pricing, "model_dump") else {},
        "boq": boq.model_dump(mode="python") if hasattr(boq, "model_dump") else boq,
        "generated_at": "",
    }
    return _report_reportlab_dict(payload)


def _report_fallback(request, optimization, edging, report_id) -> bytes:
    lines = "\n".join([
        "PanelPro Cutting Report",
        "=" * 40,
        f"Report: {report_id}",
        f"Project: {_safe_get(request, 'project_name', 'N/A')}",
        f"Customer: {_safe_get(request, 'customer_name', 'N/A')}",
        "",
        f"Boards: {_safe_get(optimization, 'total_boards', 0)}",
        f"Panels: {_safe_get(optimization, 'total_panels', 0)}",
        f"Efficiency: {_safe_get(optimization, 'overall_efficiency_percent', 0):.1f}%",
        f"Edging: {_safe_get(edging, 'total_meters', 0):.2f} m",
    ])
    return _text_to_minimal_pdf(lines)


def _report_fallback_dict(payload: Dict[str, Any]) -> bytes:
    summary = payload.get("request_summary", {})
    optimization = payload.get("optimization", {})
    edging = payload.get("edging", {})

    lines = "\n".join([
        "PanelPro Cutting Report",
        "=" * 40,
        f"Report: {payload.get('report_id', 'N/A')}",
        f"Project: {summary.get('project_name', 'N/A')}",
        f"Customer: {summary.get('customer_name', 'N/A')}",
        "",
        f"Boards: {optimization.get('total_boards', 0)}",
        f"Panels: {optimization.get('total_panels', 0)}",
        f"Efficiency: {optimization.get('overall_efficiency_percent', 0):.1f}%",
        f"Waste: {optimization.get('total_waste_percent', 0):.1f}%",
        f"Edging: {edging.get('total_meters', 0):.2f} m",
        "",
    ])

    # Add layouts
    for layout in payload.get("layouts", []):
        bn = layout.get("board_number", 0) if isinstance(layout, dict) else getattr(layout, "board_number", 0)
        eff = layout.get("efficiency_percent", 0) if isinstance(layout, dict) else getattr(layout, "efficiency_percent", 0)
        lines += f"\nBoard #{bn} - {eff:.1f}% efficiency"
        panels = layout.get("panels", []) if isinstance(layout, dict) else getattr(layout, "panels", [])
        for p in panels:
            if isinstance(p, dict):
                lines += f"\n  {p.get('label', 'Panel')}: {p.get('width', 0):.0f}x{p.get('length', 0):.0f}mm"
            else:
                lines += f"\n  {getattr(p, 'label', 'Panel')}: {getattr(p, 'width', 0):.0f}x{getattr(p, 'length', 0):.0f}mm"

    return _text_to_minimal_pdf(lines)


# ------------------------------------------------------------------ #
#  Labels PDF                                                         #
# ------------------------------------------------------------------ #

def generate_labels_pdf(
    stickers=None,
    *,
    payload: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Generate labels PDF.
    Can be called with stickers list OR payload=dict.
    """
    if payload is not None:
        sticker_list = payload.get("stickers", [])
        project = payload.get("request_summary", {}).get("project_name", "")
        customer = payload.get("request_summary", {}).get("customer_name", "")
    else:
        sticker_list = stickers or []
        project = ""
        customer = ""

    if _HAS_REPORTLAB:
        return _labels_reportlab(sticker_list, project, customer)
    return _labels_fallback(sticker_list)


def _labels_reportlab(stickers, project: str = "", customer: str = "") -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    label_w, label_h = 250, 95
    margin_x, margin_y = 50, 60
    col_gap, row_gap = 20, 12
    cols = 2
    x_positions = [margin_x, margin_x + label_w + col_gap]

    # ---- Header ----
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, h - 35, "PanelPro - Panel Labels")
    c.setFont("Helvetica", 10)
    header_text = ""
    if project:
        header_text += f"Project: {project}"
    if customer:
        header_text += f"  |  Customer: {customer}"
    if header_text:
        c.drawString(50, h - 52, header_text)

    row = 0
    col = 0

    for idx, sticker in enumerate(stickers):
        x = x_positions[col]
        y = h - margin_y - 20 - (row + 1) * (label_h + row_gap) + label_h

        if y < margin_y:
            c.showPage()
            row = 0
            y = h - margin_y - 20 - (row + 1) * (label_h + row_gap) + label_h

        # Get values (handle both dict and model)
        if isinstance(sticker, dict):
            serial = sticker.get("serial_number", "")
            panel_label = sticker.get("panel_label", "Panel")
            sw = sticker.get("width", 0)
            sl = sticker.get("length", 0)
            board_num = sticker.get("board_number", 0)
            sx = sticker.get("x", 0)
            sy = sticker.get("y", 0)
            rotated = sticker.get("rotated", False)
            board_type = sticker.get("board_type", "")
            color_name = sticker.get("color_name", "")
            thickness = sticker.get("thickness_mm", "")
            notes = sticker.get("notes")
            qr_url = sticker.get("qr_url", "")
        else:
            serial = getattr(sticker, "serial_number", "")
            panel_label = getattr(sticker, "panel_label", "Panel")
            sw = getattr(sticker, "width", 0)
            sl = getattr(sticker, "length", 0)
            board_num = getattr(sticker, "board_number", 0)
            sx = getattr(sticker, "x", 0)
            sy = getattr(sticker, "y", 0)
            rotated = getattr(sticker, "rotated", False)
            board_type = getattr(sticker, "board_type", "")
            color_name = getattr(sticker, "color_name", "")
            thickness = getattr(sticker, "thickness_mm", "")
            notes = getattr(sticker, "notes", None)
            qr_url = getattr(sticker, "qr_url", "")

        # ---- Draw label box ----
        c.setStrokeColorRGB(0.2, 0.2, 0.2)
        c.setLineWidth(0.8)
        c.roundRect(x, y - label_h, label_w, label_h, 4)

        # ---- Header bar ----
        c.setFillColorRGB(0.15, 0.15, 0.15)
        c.rect(x, y - 16, label_w, 16, fill=True)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 6, y - 12, f"{panel_label}")
        c.drawRightString(x + label_w - 6, y - 12, f"Board #{board_num}")

        # ---- Body ----
        c.setFillColorRGB(0, 0, 0)
        inner_y = y - 30

        c.setFont("Helvetica", 8)
        c.drawString(x + 6, inner_y, f"Size: {sw:.0f} x {sl:.0f} mm")
        rot_text = "Yes" if rotated else "No"
        c.drawRightString(x + label_w - 6, inner_y, f"Rotated: {rot_text}")
        inner_y -= 11

        c.drawString(x + 6, inner_y, f"Position: ({sx:.0f}, {sy:.0f})")
        inner_y -= 11

        c.drawString(x + 6, inner_y, f"Material: {board_type} {color_name} {thickness}mm")
        inner_y -= 11

        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 6, inner_y, f"SN: {serial}")
        inner_y -= 10

        if notes:
            c.setFont("Helvetica-Oblique", 7)
            c.drawString(x + 6, inner_y, f"Notes: {notes[:40]}")

        col += 1
        if col >= cols:
            col = 0
            row += 1

    c.save()
    buf.seek(0)
    return buf.read()


def _labels_fallback(stickers) -> bytes:
    lines = ["PANEL LABELS", "=" * 40, ""]
    for s in stickers:
        if isinstance(s, dict):
            lines.append(f"SN: {s.get('serial_number', '')}")
            lines.append(f"  Panel: {s.get('panel_label', '')}")
            lines.append(f"  Size: {s.get('width', 0):.0f} x {s.get('length', 0):.0f} mm")
            lines.append(f"  Board #{s.get('board_number', 0)}")
            lines.append(f"  Material: {s.get('board_type', '')} {s.get('color_name', '')}")
        else:
            lines.append(f"SN: {getattr(s, 'serial_number', '')}")
            lines.append(f"  Panel: {getattr(s, 'panel_label', '')}")
            lines.append(f"  Size: {getattr(s, 'width', 0):.0f} x {getattr(s, 'length', 0):.0f} mm")
            lines.append(f"  Board #{getattr(s, 'board_number', 0)}")
            lines.append(f"  Material: {getattr(s, 'board_type', '')} {getattr(s, 'color_name', '')}")
        lines.append("")
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
