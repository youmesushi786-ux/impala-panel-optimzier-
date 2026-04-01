# !! DO NOT add `from __future__ import annotations` here !!

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
#  Logging                                                            #
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
logger.info("  PanelPro Cutting Optimizer - Starting")
logger.info("=" * 60)

# ------------------------------------------------------------------ #
#  Environment                                                        #
# ------------------------------------------------------------------ #
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
REQUIRE_ADMIN_API_KEY = (
    os.getenv("REQUIRE_ADMIN_API_KEY", "false").lower() == "true"
)
PORT = int(os.getenv("PORT", 10000))

logger.info("PORT=%s  REQUIRE_ADMIN_API_KEY=%s", PORT, REQUIRE_ADMIN_API_KEY)

# ------------------------------------------------------------------ #
#  App                                                                #
# ------------------------------------------------------------------ #
app = FastAPI(
    title="PanelPro Cutting Optimizer",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ------------------------------------------------------------------ #
#  DB bootstrap                                                       #
# ------------------------------------------------------------------ #
def _init_db() -> None:
    try:
        from app.db import engine
        from app.models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database ready")
    except Exception as exc:
        logger.error("DB init error: %s", exc)

_init_db()

# ------------------------------------------------------------------ #
#  Static files                                                       #
# ------------------------------------------------------------------ #
try:
    if os.path.isdir("static"):
        app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass

# ------------------------------------------------------------------ #
#  CORS                                                               #
# ------------------------------------------------------------------ #
_ORIGINS = [
    o.strip().rstrip("/")
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000,"
        "https://impala-panel-optimzier.onrender.com,"
        "https://impala-panel-optimzier-v1.onrender.com",
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ #
#  Routers                                                            #
# ------------------------------------------------------------------ #
def _include_routers() -> None:
    try:
        from app.stock_routes import router as stock_router
        from app.job_routes import router as job_router
        app.include_router(stock_router, prefix="/api")
        app.include_router(job_router, prefix="/api")
        logger.info("External routers included")
    except Exception as exc:
        logger.warning("Router import failed: %s", exc)

_include_routers()

# ------------------------------------------------------------------ #
#  Dependencies                                                       #
# ------------------------------------------------------------------ #
def get_db():
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _require_admin(x_api_key: Optional[str]) -> None:
    if not REQUIRE_ADMIN_API_KEY:
        return
    if not x_api_key or x_api_key != ADMIN_API_KEY:
        raise HTTPException(403, "Invalid or missing admin API key")


# ------------------------------------------------------------------ #
#  JSON helpers                                                       #
# ------------------------------------------------------------------ #
def _json_safe(obj):
    """Default handler for json.dumps — covers enums, datetimes, models."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "value"):          # Enum
        return obj.value
    if hasattr(obj, "model_dump"):     # Pydantic v2
        return obj.model_dump(mode="python")
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)


def _safe_dump(obj):
    """Recursively convert anything to a JSON-safe dict/list."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _safe_dump(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_dump(i) for i in obj]
    if hasattr(obj, "model_dump"):
        return _safe_dump(obj.model_dump(mode="python"))
    if hasattr(obj, "value"):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return {k: _safe_dump(v) for k, v in obj.__dict__.items()
                if not k.startswith("_")}
    return str(obj)


def _safe_json_response(data: dict, status: int = 200) -> JSONResponse:
    """Guaranteed-serializable JSONResponse."""
    body = json.loads(json.dumps(_safe_dump(data), default=_json_safe))
    return JSONResponse(status_code=status, content=body)


# ------------------------------------------------------------------ #
#  Small helpers                                                      #
# ------------------------------------------------------------------ #
def _build_request_summary(req) -> Dict[str, Any]:
    opts = req.options
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
        "kerf": opts.kerf if opts else 3.0,
        "allow_rotation": opts.allow_rotation if opts else True,
        "consider_grain": opts.consider_grain if opts else False,
    }


def _impact_dicts_to_models(dicts: List[Dict]) -> list:
    from app.schemas import StockImpactItem
    out = []
    for d in dicts:
        out.append(StockImpactItem(
            board_item_id=d.get("board_item_id"),
            board_type=d.get("board_type", ""),
            thickness_mm=d.get("thickness_mm", 0),
            color_name=d.get("color_name", ""),
            company=d.get("company", ""),
            width_mm=d.get("width_mm", 0),
            length_mm=d.get("length_mm", 0),
            price_per_board=d.get("price_per_board", 0),
            quantity_needed=d.get("quantity_needed", 0),
            current_stock=d.get("current_stock", 0),
            stock_after=d.get("stock_after", 0),
            sufficient=d.get("sufficient", False),
        ))
    return out


def _serialize_tracking(item) -> Dict[str, Any]:
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


# ------------------------------------------------------------------ #
#  BOQ builder                                                        #
# ------------------------------------------------------------------ #
def _build_boq(req, optimization, edging, pricing):
    from app.config import CUTTING_PRICE_PER_BOARD, EDGING_PRICE_PER_METER
    from app.schemas import BOQItem, BOQSummary

    items = []
    for idx, p in enumerate(req.panels, 1):
        edges = "".join(
            t for t, f in [
                ("T", p.edging.top), ("R", p.edging.right),
                ("B", p.edging.bottom), ("L", p.edging.left),
            ] if f
        ) or "None"
        items.append(BOQItem(
            item_no=idx,
            description=p.label or f"Panel {idx}",
            size=f"{p.width:.0f} x {p.length:.0f} mm",
            quantity=p.quantity,
            unit="pcs",
            edges=edges,
            board_type=req.board.board_type,
            thickness_mm=req.board.thickness_mm,
            company=req.board.company,
            colour=req.board.color_name,
            material_amount=0.0,
        ))

    cut_line = next((l for l in pricing.lines if l.item == "Cutting"), None)
    edge_line = next((l for l in pricing.lines if l.item == "Edging"), None)

    return BOQSummary(
        project_name=req.project_name,
        customer_name=req.customer_name,
        date=datetime.utcnow().strftime("%Y-%m-%d"),
        items=items,
        materials={
            "board_type": req.board.board_type,
            "board_company": req.board.company,
            "board_color": req.board.color_name,
            "board_size": f"{req.board.width_mm:.0f} x {req.board.length_mm:.0f} mm",
            "boards_required": optimization.total_boards,
            "price_per_board": req.board.price_per_board,
        },
        services={
            "cutting": {
                "boards": optimization.total_boards,
                "price_per_board": CUTTING_PRICE_PER_BOARD,
                "total": cut_line.amount if cut_line else 0,
            },
            "edging": {
                "meters": edging.total_meters,
                "price_per_meter": EDGING_PRICE_PER_METER,
                "total": edge_line.amount if edge_line else 0,
            },
        },
        pricing=pricing,
    )


# ------------------------------------------------------------------ #
#  Sticker seeding                                                    #
# ------------------------------------------------------------------ #
def _seed_stickers(db: Session, report_id: str, stickers) -> None:
    from app.models import StickerTracking
    count = 0
    for s in stickers:
        if db.query(StickerTracking).filter(
            StickerTracking.serial_number == s.serial_number
        ).first():
            continue
        db.add(StickerTracking(
            serial_number=s.serial_number,
            report_id=report_id,
            panel_label=s.panel_label,
            board_number=s.board_number,
            qr_url=s.qr_url,
            status="in_store",
        ))
        count += 1
    try:
        db.commit()
        logger.info("Seeded %d stickers for %s", count, report_id)
    except Exception:
        db.rollback()
        raise


# ------------------------------------------------------------------ #
#  Exception handlers                                                 #
# ------------------------------------------------------------------ #
@app.exception_handler(RequestValidationError)
async def _val_err(request: Request, exc: RequestValidationError):
    logger.warning("Validation %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(422, {"detail": exc.errors()})


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    logger.error("Error %s %s:\n%s", request.method, request.url.path,
                 traceback.format_exc())
    return JSONResponse(500, {"detail": str(exc), "type": type(exc).__name__})


# ================================================================== #
#                          ROUTES                                     #
# ================================================================== #

# ---- health -------------------------------------------------------
@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"status": "ok", "service": "PanelPro Cutting Optimizer", "version": "2.0.0"}

@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ---- board catalog ------------------------------------------------
@app.get("/api/boards/catalog")
async def boards_catalog(db: Session = Depends(get_db)):
    from app.models import BoardItem
    items = db.query(BoardItem).all()
    return {"items": [
        {
            "id": i.id, "board_type": i.board_type,
            "thickness_mm": i.thickness_mm, "color_name": i.color_name,
            "company": i.company, "width_mm": i.width_mm,
            "length_mm": i.length_mm, "price_per_board": i.price_per_board,
            "quantity": i.quantity,
            "low_stock_threshold": i.low_stock_threshold,
            "is_active": i.is_active,
        } for i in items
    ]}


# ================================================================== #
#  /api/optimize — THE MAIN ENDPOINT                                  #
# ================================================================== #
@app.post("/api/optimize")
async def api_optimize(req: dict, db: Session = Depends(get_db)):
    from app.optimizer import run_optimization
    from app.pricing import calculate_pricing
    from app.schemas import CuttingRequest
    from app.job_service import (
        aggregate_board_requirements_from_layouts,
        compute_stock_impact_from_selected_boards,
        save_job_report,
    )

    # 1 — Parse
    try:
        cutting_req = CuttingRequest(**req)
    except Exception as exc:
        raise HTTPException(422, f"Invalid request: {exc}")

    # 2 — Optimize
    try:
        boards, summary, edging, stickers = run_optimization(cutting_req)
        logger.info(
            "Optimized: %d boards, %d panels, %.1f%% eff",
            summary.total_boards, summary.total_panels,
            summary.overall_efficiency_percent,
        )
    except Exception as exc:
        logger.exception("Optimization failed")
        raise HTTPException(400, f"Optimization failed: {exc}")

    # 3 — Pricing
    try:
        pricing = calculate_pricing(cutting_req, summary, edging.total_meters)
    except Exception as exc:
        logger.exception("Pricing failed")
        raise HTTPException(500, f"Pricing failed: {exc}")

    # 4 — BOQ
    try:
        boq = _build_boq(cutting_req, summary, edging, pricing)
    except Exception as exc:
        logger.exception("BOQ failed")
        raise HTTPException(500, f"BOQ failed: {exc}")

    report_id = f"RPT-{uuid4().hex[:10].upper()}"
    request_summary = _build_request_summary(cutting_req)

    # 5 — Stock impact (non-fatal)
    stock_dicts: List[Dict] = []
    try:
        board_reqs = aggregate_board_requirements_from_layouts(boards)
        stock_dicts = compute_stock_impact_from_selected_boards(db, board_reqs)
    except Exception as exc:
        logger.warning("Stock impact error (non-fatal): %s", exc)

    # 6 — Persist job (non-fatal)
    try:
        save_job_report(
            db=db,
            report_id=report_id,
            request_json=cutting_req.model_dump(mode="python"),
            stock_impact=stock_dicts,
        )
    except Exception as exc:
        logger.warning("Job save error (non-fatal): %s", exc)

    # 7 — Sticker tracking (non-fatal)
    try:
        _seed_stickers(db, report_id, stickers)
    except Exception as exc:
        logger.warning("Sticker seed error (non-fatal): %s", exc)

    # 8 — Build response dict (guaranteed serializable)
    response_data = {
        "report_id": report_id,
        "generated_at": datetime.utcnow().isoformat(),
        "request_summary": request_summary,
        "optimization": _safe_dump(summary),
        "layouts": _safe_dump(boards),
        "edging": _safe_dump(edging),
        "pricing": _safe_dump(pricing),
        "boq": _safe_dump(boq),
        "stickers": _safe_dump(stickers),
        "stock_impact": stock_dicts,
    }

    logger.info("Response ready: %s", report_id)
    return _safe_json_response(response_data)


# ================================================================== #
#  PDF — Report                                                       #
# ================================================================== #
@app.post("/api/optimize/report")
async def pdf_report(payload: dict):
    try:
        from app.pdf_generator import generate_report_pdf
        logger.info(
            "PDF report: id=%s keys=%s layouts=%d stickers=%d",
            payload.get("report_id", "?"),
            list(payload.keys()),
            len(payload.get("layouts", payload.get("boards", []))),
            len(payload.get("stickers", [])),
        )
        pdf = generate_report_pdf(payload=payload)
        if not pdf or len(pdf) < 50:
            raise ValueError("Empty PDF output")
        rid = payload.get("report_id", "report")
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="report-{rid}.pdf"',
                "Content-Length": str(len(pdf)),
            },
        )
    except Exception as exc:
        logger.exception("PDF report failed")
        raise HTTPException(500, f"PDF failed: {exc}")


# ================================================================== #
#  PDF — Labels                                                       #
# ================================================================== #
@app.post("/api/optimize/labels")
async def pdf_labels(payload: dict):
    try:
        from app.pdf_generator import generate_labels_pdf
        stickers = payload.get("stickers", [])
        logger.info("PDF labels: %d stickers, keys=%s", len(stickers), list(payload.keys()))
        pdf = generate_labels_pdf(payload=payload)
        if not pdf or len(pdf) < 50:
            raise ValueError("Empty PDF output")
        rid = payload.get("report_id", "labels")
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="labels-{rid}.pdf"',
                "Content-Length": str(len(pdf)),
            },
        )
    except Exception as exc:
        logger.exception("PDF labels failed")
        raise HTTPException(500, f"Labels PDF failed: {exc}")


# ================================================================== #
#  Tracking                                                           #
# ================================================================== #
@app.get("/api/tracking")
async def list_tracking(
    report_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    from app.models import StickerTracking
    q = db.query(StickerTracking)
    if report_id:
        q = q.filter(StickerTracking.report_id == report_id)
    if status:
        q = q.filter(StickerTracking.status == status)
    return {"items": [_serialize_tracking(i)
                      for i in q.order_by(StickerTracking.serial_number).all()]}


@app.get("/api/tracking/{serial}")
async def get_tracking(serial: str, db: Session = Depends(get_db)):
    from app.models import StickerTracking
    item = db.query(StickerTracking).filter(
        StickerTracking.serial_number == serial).first()
    if not item:
        raise HTTPException(404, "Sticker not found")
    return _serialize_tracking(item)


@app.put("/api/tracking/{serial}")
async def update_tracking(
    serial: str, body: dict, db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
):
    _require_admin(x_api_key)
    from app.models import StickerTracking
    VALID = ["in_store", "cutting", "edging", "dispatched",
             "delivered", "installed", "returned"]
    item = db.query(StickerTracking).filter(
        StickerTracking.serial_number == serial).first()
    if not item:
        raise HTTPException(404, "Sticker not found")
    new_status = body.get("status", "")
    if new_status not in VALID:
        raise HTTPException(400, f"status must be one of {VALID}")
    item.status = new_status
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _serialize_tracking(item)


# ================================================================== #
#  Jobs                                                               #
# ================================================================== #
@app.get("/api/jobs")
async def list_jobs(db: Session = Depends(get_db)):
    from app.models import JobReport
    jobs = db.query(JobReport).order_by(JobReport.created_at.desc()).all()
    out = []
    for j in jobs:
        rd = None
        if j.request_json:
            try:
                rd = json.loads(j.request_json) if isinstance(j.request_json, str) else j.request_json
            except Exception:
                rd = j.request_json
        out.append({
            "id": j.id, "report_id": j.report_id,
            "confirmed": j.confirmed,
            "confirmed_at": j.confirmed_at.isoformat() if j.confirmed_at else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "request_json": rd,
        })
    return {"jobs": out}


@app.get("/api/jobs/{report_id}")
async def get_job(report_id: str, db: Session = Depends(get_db)):
    from app.job_service import get_job_report
    data = get_job_report(db, report_id)
    if not data:
        raise HTTPException(404, "Job not found")
    return data


@app.post("/api/jobs/{report_id}/confirm")
async def confirm_job(
    report_id: str,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
):
    _require_admin(x_api_key)
    from app.job_service import confirm_job_report
    ok = confirm_job_report(db, report_id)
    if not ok:
        raise HTTPException(404, "Job not found or already confirmed")
    return {"detail": f"Job {report_id} confirmed — stock deducted"}


@app.delete("/api/jobs/{report_id}")
async def delete_job(
    report_id: str, db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
):
    _require_admin(x_api_key)
    from app.models import JobReport, StickerTracking
    db.query(StickerTracking).filter(StickerTracking.report_id == report_id).delete()
    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    db.delete(job)
    db.commit()
    return {"detail": f"Deleted {report_id}"}


@app.post("/api/jobs/{report_id}/reoptimize")
async def reoptimize(report_id: str, db: Session = Depends(get_db)):
    from app.models import JobReport
    from app.optimizer import run_optimization
    from app.pricing import calculate_pricing
    from app.schemas import CuttingRequest

    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    try:
        rd = json.loads(job.request_json) if isinstance(job.request_json, str) else job.request_json
        cutting_req = CuttingRequest(**rd)
    except Exception as exc:
        raise HTTPException(400, f"Bad saved request: {exc}")

    boards, summary, edging, stickers = run_optimization(cutting_req)
    pricing = calculate_pricing(cutting_req, summary, edging.total_meters)
    boq = _build_boq(cutting_req, summary, edging, pricing)
    new_id = f"RPT-{uuid4().hex[:10].upper()}"
    try:
        _seed_stickers(db, new_id, stickers)
    except Exception:
        pass

    return _safe_json_response({
        "report_id": new_id,
        "generated_at": datetime.utcnow().isoformat(),
        "request_summary": _build_request_summary(cutting_req),
        "optimization": _safe_dump(summary),
        "layouts": _safe_dump(boards),
        "edging": _safe_dump(edging),
        "pricing": _safe_dump(pricing),
        "boq": _safe_dump(boq),
        "stickers": _safe_dump(stickers),
        "stock_impact": [],
    })


# ================================================================== #
#  Stock                                                              #
# ================================================================== #
@app.post("/api/stock/deduct")
async def stock_deduct(
    body: dict, db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
):
    _require_admin(x_api_key)
    from app.models import BoardItem, StockTransaction
    bid = body.get("board_item_id")
    qty = body.get("quantity", 0)
    if not bid or qty <= 0:
        raise HTTPException(400, "board_item_id and positive quantity required")
    item = db.query(BoardItem).filter(BoardItem.id == bid).first()
    if not item:
        raise HTTPException(404, "Board not found")
    if item.quantity < qty:
        raise HTTPException(400, f"Insufficient: have {item.quantity}, need {qty}")
    before = item.quantity
    item.quantity -= qty
    db.add(StockTransaction(
        board_item_id=bid, transaction_type="deduct", quantity=qty,
        balance_before=before, balance_after=item.quantity,
        reference=body.get("reference"), notes=body.get("notes"),
    ))
    db.commit(); db.refresh(item)
    return {"detail": f"Deducted {qty}", "remaining": item.quantity}


@app.post("/api/stock/add")
async def stock_add(
    body: dict, db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
):
    _require_admin(x_api_key)
    from app.models import BoardItem, StockTransaction
    bid = body.get("board_item_id")
    qty = body.get("quantity", 0)
    if not bid or qty <= 0:
        raise HTTPException(400, "board_item_id and positive quantity required")
    item = db.query(BoardItem).filter(BoardItem.id == bid).first()
    if not item:
        raise HTTPException(404, "Board not found")
    before = item.quantity
    item.quantity += qty
    db.add(StockTransaction(
        board_item_id=bid, transaction_type="add", quantity=qty,
        balance_before=before, balance_after=item.quantity,
        reference=body.get("reference"), notes=body.get("notes"),
    ))
    db.commit(); db.refresh(item)
    return {"detail": f"Added {qty}", "total": item.quantity}


@app.get("/api/stock/low")
async def stock_low(db: Session = Depends(get_db)):
    from app.models import BoardItem
    items = db.query(BoardItem).filter(
        BoardItem.quantity <= BoardItem.low_stock_threshold,
        BoardItem.is_active == True,  # noqa
    ).all()
    return {"low_stock_items": [
        {"id": i.id, "board_type": i.board_type, "color_name": i.color_name,
         "company": i.company, "quantity": i.quantity,
         "low_stock_threshold": i.low_stock_threshold}
        for i in items
    ]}


@app.get("/api/stock/transactions")
async def stock_txns(
    board_item_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    from app.models import StockTransaction
    q = db.query(StockTransaction)
    if board_item_id:
        q = q.filter(StockTransaction.board_item_id == board_item_id)
    txns = q.order_by(StockTransaction.created_at.desc()).limit(200).all()
    return {"transactions": [
        {"id": t.id, "board_item_id": t.board_item_id,
         "transaction_type": t.transaction_type, "quantity": t.quantity,
         "balance_before": t.balance_before, "balance_after": t.balance_after,
         "report_id": t.report_id, "reference": t.reference,
         "notes": t.notes,
         "created_at": t.created_at.isoformat() if t.created_at else None}
        for t in txns
    ]}


# ================================================================== #
#  Debug                                                              #
# ================================================================== #
@app.post("/api/optimize/debug")
async def optimize_debug(req: dict):
    from app.optimizer import run_optimization
    from app.schemas import CuttingRequest
    steps = {}
    try:
        cr = CuttingRequest(**req)
        steps["parse"] = "ok"
    except Exception as e:
        return JSONResponse(422, {"step": "parse", "error": str(e)})
    try:
        boards, summary, edging, stickers = run_optimization(cr)
        steps["optimize"] = {"boards": len(boards), "panels": summary.total_panels}
    except Exception as e:
        return JSONResponse(400, {"step": "optimize", "error": str(e),
                                   "trace": traceback.format_exc()})
    try:
        data = {
            "summary": _safe_dump(summary),
            "first_board": _safe_dump(boards[0]) if boards else None,
            "stickers_count": len(stickers),
        }
        steps["serialize"] = "ok"
        steps["data"] = data
    except Exception as e:
        return JSONResponse(500, {"step": "serialize", "error": str(e),
                                   "trace": traceback.format_exc()})
    return _safe_json_response(steps)


# ------------------------------------------------------------------ #
#  Startup                                                            #
# ------------------------------------------------------------------ #
@app.on_event("startup")
async def _startup():
    logger.info("PanelPro ready on port %s — docs at /docs", PORT)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, log_level="info")
