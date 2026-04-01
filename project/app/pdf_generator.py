import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("panelpro.pdf")

_RL = False
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas
    _RL = True
except ImportError:
    logger.info("reportlab not available — fallback PDFs only")


def _g(obj, key, default=""):
    if obj is None: return default
    if isinstance(obj, dict): return obj.get(key, default)
    return getattr(obj, key, default)


def _gl(obj, key):
    if obj is None: return []
    if isinstance(obj, dict): return obj.get(key, [])
    return getattr(obj, key, [])


def _to_dict(obj):
    if obj is None: return {}
    if isinstance(obj, dict): return obj
    if hasattr(obj, "model_dump"): return obj.model_dump(mode="python")
    if hasattr(obj, "__dict__"): return {k:v for k,v in obj.__dict__.items() if not k.startswith("_")}
    return {}


def _normalize(payload: dict) -> dict:
    """Turn ANY shape of payload into a flat predictable dict."""
    rs = _g(payload, "request_summary", {})
    if not isinstance(rs, dict): rs = {}

    opt = _g(payload, "optimization") or _g(payload, "summary") or {}
    opt = _to_dict(opt) if not isinstance(opt, dict) else opt

    layouts = _gl(payload, "layouts") or _gl(payload, "boards")
    clean_layouts = []
    for la in layouts:
        la = _to_dict(la) if not isinstance(la, dict) else la
        la["panels"] = [_to_dict(p) if not isinstance(p, dict) else p for p in la.get("panels", [])]
        la["cuts"]   = [_to_dict(c) if not isinstance(c, dict) else c for c in la.get("cuts", [])]
        clean_layouts.append(la)

    edging = _to_dict(_g(payload, "edging")) if not isinstance(_g(payload, "edging"), dict) else _g(payload, "edging", {})
    edging_details = edging.get("details", [])
    edging["details"] = [_to_dict(d) if not isinstance(d, dict) else d for d in edging_details]

    pricing = _g(payload, "pricing") or {}
    if not isinstance(pricing, dict):
        pricing = _to_dict(pricing)
    if not pricing:
        boq = _g(payload, "boq") or {}
        if not isinstance(boq, dict): boq = _to_dict(boq)
        p2 = boq.get("pricing")
        if p2:
            pricing = _to_dict(p2) if not isinstance(p2, dict) else p2
    if pricing.get("lines"):
        pricing["lines"] = [_to_dict(l) if not isinstance(l, dict) else l for l in pricing["lines"]]

    stickers = _gl(payload, "stickers")
    stickers = [_to_dict(s) if not isinstance(s, dict) else s for s in stickers]

    return {
        "report_id":    _g(payload, "report_id", "N/A"),
        "generated_at": _g(payload, "generated_at", datetime.utcnow().isoformat()),
        "project":      rs.get("project_name") or _g(payload, "project_name", "N/A"),
        "customer":     rs.get("customer_name") or _g(payload, "customer_name", "N/A"),
        "board_type":   rs.get("board_type", ""),
        "board_color":  rs.get("board_color", ""),
        "board_company":rs.get("board_company", ""),
        "board_size":   rs.get("board_size", ""),
        "thickness_mm": rs.get("thickness_mm", ""),
        "kerf":         rs.get("kerf", 3),
        "opt":          opt,
        "layouts":      clean_layouts,
        "edging":       edging,
        "pricing":      pricing,
        "stickers":     stickers,
    }


# ================================================================== #
#  REPORT PDF                                                         #
# ================================================================== #
def generate_report_pdf(payload: dict = None, **kw) -> bytes:
    data = _normalize(payload or kw)
    return _report_rl(data) if _RL else _report_txt(data)


def _report_rl(d: dict) -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    y = H - 50; pg = 1

    def nl(n=60):
        nonlocal y, pg
        if y < n:
            c.setFont("Helvetica",7); c.setFillGray(0.5)
            c.drawString(50,20,f"PanelPro | Page {pg}")
            c.setFillGray(0); c.showPage(); pg+=1; y=H-50

    # ---- title ----
    c.setFont("Helvetica-Bold",20); c.drawString(50,y,"PanelPro Cutting Report")
    y-=8; c.setLineWidth(2); c.line(50,y,W-50,y); y-=25

    # ---- info ----
    for lbl,val in [
        ("Report ID:", d["report_id"]),
        ("Project:",   d["project"]),
        ("Customer:",  d["customer"]),
        ("Date:",      d["generated_at"][:10]),
        ("",""),
        ("Board:",     f"{d['board_type']} - {d['board_color']} ({d['board_company']})"),
        ("Board Size:",d["board_size"]),
        ("Thickness:", f"{d['thickness_mm']} mm"),
        ("Kerf:",      f"{d['kerf']} mm"),
    ]:
        if lbl:
            c.setFont("Helvetica-Bold",10); c.drawString(50,y,lbl)
            c.setFont("Helvetica",10); c.drawString(160,y,str(val))
        y-=15

    # ---- summary ----
    o = d["opt"]; y-=10; nl(140)
    c.setFont("Helvetica-Bold",14); c.drawString(50,y,"Optimization Summary")
    y-=5; c.setLineWidth(.5); c.line(50,y,W-50,y); y-=18
    for lbl,val in [
        ("Total Boards:", o.get("total_boards",0)),
        ("Total Panels:", o.get("total_panels",0)),
        ("Efficiency:",   f"{o.get('overall_efficiency_percent',0):.1f}%"),
        ("Waste:",        f"{o.get('total_waste_percent',0):.1f}%"),
        ("Edging:",       f"{d['edging'].get('total_meters',0):.2f} m"),
        ("Cuts:",         o.get("total_cuts",0)),
    ]:
        c.setFont("Helvetica-Bold",10); c.drawString(50,y,str(lbl))
        c.setFont("Helvetica",10); c.drawString(170,y,str(val))
        y-=15

    # warnings
    for w in o.get("warnings",[]):
        nl(); c.setFont("Helvetica-Oblique",9)
        c.setFillColorRGB(.8,.2,0); c.drawString(50,y,f"⚠ {w}"); c.setFillGray(0); y-=13

    # impossible
    imp = o.get("impossible_panels",[])
    if imp:
        y-=5; c.setFont("Helvetica-Bold",10); c.setFillColorRGB(.8,0,0)
        c.drawString(50,y,"Could not place:"); y-=14; c.setFont("Helvetica",9)
        for p in imp: nl(); c.drawString(70,y,f"• {p}"); y-=12
        c.setFillGray(0)

    # ---- boards ----
    y-=15
    for lay in d["layouts"]:
        nl(130)
        mat = lay.get("material",{})
        bn = lay.get("board_number",0)
        bw = lay.get("board_width",0); bl_ = lay.get("board_length",0)
        pc = lay.get("panel_count",0); eff = lay.get("efficiency_percent",0)
        waste = lay.get("waste_area_mm2",0); used = lay.get("used_area_mm2",0)

        c.setFillGray(.92); c.rect(50,y-4,W-100,18,fill=1,stroke=0); c.setFillGray(0)
        c.setFont("Helvetica-Bold",11); c.drawString(55,y,f"Board #{bn}")
        c.setFont("Helvetica",10)
        c.drawString(130,y,f"{bw:.0f}×{bl_:.0f}mm | {mat.get('board_type',d['board_type'])} {mat.get('color_name',d['board_color'])}")
        y-=18; c.setFont("Helvetica",9)
        c.drawString(70,y,f"Panels:{pc}  Eff:{eff:.1f}%  Used:{used:.0f}mm²  Waste:{waste:.0f}mm²")
        y-=16

        panels = lay.get("panels",[])
        if panels:
            c.setFont("Helvetica-Bold",8)
            c.drawString(70,y,"Panel"); c.drawString(210,y,"Size")
            c.drawString(310,y,"Position"); c.drawString(400,y,"Rot"); c.drawString(440,y,"Grain")
            y-=3; c.setLineWidth(.3); c.line(70,y,W-70,y); y-=11
            c.setFont("Helvetica",8)
            for p in panels:
                nl(35)
                ga = p.get("grain_aligned","none")
                if hasattr(ga,"value"): ga=ga.value
                c.drawString(70,y,str(p.get("label",""))[:22])
                c.drawString(210,y,f"{p.get('width',0):.0f}×{p.get('length',0):.0f}")
                c.drawString(310,y,f"({p.get('x',0):.0f},{p.get('y',0):.0f})")
                c.drawString(400,y,"Y" if p.get("rotated") else "N")
                c.drawString(440,y,str(ga))
                y-=12
        y-=10

    # ---- edging ----
    ed = d["edging"].get("details",[])
    if ed:
        nl(100); y-=5
        c.setFont("Helvetica-Bold",13); c.drawString(50,y,"Edging Details")
        y-=5; c.line(50,y,W-50,y); y-=16
        c.setFont("Helvetica-Bold",8)
        c.drawString(50,y,"Panel"); c.drawString(210,y,"Qty")
        c.drawString(260,y,"Per pc (m)"); c.drawString(350,y,"Total (m)"); c.drawString(430,y,"Edges")
        y-=3; c.line(50,y,W-50,y); y-=11; c.setFont("Helvetica",8)
        for e in ed:
            nl()
            c.drawString(50,y,str(e.get("panel_label",""))[:22])
            c.drawString(210,y,str(e.get("quantity",0)))
            c.drawString(260,y,f"{e.get('edge_per_panel_m',0):.3f}")
            c.drawString(350,y,f"{e.get('total_edge_m',0):.3f}")
            c.drawString(430,y,str(e.get("edges_applied","")))
            y-=12
        y-=5; c.setFont("Helvetica-Bold",10)
        c.drawString(50,y,f"Total Edging: {d['edging'].get('total_meters',0):.2f} m"); y-=15

    # ---- pricing ----
    pl = d["pricing"].get("lines",[])
    if pl:
        nl(120); y-=10
        c.setFont("Helvetica-Bold",13); c.drawString(50,y,"Pricing"); y-=5
        c.line(50,y,W-50,y); y-=18; c.setFont("Helvetica",10)
        for ln in pl:
            nl()
            c.drawString(50,y,ln.get("item",""))
            c.setFont("Helvetica",9); c.drawString(130,y,ln.get("description",""))
            c.drawRightString(W-50,y,f"R {ln.get('amount',0):.2f}")
            c.setFont("Helvetica",10); y-=16
        y-=4; c.line(50,y+8,W-50,y+8)
        for lbl,key in [("Subtotal","subtotal"),("Tax","tax")]:
            c.drawString(50,y,f"{lbl}:"); c.drawRightString(W-50,y,f"R {d['pricing'].get(key,0):.2f}"); y-=16
        c.setFont("Helvetica-Bold",12)
        c.drawString(50,y,"TOTAL:"); c.drawRightString(W-50,y,f"R {d['pricing'].get('total',0):.2f}")

    # footer
    c.setFont("Helvetica",7); c.setFillGray(.5)
    c.drawString(50,20,f"PanelPro | {d['generated_at'][:10]} | Page {pg}")
    c.save(); buf.seek(0); return buf.read()


def _report_txt(d):
    lines = [
        "PANELPRO CUTTING REPORT","="*50,
        f"Report: {d['report_id']}",f"Project: {d['project']}",
        f"Customer: {d['customer']}",f"Board: {d['board_type']} {d['board_color']}",
        f"Size: {d['board_size']}","",
        f"Boards: {d['opt'].get('total_boards',0)}",
        f"Panels: {d['opt'].get('total_panels',0)}",
        f"Eff: {d['opt'].get('overall_efficiency_percent',0):.1f}%","",
    ]
    for lay in d["layouts"]:
        lines.append(f"Board #{lay.get('board_number',0)} - {lay.get('efficiency_percent',0):.1f}%")
        for p in lay.get("panels",[]):
            lines.append(f"  {p.get('label','')}: {p.get('width',0):.0f}x{p.get('length',0):.0f}")
        lines.append("")
    for ln in d["pricing"].get("lines",[]):
        lines.append(f"  {ln.get('item','')}: R{ln.get('amount',0):.2f}")
    if d["pricing"].get("total"):
        lines.append(f"  TOTAL: R{d['pricing']['total']:.2f}")
    return _txt_pdf("\n".join(lines))


# ================================================================== #
#  LABELS PDF                                                         #
# ================================================================== #
def generate_labels_pdf(payload: dict = None, stickers: list = None, **kw) -> bytes:
    data = _normalize(payload or kw) if payload else {"stickers": stickers or [], "project":"","customer":""}
    sl = data.get("stickers", stickers or [])
    sl = [_to_dict(s) if not isinstance(s,dict) else s for s in sl]
    proj = data.get("project",""); cust = data.get("customer","")
    return _labels_rl(sl,proj,cust) if _RL else _labels_txt(sl)


def _labels_rl(stickers, project, customer):
    buf = io.BytesIO(); c = rl_canvas.Canvas(buf, pagesize=A4)
    W,H = A4; LW=245; LH=100; MX=50; MY=70; CG=20; RG=12

    c.setFont("Helvetica-Bold",16); c.drawString(50,H-35,"PanelPro — Panel Labels")
    c.setFont("Helvetica",9)
    hdr = [f"Labels: {len(stickers)}"]
    if project: hdr.insert(0,f"Project: {project}")
    if customer: hdr.insert(1,f"Customer: {customer}")
    c.drawString(50,H-50," | ".join(hdr))

    row=col=0; pg=1
    for s in stickers:
        x = MX + col*(LW+CG)
        yt = H - MY - row*(LH+RG); yb = yt-LH
        if yb < 35:
            c.showPage(); pg+=1; row=0; col=0
            x = MX; yt=H-MY; yb=yt-LH

        c.setStrokeGray(.3); c.setLineWidth(.8); c.roundRect(x,yb,LW,LH,3)
        # header bar
        c.setFillGray(.15); c.rect(x,yt-16,LW,16,fill=1,stroke=0)
        c.setFillColorRGB(1,1,1); c.setFont("Helvetica-Bold",9)
        c.drawString(x+5,yt-12,str(s.get("panel_label",""))[:20])
        c.setFont("Helvetica",8)
        c.drawRightString(x+LW-5,yt-12,f"Board #{s.get('board_number',0)}")
        c.setFillGray(0)

        ty = yt-30; c.setFont("Helvetica",8)
        c.drawString(x+5,ty,f"Size: {s.get('width',0):.0f} × {s.get('length',0):.0f} mm")
        c.drawRightString(x+LW-5,ty,f"Rot: {'Y' if s.get('rotated') else 'N'}"); ty-=11
        c.drawString(x+5,ty,f"Pos: ({s.get('x',0):.0f}, {s.get('y',0):.0f})"); ty-=11
        mat = f"{s.get('board_type','')} {s.get('color_name','')}".strip()
        if s.get("thickness_mm"): mat += f" {s['thickness_mm']}mm"
        c.drawString(x+5,ty,f"Mat: {mat}"); ty-=11
        c.setFont("Helvetica-Bold",7)
        c.drawString(x+5,ty,f"SN: {s.get('serial_number','')}"); ty-=10
        if s.get("notes"):
            c.setFont("Helvetica-Oblique",7); c.drawString(x+5,ty,f"Notes: {str(s['notes'])[:35]}")

        col+=1
        if col>=2: col=0; row+=1

    c.setFont("Helvetica",7); c.setFillGray(.5)
    c.drawString(50,20,f"PanelPro | {len(stickers)} labels | Page {pg}")
    c.save(); buf.seek(0); return buf.read()


def _labels_txt(stickers):
    lines = ["PANEL LABELS","="*50,""]
    for i,s in enumerate(stickers,1):
        lines += [f"#{i} {s.get('panel_label','')}",
                  f"  SN: {s.get('serial_number','')}",
                  f"  Size: {s.get('width',0):.0f}x{s.get('length',0):.0f}mm",
                  f"  Board #{s.get('board_number',0)}",
                  f"  {s.get('board_type','')} {s.get('color_name','')}",""]
    return _txt_pdf("\n".join(lines))


# ================================================================== #
#  Minimal text PDF                                                   #
# ================================================================== #
def _txt_pdf(text: str) -> bytes:
    parts = ["BT","/F1 10 Tf","50 740 Td"]
    for line in text.split("\n"):
        safe = line.replace("\\","\\\\").replace("(","\\(").replace(")","\\)")
        parts += [f"({safe}) Tj","0 -14 Td"]
    parts.append("ET"); stream = "\n".join(parts)
    objs = [
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj",
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj",
        f"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj",
        f"4 0 obj<</Length {len(stream)}>>stream\n{stream}\nendstream\nendobj",
        "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj",
    ]
    body = "\n".join(objs); xref = len("%PDF-1.4\n")+len(body)+1
    return (f"%PDF-1.4\n{body}\nxref\n0 6\ntrailer<</Size 6/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF").encode("latin-1")
