# !! DO NOT add `from __future__ import annotations` here !!
# It turns all type annotations into strings, which breaks FastAPI's
# runtime introspection of Depends(), Header(), Query(), etc.

import logging
import os
import sys
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
    from app.stock_routes import router as board_router
    from app.job_routes import router as job_router

    app.include_router(board_router, prefix="/api")
    app.include_router(job_router, prefix="/api")
    logger.info("Routers included")


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
        "board_size": (
            f"{request.board.width_mm:.0f} x {request.board.length_mm:.0f} mm"
        ),
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
    db.commit()


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
    logger.exception("Unhandled error %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


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
#  Optimize                                                           #
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

    # --- parse ---
    try:
        cutting_req = CuttingRequest(**req)
        logger.info("CuttingRequest parsed successfully")
    except Exception as exc:
        logger.exception("Invalid request payload")
        raise HTTPException(status_code=422, detail=f"Invalid request: {exc}")

    # --- optimize ---
    try:
        boards, optimization, edging_summary, stickers = run_optimization(cutting_req)
        logger.info(
            "Optimization complete: boards=%d  panels=%d  efficiency=%.1f%%",
            optimization.total_boards,
            optimization.total_panels,
            optimization.overall_efficiency_percent,
        )
    except Exception as exc:
        logger.exception("Optimization failed")
        raise HTTPException(status_code=400, detail=f"Optimization failed: {exc}")

    # --- pricing ---
    try:
        pricing = calculate_pricing(
            cutting_req, optimization, edging_summary.total_meters,
        )
        logger.info("Pricing calculated")
    except Exception as exc:
        logger.exception("Pricing calculation failed")
        raise HTTPException(status_code=500, detail=f"Pricing failed: {exc}")

    # --- BOQ ---
    try:
        boq = build_boq(cutting_req, optimization, edging_summary, pricing)
        logger.info("BOQ built")
    except Exception as exc:
        logger.exception("BOQ build failed")
        raise HTTPException(status_code=500, detail=f"BOQ failed: {exc}")

    report_id = f"RPT-{uuid4().hex[:10].upper()}"
    request_json = cutting_req.model_dump()

    # --- stock ---
    try:
        board_requirements = aggregate_board_requirements_from_layouts(boards)
        logger.info("Board requirements: %s", board_requirements)
    except Exception as exc:
        logger.exception("Board aggregation failed")
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        stock_impact = compute_stock_impact_from_selected_boards(
            db, board_requirements,
        )
        logger.info("Stock impact rows: %d", len(stock_impact))
    except Exception as exc:
        logger.exception("Stock impact failed")
        raise HTTPException(status_code=500, detail=str(exc))

    # --- persist ---
    try:
        save_job_report(
            db=db,
            report_id=report_id,
            request_json=request_json,
            stock_impact=stock_impact,
        )
        logger.info("Job report saved: %s", report_id)
    except Exception as exc:
        logger.exception("Save job report failed")
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        seed_sticker_tracking(db, report_id, stickers)
        logger.info("Sticker tracking seeded: %d 
