# !! DO NOT add `from __future__ import annotations` here !!

import json
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
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

logger.info("=" * 50)
logger.info("Starting PanelPro - Cutting Optimizer")
logger.info("=" * 50)

# ------------------------------------------------------------------ #
#  Environment                                                        #
# ------------------------------------------------------------------ #
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
REQUIRE_ADMIN_API_KEY = os.getenv("REQUIRE_ADMIN_API_KEY", "false").lower() == "true"
PORT = int(os.getenv("PORT", 10000))

logger.info("PORT: %s", PORT)
logger.info("REQUIRE_ADMIN_API_KEY: %s", REQUIRE_ADMIN_API_KEY)

# ------------------------------------------------------------------ #
#  FastAPI app                                                        #
# ------------------------------------------------------------------ #
app = FastAPI(
    title="PanelPro - Cutting Optimizer",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ------------------------------------------------------------------ #
#  Database bootstrap                                                 #
# ------------------------------------------------------------------ #
def _init_db() -> None:
    try:
        logger.info("Initializing database ...")
        from app.db import engine
        from app.models import Base

        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully!")
    except Exception as exc:
        logger.error("Database init error: %s", exc)
        logger.warning("App will continue but DB features may be unavailable")


_init_db()


# ------------------------------------------------------------------ #
#  Static files                                                       #
# ------------------------------------------------------------------ #
try:
    if os.path.isdir("static"):
        app.mount("/static", StaticFiles(directory="static"), name="static")
        logger.info("Static files mounted")
except Exception as exc:
    logger.warning("Could not mount static files: %s", exc)


# ------------------------------------------------------------------ #
#  CORS                                                               #
# ------------------------------------------------------------------ #
def _parse_origins() -> List[str]:
    env = os.getenv("ALLOWED_ORIGINS", "").strip()
    if env:
        return [o.strip().rstrip("/") for o in env.split(",") if o.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://impala-panel-optimzier.onrender.com",
        "https://impala-panel-optimzier-v1.onrender.com",
    ]


origins = _parse_origins()
logger.info("CORS origins: %s", origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ #
#  Routers                                                            #
# ------------------------------------------------------------------ #
def _include_routers() -> None:
    try:
        from app.stock_routes import router as board_router
        from app.job_routes import router as job_router

        app.include_router(board_router, prefix="/api")
        app.include_router(job_router, prefix="/api")
        logger.info("Routers included")
    except Exception as exc:
        logger.error("Failed to include routers: %s", exc)
        logger.warning("Some routes may be unavailable")


_include_routers()


# ------------------------------------------------------------------ #
#  DB dependency                                                      #
# ------------------------------------------------------------------ #
def get_db():
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------------------------------------------------------ #
#  Admin key helper                                                   #
# ------------------------------------------------------------------ #
def require_admin_api_key(x_api_key: Optional[str]) -> None:
    if not REQUIRE_ADMIN_API_KEY:
        return
    if not x_api_key:
        raise HTTPException(status_code=403, detail="Missing admin API key")
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin API key")


# ------------------------------------------------------------------ #
#  JSON safe serializer                                               #
# ------------------------------------------------------------------ #
def _json_safe(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if hasattr(obj, "value"):
        return obj.value
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="python")
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)


# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #
def serialize_tracking(item) -> Dict[str, Any]:
    return {
        "serial_number": item.serial_number,
        "report_id": item.report_id,
        "panel_label": item.panel_label,
        "status": item.status,
        "qr_url": item.qr_url,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "board_number": item.board_number,
    }


def _build_request_summary(cutting_req) -> Dict[str, Any]:
    return {
        "project_name": cutting_req.project_name,
        "customer_name": cutting_req.customer_name,
        "board_type": cutting_req.board.board_type,
        "board_company": cutting_req.board.company,
        "board_color": cutting_req.board.color_name,
        "board_size": f"{cutting_req.board.width_mm:.0f} x {cutting_req.board.length_mm:.0f} mm",
        "thickness_mm": cutting_req.board.thickness_mm,
        "panel_count": len(cutting_req.panels),
        "total_pieces": sum(p.quantity for p in cutting_req.panels),
        "kerf": cutting_req.options.kerf if cutting_req.options else 3.0,
        "allow_rotation": cutting_req.options.allow_rotation if cutting_req.options else True,
        "consider_grain": cutting_req.options.consider_grain if cutting_req.options else False,
    }


def _stock_impact_dicts_to_models(stock_impact_dicts: List[Dict[str, Any]]) -> list:
    from app.schemas import StockImpactItem

    items = []
    for d in stock_impact_dicts:
        items.append(StockImpactItem(
            board_item_id=d.get("board_item_id"),
            board_type=d.get("board_type", ""),
            thickness_mm=d.get("thickness_mm", 0.0),
            color_name=d.get("color_name", ""),
            company=d.get("company", ""),
            width_mm=d.get("width_mm", 0.0),
            length_mm=d.get("length_mm", 0.0),
            price_per_board=d.get("price_per_board", 0.0),
            quantity_needed=d.get("quantity_needed", 0),
            current_stock=d.get("current_stock", 0),
            stock_after=d.get("stock_after", 0),
            sufficient=d.get("sufficient", False),
        ))
    return items


def build_boq(request, optimization, edging, pricing):
    from app.config import CUTTING_PRICE_PER_BOARD, EDGING_PRICE_PER_METER
    from app.schemas import BOQItem, BOQSummary

    items: List[BOQItem] = []
    for idx, p in enumerate(request.panels, start=1):
        edges = (
            "".join(
                tag
                for tag, flag in [
                    ("T", p.edging.top),
                    ("R", p.edging.right),
                    ("B", p.edging.bottom),
                    ("L", p.edging.left),
                ]
                if flag
            )
            or "None"
        )
        items.append(
            BOQItem(
                item_no=idx,
                description=p.label or f"Panel {idx}",
                size=f"{p.width:.0f} x {p.length:.0f} mm",
                quantity=p.quantity,
                unit="pcs",
                edges=edges,
                board_type=request.board.board_type,
                thickness_mm=request.board.thickness_mm,
                company=request.board.company,
                colour=request.board.color_name,
                material_amount=0.0,
            )
        )

    materials = {
        "board_type": request.board.board_type,
        "board_company": request.board.company,
        "board_color": request.board.color_name,
        "board_size": f"{request.board.width_mm:.0f} x {request.board.length_mm:.0f} mm",
        "boards_required": optimization.total_boards,
    }

    cutting_line = next((l for l in pricing.lines if l.item == "Cutting"), None)
    edging_line = next((l for l in pricing.lines if l.item == "Edging"), None)

    services = {
        "cutting": {
            "boards": optimization.total_boards,
            "price_per_board": CUTTING_PRICE_PER_BOARD,
            "total": cutting_line.amount if cutting_line else 0.0,
        },
        "edging": {
            "meters": edging.total_meters,
            "price_per_meter": EDGING_PRICE_PER_METER,
            "total": edging_line.amount if edging_line else 0.0,
        },
    }

    return BOQSummary(
        project_name=request.project_name,
        customer_name=request.customer_name,
        date=datetime.utcnow().strftime("%Y-%m-%d"),
        items=items,
        materials=materials,
        services=services,
        pricing=pricing,
    )


def seed_sticker_tracking(db: Session, report_id: str, stickers) -> None:
    from app.models import StickerTracking

    for s in stickers:
        exists = (
            db.query(StickerTracking)
            .filter(StickerTracking.serial_number == s.serial_number)
            .first()
        )
        if exists:
            continue
        db.add(
            StickerTracking(
                serial_number=s.serial_number,
                report_id=report_id,
                panel_label=s.panel_label,
                board_number=s.board_number,
                qr_url=s.qr_url,
                status="in_store",
            )
        )
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to commit sticker tracking: %s", exc)
        raise


# ------------------------------------------------------------------ #
#  Exception handlers                                                 #
# ------------------------------------------------------------------ #
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(
        "Validation error %s %s: %s",
        request.method, request.url.path, exc.errors(),
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error(
        "Unhandled error %s %s: %s\n%s",
        request.method, request.url.path, str(exc), tb,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


# ------------------------------------------------------------------ #
#  Root / health                                                      #
# ------------------------------------------------------------------ #
@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {
        "status": "ok",
        "message": "PanelPro Cutting Optimizer API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    try:
        from app.schemas import HealthResponse
        return HealthResponse()
    except Exception:
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/health")
async def api_health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ------------------------------------------------------------------ #
#  Board catalog                                                      #
# ------------------------------------------------------------------ #
@app.get("/api/boards/catalog")
async def boards_catalog(db: Session = Depends(get_db)) -> Dict[str, Any]:
    from app.models import BoardItem

    items = db.query(BoardItem).all()
    return {
        "items": [
            {
                "id": i.id,
                "board_type": i.board_type,
                "thickness_mm": i.thickness_mm,
                "color_name": i.color_name,
                "company": i.company,
                "width_mm": i.width_mm,
                "length_mm": i.length_mm,
                "price_per_board": i.price_per_board,
                "quantity": i.quantity,
                "low_stock_threshold": i.low_stock_threshold,
                "is_active": i.is_active,
            }
            for i in items
        ]
    }


# ------------------------------------------------------------------ #
#  Optimize  (MAIN ENDPOINT)                                          #
# ------------------------------------------------------------------ #
@app.post("/api/optimize")
async def api_optimize(req: dict, db: Session = Depends(get_db)):
    from app.job_service import (
        aggregate_board_requirements_from_layouts,
        compute_stock_impact_from_selected_boards,
        save_job_report,
    )
    from app.optimizer import run_optimization
    from app.pricing import calculate_pricing
    from app.schemas import CuttingRequest, CuttingResponse

    # ---- 1. Parse ----
    try:
        cutting_req = CuttingRequest(**req)
        logger.info("CuttingRequest parsed OK")
    except Exception as exc:
        logger.exception("Invalid request payload")
        raise HTTPException(status_code=422, detail=f"Invalid request: {exc}")

    # ---- 2. Optimize ----
    try:
        boards, optimization, edging_summary, stickers = run_optimization(cutting_req)
        logger.info(
            "Optimization OK: boards=%d panels=%d eff=%.1f%%",
            optimization.total_boards,
            optimization.total_panels,
            optimization.overall_efficiency_percent,
        )
    except Exception as exc:
        logger.exception("Optimization failed")
        raise HTTPException(status_code=400, detail=f"Optimization failed: {exc}")

    # ---- 3. Pricing ----
    try:
        pricing = calculate_pricing(
            cutting_req, optimization, edging_summary.total_meters,
        )
        logger.info("Pricing OK")
    except Exception as exc:
        logger.exception("Pricing failed")
        raise HTTPException(status_code=500, detail=f"Pricing failed: {exc}")

    # ---- 4. BOQ ----
    try:
        boq = build_boq(cutting_req, optimization, edging_summary, pricing)
        logger.info("BOQ OK")
    except Exception as exc:
        logger.exception("BOQ failed")
        raise HTTPException(status_code=500, detail=f"BOQ failed: {exc}")

    report_id = f"RPT-{uuid4().hex[:10].upper()}"

    # ---- 5. Serialize request for DB ----
    try:
        request_json_dict = cutting_req.model_dump(mode="python")
        logger.info("Request serialized OK")
    except Exception as exc:
        logger.exception("Request serialization failed")
        request_json_dict = {"error": "serialization_failed"}

    # ---- 6. Stock impact ----
    stock_impact_dicts: List[Dict[str, Any]] = []
    try:
        board_requirements = aggregate_board_requirements_from_layouts(boards)
        logger.info("Board requirements: %s", board_requirements)
        stock_impact_dicts = compute_stock_impact_from_selected_boards(
            db, board_requirements,
        )
        logger.info("Stock impact rows: %d", len(stock_impact_dicts))
    except Exception as exc:
        logger.exception("Stock impact failed (non-fatal)")

    # ---- 7. Persist (non-fatal) ----
    try:
        save_job_report(
            db=db,
            report_id=report_id,
            request_json=request_json_dict,
            stock_impact=stock_impact_dicts,
        )
        logger.info("Job report saved: %s", report_id)
    except Exception as exc:
        logger.exception("Save job report failed (non-fatal)")

    # ---- 8. Sticker tracking (non-fatal) ----
    try:
        seed_sticker_tracking(db, report_id, stickers)
        logger.info("Stickers seeded: %d", len(stickers))
    except Exception as exc:
        logger.exception("Sticker tracking failed (non-fatal)")

    # ---- 9. Build response ----
    try:
        request_summary = _build_request_summary(cutting_req)
        stock_impact_models = _stock_impact_dicts_to_models(stock_impact_dicts)

        response = CuttingResponse(
            report_id=report_id,
            request_summary=request_summary,
            optimization=optimization,
            layouts=boards,
            edging=edging_summary,
            pricing=pricing,
            boq=boq,
            stickers=stickers,
            stock_impact=stock_impact_models,
            generated_at=datetime.utcnow().isoformat(),
        )

        logger.info("Response built OK for %s", report_id)
        return response

    except Exception as exc:
        logger.exception("CuttingResponse build failed, using fallback")
        try:
            fallback = _build_fallback_response(
                report_id, cutting_req, boards, optimization,
                edging_summary, pricing, boq, stickers, stock_impact_dicts,
            )
            return JSONResponse(status_code=200, content=fallback)
        except Exception as exc2:
            logger.exception("Fallback also failed")
            raise HTTPException(
                status_code=500,
                detail=f"Response build failed: {exc}; fallback: {exc2}",
            )


def _build_fallback_response(
    report_id, cutting_req, boards, optimization,
    edging_summary, pricing, boq, stickers, stock_impact_dicts,
) -> dict:
    def _safe_dump(obj):
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list):
            return [_safe_dump(i) for i in obj]
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="python")
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        return obj

    result = {
        "report_id": report_id,
        "request_summary": _build_request_summary(cutting_req),
        "optimization": _safe_dump(optimization),
        "layouts": [_safe_dump(b) for b in boards],
        "edging": _safe_dump(edging_summary),
        "pricing": _safe_dump(pricing),
        "boq": _safe_dump(boq),
        "stickers": [_safe_dump(s) for s in stickers],
        "stock_impact": stock_impact_dicts,
        "generated_at": datetime.utcnow().isoformat(),
    }
    safe_json = json.dumps(result, default=_json_safe)
    return json.loads(safe_json)


# ------------------------------------------------------------------ #
#  PDF Report endpoint                                                #
# ------------------------------------------------------------------ #
@app.post("/api/optimize/report")
async def generate_report_pdf_endpoint(payload: dict):
    """Generate cutting report PDF from optimization results."""
    try:
        from app.pdf_generator import generate_report_pdf

        logger.info(
            "Generating report PDF for %s (%d layouts)",
            payload.get("report_id", "unknown"),
            len(payload.get("layouts", [])),
        )

        pdf_bytes = generate_report_pdf(payload=payload)

        if not pdf_bytes or len(pdf_bytes) < 10:
            logger.error("PDF generation returned empty bytes")
            raise HTTPException(status_code=500, detail="PDF generation returned empty")

        report_id = payload.get("report_id", "report")
        logger.info("Report PDF generated: %d bytes", len(pdf_bytes))

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="cutting-report-{report_id}.pdf"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Report PDF generation failed")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")


# ------------------------------------------------------------------ #
#  Labels PDF endpoint                                                #
# ------------------------------------------------------------------ #
@app.post("/api/optimize/labels")
async def generate_labels_pdf_endpoint(payload: dict):
    """Generate sticker labels PDF."""
    try:
        from app.pdf_generator import generate_labels_pdf

        stickers = payload.get("stickers", [])
        logger.info("Generating labels PDF: %d stickers", len(stickers))

        pdf_bytes = generate_labels_pdf(payload=payload)

        if not pdf_bytes or len(pdf_bytes) < 10:
            logger.error("Labels PDF generation returned empty bytes")
            raise HTTPException(status_code=500, detail="Labels PDF generation returned empty")

        report_id = payload.get("report_id", "labels")
        logger.info("Labels PDF generated: %d bytes", len(pdf_bytes))

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="panel-labels-{report_id}.pdf"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Labels PDF generation failed")
        raise HTTPException(status_code=500, detail=f"Labels PDF generation failed: {exc}")


# ------------------------------------------------------------------ #
#  Sticker / Tracking endpoints                                       #
# ------------------------------------------------------------------ #
@app.get("/api/tracking/{serial_number}")
async def get_tracking(serial_number: str, db: Session = Depends(get_db)):
    from app.models import StickerTracking

    item = (
        db.query(StickerTracking)
        .filter(StickerTracking.serial_number == serial_number)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Sticker not found")
    return serialize_tracking(item)


@app.put("/api/tracking/{serial_number}")
async def update_tracking(
    serial_number: str,
    body: dict,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
):
    require_admin_api_key(x_api_key)
    from app.models import StickerTracking

    item = (
        db.query(StickerTracking)
        .filter(StickerTracking.serial_number == serial_number)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Sticker not found")

    valid_statuses = ["in_store", "dispatched", "delivered", "installed", "returned"]
    new_status = body.get("status")
    if new_status and new_status in valid_statuses:
        item.status = new_status
        item.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
        logger.info("Tracking updated: %s -> %s", serial_number, new_status)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    return serialize_tracking(item)


@app.get("/api/tracking")
async def list_tracking(
    report_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    from app.models import StickerTracking

    query = db.query(StickerTracking)
    if report_id:
        query = query.filter(StickerTracking.report_id == report_id)
    if status:
        query = query.filter(StickerTracking.status == status)

    items = query.order_by(StickerTracking.serial_number).all()
    return {"items": [serialize_tracking(i) for i in items]}


# ------------------------------------------------------------------ #
#  Job reports                                                        #
# ------------------------------------------------------------------ #
@app.get("/api/jobs")
async def list_jobs(db: Session = Depends(get_db)):
    from app.models import JobReport

    jobs = db.query(JobReport).order_by(JobReport.created_at.desc()).all()
    results = []
    for j in jobs:
        req_data = None
        if j.request_json:
            try:
                req_data = (
                    json.loads(j.request_json)
                    if isinstance(j.request_json, str)
                    else j.request_json
                )
            except (json.JSONDecodeError, TypeError):
                req_data = j.request_json

        results.append({
            "id": j.id,
            "report_id": j.report_id,
            "confirmed": j.confirmed,
            "confirmed_at": j.confirmed_at.isoformat() if j.confirmed_at else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "updated_at": j.updated_at.isoformat() if j.updated_at else None,
            "request_json": req_data,
        })
    return {"jobs": results}


@app.get("/api/jobs/{report_id}")
async def get_job(report_id: str, db: Session = Depends(get_db)):
    from app.job_service import get_job_report

    job_data = get_job_report(db, report_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job report not found")
    return job_data


# ------------------------------------------------------------------ #
#  Confirm job & deduct stock                                         #
# ------------------------------------------------------------------ #
@app.post("/api/jobs/{report_id}/confirm")
async def confirm_job(
    report_id: str,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
):
    require_admin_api_key(x_api_key)
    from app.job_service import confirm_job_report

    success = confirm_job_report(db, report_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job report not found")
    return {"detail": f"Job {report_id} confirmed and stock deducted"}


@app.delete("/api/jobs/{report_id}")
async def delete_job(
    report_id: str,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
):
    require_admin_api_key(x_api_key)
    from app.models import JobReport, StickerTracking

    db.query(StickerTracking).filter(
        StickerTracking.report_id == report_id
    ).delete()

    job = (
        db.query(JobReport)
        .filter(JobReport.report_id == report_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job report not found")

    db.delete(job)
    db.commit()
    logger.info("Deleted job report: %s", report_id)
    return {"detail": f"Job report {report_id} deleted"}


# ------------------------------------------------------------------ #
#  Stock management                                                   #
# ------------------------------------------------------------------ #
@app.post("/api/stock/deduct")
async def deduct_stock(
    body: dict,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
):
    require_admin_api_key(x_api_key)
    from app.models import BoardItem, StockTransaction

    board_item_id = body.get("board_item_id")
    quantity = body.get("quantity", 0)

    if not board_item_id or quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="board_item_id and positive quantity required",
        )

    item = db.query(BoardItem).filter(BoardItem.id == board_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board item not found")

    if item.quantity < quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock: have {item.quantity}, need {quantity}",
        )

    balance_before = item.quantity
    item.quantity -= quantity
    balance_after = item.quantity

    txn = StockTransaction(
        board_item_id=board_item_id,
        transaction_type="deduct",
        quantity=quantity,
        balance_before=balance_before,
        balance_after=balance_after,
        reference=body.get("reference"),
        notes=body.get("notes"),
    )
    db.add(txn)
    db.commit()
    db.refresh(item)

    return {
        "detail": f"Deducted {quantity} from {item.color_name}",
        "remaining": item.quantity,
    }


@app.post("/api/stock/add")
async def add_stock(
    body: dict,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None),
):
    require_admin_api_key(x_api_key)
    from app.models import BoardItem, StockTransaction

    board_item_id = body.get("board_item_id")
    quantity = body.get("quantity", 0)

    if not board_item_id or quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="board_item_id and positive quantity required",
        )

    item = db.query(BoardItem).filter(BoardItem.id == board_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board item not found")

    balance_before = item.quantity
    item.quantity += quantity
    balance_after = item.quantity

    txn = StockTransaction(
        board_item_id=board_item_id,
        transaction_type="add",
        quantity=quantity,
        balance_before=balance_before,
        balance_after=balance_after,
        reference=body.get("reference"),
        notes=body.get("notes"),
    )
    db.add(txn)
    db.commit()
    db.refresh(item)

    return {
        "detail": f"Added {quantity} to {item.color_name}",
        "total": item.quantity,
    }


@app.get("/api/stock/low")
async def low_stock(db: Session = Depends(get_db)):
    from app.models import BoardItem

    items = (
        db.query(BoardItem)
        .filter(BoardItem.quantity <= BoardItem.low_stock_threshold)
        .filter(BoardItem.is_active == True)  # noqa: E712
        .all()
    )
    return {
        "low_stock_items": [
            {
                "id": i.id,
                "board_type": i.board_type,
                "color_name": i.color_name,
                "company": i.company,
                "quantity": i.quantity,
                "low_stock_threshold": i.low_stock_threshold,
            }
            for i in items
        ]
    }


@app.get("/api/stock/transactions")
async def list_transactions(
    board_item_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    from app.models import StockTransaction

    query = db.query(StockTransaction)
    if board_item_id:
        query = query.filter(StockTransaction.board_item_id == board_item_id)

    txns = query.order_by(StockTransaction.created_at.desc()).limit(100).all()
    return {
        "transactions": [
            {
                "id": t.id,
                "board_item_id": t.board_item_id,
                "transaction_type": t.transaction_type,
                "quantity": t.quantity,
                "balance_before": t.balance_before,
                "balance_after": t.balance_after,
                "report_id": t.report_id,
                "reference": t.reference,
                "notes": t.notes,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in txns
        ]
    }


# ------------------------------------------------------------------ #
#  Re-optimize                                                        #
# ------------------------------------------------------------------ #
@app.post("/api/jobs/{report_id}/reoptimize")
async def reoptimize_job(report_id: str, db: Session = Depends(get_db)):
    from app.models import JobReport
    from app.optimizer import run_optimization
    from app.pricing import calculate_pricing
    from app.schemas import CuttingRequest, CuttingResponse

    job = (
        db.query(JobReport)
        .filter(JobReport.report_id == report_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job report not found")

    try:
        req_data = (
            json.loads(job.request_json)
            if isinstance(job.request_json, str)
            else job.request_json
        )
        cutting_req = CuttingRequest(**req_data)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not parse saved request: {exc}",
        )

    try:
        boards, optimization, edging_summary, stickers = run_optimization(cutting_req)
        pricing = calculate_pricing(
            cutting_req, optimization, edging_summary.total_meters,
        )
        boq = build_boq(cutting_req, optimization, edging_summary, pricing)

        new_report_id = f"RPT-{uuid4().hex[:10].upper()}"

        try:
            seed_sticker_tracking(db, new_report_id, stickers)
        except Exception as exc:
            logger.warning("Sticker seeding failed during reoptimize: %s", exc)

        response = CuttingResponse(
            report_id=new_report_id,
            request_summary=_build_request_summary(cutting_req),
            optimization=optimization,
            layouts=boards,
            edging=edging_summary,
            pricing=pricing,
            boq=boq,
            stickers=stickers,
            stock_impact=[],
            generated_at=datetime.utcnow().isoformat(),
        )

        logger.info("Re-optimization OK: %s -> %s", report_id, new_report_id)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Re-optimization failed")
        raise HTTPException(status_code=500, detail=f"Re-optimization failed: {exc}")


# ------------------------------------------------------------------ #
#  Debug endpoint                                                     #
# ------------------------------------------------------------------ #
@app.post("/api/optimize/debug")
async def api_optimize_debug(req: dict):
    from app.optimizer import run_optimization
    from app.schemas import CuttingRequest

    try:
        cutting_req = CuttingRequest(**req)
    except Exception as exc:
        return JSONResponse(
            status_code=422,
            content={"step": "parse", "error": str(exc)},
        )

    try:
        boards, optimization, edging_summary, stickers = run_optimization(cutting_req)
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={
                "step": "optimize",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )

    try:
        result = {
            "boards_count": len(boards),
            "summary": optimization.model_dump(mode="python"),
            "edging": edging_summary.model_dump(mode="python"),
            "stickers_count": len(stickers),
            "first_board": boards[0].model_dump(mode="python") if boards else None,
        }
        safe_json = json.dumps(result, default=_json_safe)
        return JSONResponse(content=json.loads(safe_json))
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "step": "serialize",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )


# ------------------------------------------------------------------ #
#  Startup                                                            #
# ------------------------------------------------------------------ #
@app.on_event("startup")
async def on_startup():
    logger.info("PanelPro API is ready on port %s", PORT)
    logger.info("Docs available at /docs")


# ------------------------------------------------------------------ #
#  Entry point                                                        #
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        log_level="info",
    )
