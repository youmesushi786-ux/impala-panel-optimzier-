# main.py
# !! DO NOT add `from __future__ import annotations` !!
# Self-contained — no circular imports possible

import json
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

# ------------------------------------------------------------------ #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("panelpro")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

logger.info("=" * 60)
logger.info("  PanelPro v2 — Starting")
logger.info("=" * 60)

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
REQUIRE_KEY = os.getenv("REQUIRE_ADMIN_API_KEY", "false").lower() == "true"
PORT = int(os.getenv("PORT", 10000))

# ------------------------------------------------------------------ #
app = FastAPI(title="PanelPro", version="2.0.0", docs_url="/docs")

# ---- DB ----
def _init_db():
    try:
        from app.db import engine
        from app.models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("DB ready")
    except Exception as e:
        logger.error("DB init: %s", e)

_init_db()

# ---- Static ----
try:
    if os.path.isdir("static"):
        app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass

# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip().rstrip("/") for o in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://localhost:3000,"
            "https://impala-panel-optimzier.onrender.com,"
            "https://impala-panel-optimzier-v1.onrender.com"
        ).split(",") if o.strip()
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routers (wrapped so crash doesn't kill app) ----
def _try_routers():
    try:
        from app.stock_routes import router as sr
        app.include_router(sr, prefix="/api")
        logger.info("stock_routes loaded")
    except Exception as e:
        logger.warning("stock_routes skip: %s", e)
    try:
        from app.job_routes import router as jr
        app.include_router(jr, prefix="/api")
        logger.info("job_routes loaded")
    except Exception as e:
        logger.warning("job_routes skip: %s", e)

_try_routers()

# ---- DB dep ----
def get_db():
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _chk_admin(key: Optional[str]):
    if not REQUIRE_KEY:
        return
    if not key or key != ADMIN_API_KEY:
        raise HTTPException(403, "Bad API key")


# ================================================================== #
#  SERIALIZATION HELPERS                                              #
# ================================================================== #
def _js(obj):
    """json.dumps default handler"""
    if isinstance(obj, datetime): return obj.isoformat()
    if hasattr(obj, "value"): return obj.value
    if hasattr(obj, "model_dump"): return obj.model_dump(mode="python")
    if isinstance(obj, (set, frozenset)): return list(obj)
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)

def _sd(obj):
    """Recursively make JSON-safe"""
    if obj is None: return None
    if isinstance(obj, (str, int, float, bool)): return obj
    if isinstance(obj, dict): return {k: _sd(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)): return [_sd(i) for i in obj]
    if hasattr(obj, "model_dump"): return _sd(obj.model_dump(mode="python"))
    if hasattr(obj, "value"): return obj.value
    if isinstance(obj, datetime): return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return {k: _sd(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)

def _jr(data, status=200):
    """Safe JSONResponse"""
    body = json.loads(json.dumps(_sd(data), default=_js))
    return JSONResponse(status_code=status, content=body)

def _st(item):
    """Serialize sticker tracking row"""
    return {
        "serial_number": item.serial_number,
        "report_id": item.report_id,
        "panel_label": item.panel_label,
        "status": item.status,
        "qr_url": item.qr_url,
        "board_number": item.board_number,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


# ================================================================== #
#  HELPERS                                                            #
# ================================================================== #
def _req_summary(req):
    o = req.options
    return {
        "project_name": req.project_name,
        "customer_name": req.customer_name,
        "board_type": req.board.board_type,
        "board_company": req.board.company,
        "board_color": req.board.color_name,
        "board_size": f"{req.board.width_mm:.0f} x {req.board.length_mm:.0f} mm",
        "thickness_mm": req.board.thickness_mm,
        "price_per_board": req.board.price_per_board,
        "panel_count": len(req.panels),
        "total_pieces": sum(p.quantity for p in req.panels),
        "kerf": o.kerf if o else 3.0,
        "allow_rotation": o.allow_rotation if o else True,
        "consider_grain": o.consider_grain if o else False,
    }

def _mk_boq(req, opt, edging, pricing):
    from app.schemas import BOQItem, BOQSummary
    try:
        from app.config import CUTTING_PRICE_PER_BOARD, EDGING_PRICE_PER_METER
    except Exception:
        CUTTING_PRICE_PER_BOARD = 50.0
        EDGING_PRICE_PER_METER = 15.0

    items = []
    for i, p in enumerate(req.panels, 1):
        edges = "".join(t for t, f in [
            ("T", p.edging.top), ("R", p.edging.right),
            ("B", p.edging.bottom), ("L", p.edging.left)] if f) or "None"
        items.append(BOQItem(
            item_no=i, description=p.label or f"Panel {i}",
            size=f"{p.width:.0f} x {p.length:.0f} mm",
            quantity=p.quantity, unit="pcs", edges=edges,
            board_type=req.board.board_type, thickness_mm=req.board.thickness_mm,
            company=req.board.company, colour=req.board.color_name,
        ))
    cl = next((l for l in pricing.lines if l.item == "Cutting"), None)
    el = next((l for l in pricing.lines if l.item == "Edging"), None)
    return BOQSummary(
        project_name=req.project_name, customer_name=req.customer_name,
        date=datetime.utcnow().strftime("%Y-%m-%d"), items=items,
        materials={"board_type": req.board.board_type, "board_company": req.board.company,
                    "board_color": req.board.color_name,
                    "board_size": f"{req.board.width_mm:.0f} x {req.board.length_mm:.0f} mm",
                    "boards_required": opt.total_boards,
                    "price_per_board": req.board.price_per_board},
        services={"cutting": {"boards": opt.total_boards,
                               "price_per_board": CUTTING_PRICE_PER_BOARD,
                               "total": cl.amount if cl else 0},
                   "edging": {"meters": edging.total_meters,
                               "price_per_meter": EDGING_PRICE_PER_METER,
                               "total": el.amount if el else 0}},
        pricing=pricing,
    )

def _seed(db, report_id, stickers):
    from app.models import StickerTracking
    n = 0
    for s in stickers:
        if db.query(StickerTracking).filter(
                StickerTracking.serial_number == s.serial_number).first():
            continue
        db.add(StickerTracking(
            serial_number=s.serial_number, report_id=report_id,
            panel_label=s.panel_label, board_number=s.board_number,
            qr_url=s.qr_url, status="in_store",
        ))
        n += 1
    db.commit()
    logger.info("Seeded %d stickers", n)

def _save_job(db, report_id, req_dict, impact):
    from app.models import JobReport
    if db.query(JobReport).filter(JobReport.report_id == report_id).first():
        return
    db.add(JobReport(
        report_id=report_id,
        request_json=json.dumps(req_dict, default=str),
        stock_impact_json=json.dumps(impact, default=str),
        confirmed=False,
    ))
    db.commit()

def _stock_impact(db, boards):
    from app.models import BoardItem
    reqs = {}
    for bl in boards:
        mat = _sd(bl).get("material", {}) if not isinstance(bl, dict) else bl.get("material", {})
        bid = mat.get("board_item_id", "")
        key = f"{bid}|{mat.get('board_type','')}|{mat.get('color_name','')}"
        if key not in reqs:
            reqs[key] = {**mat, "quantity_needed": 0}
        reqs[key]["quantity_needed"] += 1
    result = []
    for r in reqs.values():
        bid = r.get("board_item_id")
        item = db.query(BoardItem).filter(BoardItem.id == bid).first() if bid else None
        stock = item.quantity if item else 0
        after = stock - r.get("quantity_needed", 0)
        result.append({**r, "current_stock": stock, "stock_after": after, "sufficient": after >= 0})
    return result


# ================================================================== #
#  ERROR HANDLERS                                                     #
# ================================================================== #
@app.exception_handler(RequestValidationError)
async def _ve(req: Request, exc: RequestValidationError):
    return JSONResponse(422, {"detail": exc.errors()})

@app.exception_handler(Exception)
async def _ue(req: Request, exc: Exception):
    logger.error("%s %s: %s\n%s", req.method, req.url.path, exc, traceback.format_exc())
    return JSONResponse(500, {"detail": str(exc)})


# ================================================================== #
#  HEALTH                                                             #
# ================================================================== #
@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"status": "ok", "service": "PanelPro v2"}

@app.get("/health")
async def health():
    return {"status": "healthy", "ts": datetime.utcnow().isoformat()}

@app.get("/api/health")
async def api_health():
    return {"status": "healthy", "ts": datetime.utcnow().isoformat()}


# ================================================================== #
#  BOARD CATALOG                                                      #
# ================================================================== #
@app.get("/api/boards/catalog")
async def catalog(db: Session = Depends(get_db)):
    from app.models import BoardItem
    return {"items": [
        {"id": i.id, "board_type": i.board_type, "thickness_mm": i.thickness_mm,
         "color_name": i.color_name, "company": i.company,
         "width_mm": i.width_mm, "length_mm": i.length_mm,
         "price_per_board": i.price_per_board, "quantity": i.quantity,
         "low_stock_threshold": i.low_stock_threshold, "is_active": i.is_active}
        for i in db.query(BoardItem).all()
    ]}


# ================================================================== #
#  OPTIMIZE                                                           #
# ================================================================== #
@app.post("/api/optimize")
async def optimize(req: dict, db: Session = Depends(get_db)):
    from app.optimizer import run_optimization
    from app.pricing import calculate_pricing
    from app.schemas import CuttingRequest

    try:
        cr = CuttingRequest(**req)
    except Exception as e:
        raise HTTPException(422, f"Bad request: {e}")

    try:
        boards, summary, edging, stickers = run_optimization(cr)
    except Exception as e:
        logger.exception("Optimize fail")
        raise HTTPException(400, f"Optimize fail: {e}")

    try:
        pricing = calculate_pricing(cr, summary, edging.total_meters)
    except Exception as e:
        logger.exception("Pricing fail")
        raise HTTPException(500, f"Pricing fail: {e}")

    try:
        boq = _mk_boq(cr, summary, edging, pricing)
    except Exception as e:
        logger.exception("BOQ fail")
        boq = None

    rid = f"RPT-{uuid4().hex[:10].upper()}"
    rs = _req_summary(cr)

    # non-fatal DB ops
    si = []
    try:
        si = _stock_impact(db, boards)
    except Exception as e:
        logger.warning("Stock impact: %s", e)
    try:
        _save_job(db, rid, cr.model_dump(mode="python"), si)
    except Exception as e:
        logger.warning("Save job: %s", e)
    try:
        _seed(db, rid, stickers)
    except Exception as e:
        logger.warning("Seed stickers: %s", e)

    return _jr({
        "report_id": rid,
        "generated_at": datetime.utcnow().isoformat(),
        "request_summary": rs,
        "optimization": _sd(summary),
        "layouts": _sd(boards),
        "edging": _sd(edging),
        "pricing": _sd(pricing),
        "boq": _sd(boq),
        "stickers": _sd(stickers),
        "stock_impact": si,
    })


# ================================================================== #
#  PDF REPORT                                                         #
# ================================================================== #
@app.post("/api/optimize/report")
async def pdf_report(payload: dict):
    try:
        from app.pdf_generator import generate_report_pdf
        logger.info("PDF report: keys=%s layouts=%d stickers=%d",
                     list(payload.keys()),
                     len(payload.get("layouts", payload.get("boards", []))),
                     len(payload.get("stickers", [])))
        pdf = generate_report_pdf(payload=payload)
        assert pdf and len(pdf) > 50, f"PDF empty ({len(pdf) if pdf else 0} bytes)"
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition":
                                     f'attachment; filename="report-{payload.get("report_id","r")}.pdf"',
                                 "Content-Length": str(len(pdf))})
    except Exception as e:
        logger.exception("PDF report fail")
        raise HTTPException(500, f"PDF fail: {e}")


# ================================================================== #
#  PDF LABELS                                                         #
# ================================================================== #
@app.post("/api/optimize/labels")
async def pdf_labels(payload: dict):
    try:
        from app.pdf_generator import generate_labels_pdf
        logger.info("PDF labels: %d stickers", len(payload.get("stickers", [])))
        pdf = generate_labels_pdf(payload=payload)
        assert pdf and len(pdf) > 50, f"Labels empty ({len(pdf) if pdf else 0} bytes)"
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition":
                                     f'attachment; filename="labels-{payload.get("report_id","l")}.pdf"',
                                 "Content-Length": str(len(pdf))})
    except Exception as e:
        logger.exception("PDF labels fail")
        raise HTTPException(500, f"Labels fail: {e}")


# ================================================================== #
#  TRACKING                                                           #
# ================================================================== #
@app.get("/api/tracking")
async def list_track(
    report_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    from app.models import StickerTracking
    q = db.query(StickerTracking)
    if report_id: q = q.filter(StickerTracking.report_id == report_id)
    if status: q = q.filter(StickerTracking.status == status)
    return {"items": [_st(i) for i in q.order_by(StickerTracking.serial_number).all()]}

@app.get("/api/tracking/{sn}")
async def get_track(sn: str, db: Session = Depends(get_db)):
    from app.models import StickerTracking
    it = db.query(StickerTracking).filter(StickerTracking.serial_number == sn).first()
    if not it: raise HTTPException(404, "Not found")
    return _st(it)

@app.put("/api/tracking/{sn}")
async def upd_track(sn: str, body: dict, db: Session = Depends(get_db),
                     x_api_key: Optional[str] = Header(None)):
    _chk_admin(x_api_key)
    from app.models import StickerTracking
    VALID = ["in_store","cutting","edging","dispatched","delivered","installed","returned"]
    it = db.query(StickerTracking).filter(StickerTracking.serial_number == sn).first()
    if not it: raise HTTPException(404, "Not found")
    ns = body.get("status","")
    if ns not in VALID: raise HTTPException(400, f"Must be one of {VALID}")
    it.status = ns; it.updated_at = datetime.utcnow()
    db.commit(); db.refresh(it)
    return _st(it)


# ================================================================== #
#  JOBS                                                               #
# ================================================================== #
@app.get("/api/jobs")
async def list_jobs(db: Session = Depends(get_db)):
    from app.models import JobReport
    jobs = db.query(JobReport).order_by(JobReport.created_at.desc()).all()
    out = []
    for j in jobs:
        rd = None
        try:
            rd = json.loads(j.request_json) if isinstance(j.request_json, str) else j.request_json
        except Exception:
            rd = j.request_json
        out.append({
            "id": j.id, "report_id": j.report_id, "confirmed": j.confirmed,
            "confirmed_at": j.confirmed_at.isoformat() if j.confirmed_at else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "request_json": rd,
        })
    return {"jobs": out}

@app.get("/api/jobs/{rid}")
async def get_job(rid: str, db: Session = Depends(get_db)):
    from app.models import JobReport
    j = db.query(JobReport).filter(JobReport.report_id == rid).first()
    if not j: raise HTTPException(404, "Not found")
    rd = None
    try:
        rd = json.loads(j.request_json) if isinstance(j.request_json, str) else j.request_json
    except Exception:
        rd = j.request_json
    si = None
    try:
        si = json.loads(j.stock_impact_json) if isinstance(j.stock_impact_json, str) else j.stock_impact_json
    except Exception:
        si = j.stock_impact_json
    return {
        "id": j.id, "report_id": j.report_id,
        "request_json": rd, "stock_impact_json": si,
        "confirmed": j.confirmed,
        "confirmed_at": j.confirmed_at.isoformat() if j.confirmed_at else None,
        "created_at": j.created_at.isoformat() if j.created_at else None,
    }


# ================================================================== #
#  CONFIRM JOB — deduct stock                                        #
# ================================================================== #
@app.post("/api/jobs/{rid}/confirm")
async def confirm_job(rid: str, db: Session = Depends(get_db),
                       x_api_key: Optional[str] = Header(None)):
    _chk_admin(x_api_key)
    from app.models import BoardItem, JobReport, StockTransaction

    j = db.query(JobReport).filter(JobReport.report_id == rid).first()
    if not j:
        raise HTTPException(404, "Job not found")
    if j.confirmed:
        return {"detail": f"{rid} already confirmed"}

    impacts = []
    try:
        impacts = json.loads(j.stock_impact_json) if isinstance(j.stock_impact_json, str) else (j.stock_impact_json or [])
    except Exception:
        pass

    for imp in (impacts or []):
        bid = imp.get("board_item_id")
        needed = imp.get("quantity_needed", 0)
        if not bid or needed <= 0:
            continue
        item = db.query(BoardItem).filter(BoardItem.id == bid).first()
        if not item:
            continue
        before = item.quantity
        item.quantity = max(0, item.quantity - needed)
        db.add(StockTransaction(
            board_item_id=bid, transaction_type="deduct",
            quantity=needed, balance_before=before,
            balance_after=item.quantity, report_id=rid,
            reference=f"Job confirm: {rid}",
        ))
        logger.info("Deducted %d of item %s (%d→%d)", needed, bid, before, item.quantity)

    j.confirmed = True
    j.confirmed_at = datetime.utcnow()
    db.commit()
    logger.info("Job %s confirmed", rid)
    return {"detail": f"Job {rid} confirmed, stock deducted"}


@app.delete("/api/jobs/{rid}")
async def del_job(rid: str, db: Session = Depends(get_db),
                   x_api_key: Optional[str] = Header(None)):
    _chk_admin(x_api_key)
    from app.models import JobReport, StickerTracking
    db.query(StickerTracking).filter(StickerTracking.report_id == rid).delete()
    j = db.query(JobReport).filter(JobReport.report_id == rid).first()
    if not j: raise HTTPException(404, "Not found")
    db.delete(j); db.commit()
    return {"detail": f"Deleted {rid}"}


@app.post("/api/jobs/{rid}/reoptimize")
async def reopt(rid: str, db: Session = Depends(get_db)):
    from app.models import JobReport
    from app.optimizer import run_optimization
    from app.pricing import calculate_pricing
    from app.schemas import CuttingRequest

    j = db.query(JobReport).filter(JobReport.report_id == rid).first()
    if not j: raise HTTPException(404, "Not found")
    try:
        rd = json.loads(j.request_json) if isinstance(j.request_json, str) else j.request_json
        cr = CuttingRequest(**rd)
    except Exception as e:
        raise HTTPException(400, f"Bad saved data: {e}")

    boards, summary, edging, stickers = run_optimization(cr)
    pricing = calculate_pricing(cr, summary, edging.total_meters)
    boq = _mk_boq(cr, summary, edging, pricing)
    nid = f"RPT-{uuid4().hex[:10].upper()}"
    try: _seed(db, nid, stickers)
    except Exception: pass

    return _jr({
        "report_id": nid, "generated_at": datetime.utcnow().isoformat(),
        "request_summary": _req_summary(cr),
        "optimization": _sd(summary), "layouts": _sd(boards),
        "edging": _sd(edging), "pricing": _sd(pricing),
        "boq": _sd(boq), "stickers": _sd(stickers), "stock_impact": [],
    })


# ================================================================== #
#  STOCK                                                              #
# ================================================================== #
@app.post("/api/stock/deduct")
async def s_deduct(body: dict, db: Session = Depends(get_db),
                    x_api_key: Optional[str] = Header(None)):
    _chk_admin(x_api_key)
    from app.models import BoardItem, StockTransaction
    bid = body.get("board_item_id"); qty = body.get("quantity", 0)
    if not bid or qty <= 0: raise HTTPException(400, "Need board_item_id + qty")
    it = db.query(BoardItem).filter(BoardItem.id == bid).first()
    if not it: raise HTTPException(404, "Board not found")
    if it.quantity < qty: raise HTTPException(400, f"Have {it.quantity}, need {qty}")
    b = it.quantity; it.quantity -= qty
    db.add(StockTransaction(board_item_id=bid, transaction_type="deduct",
                             quantity=qty, balance_before=b, balance_after=it.quantity,
                             reference=body.get("reference"), notes=body.get("notes")))
    db.commit(); db.refresh(it)
    return {"detail": f"Deducted {qty}", "remaining": it.quantity}

@app.post("/api/stock/add")
async def s_add(body: dict, db: Session = Depends(get_db),
                 x_api_key: Optional[str] = Header(None)):
    _chk_admin(x_api_key)
    from app.models import BoardItem, StockTransaction
    bid = body.get("board_item_id"); qty = body.get("quantity", 0)
    if not bid or qty <= 0: raise HTTPException(400, "Need board_item_id + qty")
    it = db.query(BoardItem).filter(BoardItem.id == bid).first()
    if not it: raise HTTPException(404, "Board not found")
    b = it.quantity; it.quantity += qty
    db.add(StockTransaction(board_item_id=bid, transaction_type="add",
                             quantity=qty, balance_before=b, balance_after=it.quantity,
                             reference=body.get("reference"), notes=body.get("notes")))
    db.commit(); db.refresh(it)
    return {"detail": f"Added {qty}", "total": it.quantity}

@app.get("/api/stock/low")
async def s_low(db: Session = Depends(get_db)):
    from app.models import BoardItem
    items = db.query(BoardItem).filter(
        BoardItem.quantity <= BoardItem.low_stock_threshold,
        BoardItem.is_active == True).all()
    return {"low_stock_items": [
        {"id": i.id, "board_type": i.board_type, "color_name": i.color_name,
         "company": i.company, "quantity": i.quantity,
         "low_stock_threshold": i.low_stock_threshold} for i in items
    ]}

@app.get("/api/stock/transactions")
async def s_txns(board_item_id: Optional[int] = None, db: Session = Depends(get_db)):
    from app.models import StockTransaction
    q = db.query(StockTransaction)
    if board_item_id: q = q.filter(StockTransaction.board_item_id == board_item_id)
    return {"transactions": [
        {"id": t.id, "board_item_id": t.board_item_id,
         "transaction_type": t.transaction_type, "quantity": t.quantity,
         "balance_before": t.balance_before, "balance_after": t.balance_after,
         "report_id": t.report_id, "reference": t.reference, "notes": t.notes,
         "created_at": t.created_at.isoformat() if t.created_at else None}
        for t in q.order_by(StockTransaction.created_at.desc()).limit(200).all()
    ]}


# ================================================================== #
#  DEBUG                                                              #
# ================================================================== #
@app.post("/api/optimize/debug")
async def dbg(req: dict):
    from app.schemas import CuttingRequest
    from app.optimizer import run_optimization
    try:
        cr = CuttingRequest(**req)
    except Exception as e:
        return JSONResponse(422, {"step": "parse", "error": str(e)})
    try:
        boards, s, e, st = run_optimization(cr)
    except Exception as e:
        return JSONResponse(400, {"step": "optimize", "error": str(e), "tb": traceback.format_exc()})
    try:
        return _jr({"boards": len(boards), "panels": s.total_panels,
                     "eff": s.overall_efficiency_percent, "stickers": len(st),
                     "first": _sd(boards[0]) if boards else None})
    except Exception as e:
        return JSONResponse(500, {"step": "serialize", "error": str(e)})


# ================================================================== #
@app.on_event("startup")
async def _up():
    logger.info("PanelPro ready port=%s docs=/docs", PORT)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, log_level="info")
