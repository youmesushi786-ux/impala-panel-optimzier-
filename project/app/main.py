from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

# Configure logging FIRST - ensure output goes to stdout for Render
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("panelpro")

# Force flush stdout
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

logger.info("=" * 50)
logger.info("Starting PanelPro - Cutting Optimizer")
logger.info("=" * 50)

# Environment variables
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
REQUIRE_ADMIN_API_KEY = os.getenv("REQUIRE_ADMIN_API_KEY", "false").lower() == "true"
PORT = int(os.getenv("PORT", 10000))

logger.info(f"PORT: {PORT}")
logger.info(f"REQUIRE_ADMIN_API_KEY: {REQUIRE_ADMIN_API_KEY}")

# Create FastAPI app
app = FastAPI(
    title="PanelPro - Cutting Optimizer",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# --- Database setup with error handling ---
def _init_db():
    try:
        logger.info("Initializing database connection...")
        from app.db import engine
        from app.models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully!")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        logger.warning("App will continue but database features may not work")


# Initialize database
_init_db()


# --- Mount static files ---
try:
    if os.path.isdir("static"):
        app.mount("/static", StaticFiles(directory="static"), name="static")
        logger.info("Static files directory mounted")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")


# --- CORS Configuration ---
def parse_allowed_origins() -> list[str]:
    env_value = os.getenv("ALLOWED_ORIGINS", "").strip()
    if env_value:
        return [origin.strip().rstrip("/") for origin in env_value.split(",") if origin.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://impala-panel-optimzier.onrender.com",
    ]


origins = parse_allowed_origins()
logger.info(f"Allowed CORS origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Include routers with error handling ---
def _include_routers():
    try:
        from app.stock_routes import router as board_router
        from app.job_routes import router as job_router
        app.include_router(board_router, prefix="/api")
        app.include_router(job_router, prefix="/api")
        logger.info("Routers included successfully")
    except Exception as e:
        logger.error(f"Failed to include routers: {e}")
        raise


_include_routers()


# --- Database dependency ---
def get_db():
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Admin API key check ---
def require_admin_api_key(x_api_key: str | None):
    if not REQUIRE_ADMIN_API_KEY:
        return
    if not x_api_key:
        raise HTTPException(status_code=403, detail="Missing admin API key")
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin API key")


# --- Helper functions ---
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


# --- Exception handlers ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server error on {request.method} {request.url.path}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# --- Root and Health endpoints ---
@app.get("/")
async def root():
    """Root endpoint - confirms API is running"""
    return {
        "status": "ok",
        "message": "PanelPro Cutting Optimizer API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        from app.schemas import HealthResponse
        return HealthResponse()
    except Exception:
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/health")
async def api_health():
    """API health check"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# --- Board catalog endpoint ---
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


# --- BOQ Builder ---
def build_boq(request, optimization, edging, pricing):
    from app.schemas import BOQItem, BOQSummary
    from app.config import CUTTING_PRICE_PER_BOARD, EDGING_PRICE_PER_METER

    items = []
    for idx, p in enumerate(request.panels, start=1):
        edges = "".join(
            edge[0].upper()
            for edge, flag in [
                ("Top", p.edging.top),
                ("Right", p.edging.right),
                ("Bottom", p.edging.bottom),
                ("Left", p.edging.left),
            ]
            if flag
        ) or "None"

        eff_board = p.get_effective_board(request.board)

        items.append(
            BOQItem(
                item_no=idx,
                description=p.label or f"Panel {idx}",
                size=f"{p.width}×{p.length} mm",
                quantity=p.quantity,
                unit="pcs",
                edges=edges,
                board_type=eff_board.board_type,
                thickness_mm=eff_board.thickness_mm,
                company=eff_board.company,
                colour=eff_board.color_name,
                material_amount=0.0,
            )
        )

    materials = {
        "board_type": request.board.board_type,
        "board_company": request.board.company,
        "board_color": request.board.color_name,
        "board_size": f"{request.board.width_mm}×{request.board.length_mm} mm",
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


# --- Sticker tracking seed ---
def seed_sticker_tracking(db: Session, report_id: str, stickers):
    from app.models import StickerTracking
    for s in stickers:
        existing = db.query(StickerTracking).filter(
            StickerTracking.serial_number == s.serial_number
        ).first()
        if existing:
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


# --- Optimization endpoint ---
@app.post("/api/optimize")
async def api_optimize(req: dict, db: Session = Depends(get_db)):
    from app.schemas import CuttingRequest, CuttingResponse
    from app.optimizer import run_optimization
    from app.pricing import calculate_pricing
    from app.job_service import (
        aggregate_board_requirements_from_layouts,
        compute_stock_impact_from_selected_boards,
        save_job_report,
    )

    try:
        cutting_req = CuttingRequest(**req)
    except Exception as e:
        logger.error(f"Invalid request: {e}")
        raise HTTPException(status_code=422, detail=f"Invalid request: {str(e)}")

    try:
        boards, optimization, edging_summary, stickers = run_optimization(cutting_req)
    except Exception as e:
        logger.exception("Optimization failed")
        raise HTTPException(status_code=400, detail=f"Optimization failed: {str(e)}")

    pricing = calculate_pricing(cutting_req, optimization, edging_summary.total_meters)
    boq = build_boq(cutting_req, optimization, edging_summary, pricing)

    report_id = f"RPT-{uuid4().hex[:10].upper()}"
    request_json = cutting_req.model_dump()

    board_requirements = aggregate_board_requirements_from_layouts(boards)
    stock_impact = compute_stock_impact_from_selected_boards(db, board_requirements)

    save_job_report(
        db=db,
        report_id=report_id,
        request_json=request_json,
        stock_impact=stock_impact,
    )

    seed_sticker_tracking(db, report_id, stickers)

    return CuttingResponse(
        request_summary={
            "project_name": cutting_req.project_name,
            "customer_name": cutting_req.customer_name,
            "total_panels": optimization.total_panels,
        },
        optimization=optimization,
        layouts=boards,
        edging=edging_summary,
        boq=boq,
        stickers=stickers,
        stock_impact=stock_impact,
        report_id=report_id,
        generated_at=datetime.utcnow(),
    )


# --- PDF Report endpoint ---
@app.post("/api/optimize/report")
async def export_report_pdf(req: dict, db: Session = Depends(get_db)):
    from app.schemas import CuttingRequest
    from app.optimizer import run_optimization
    from app.pricing import calculate_pricing
    from app.pdf_generator import generate_report_pdf
    from app.job_service import (
        aggregate_board_requirements_from_layouts,
        compute_stock_impact_from_selected_boards,
    )

    cutting_req = CuttingRequest(**req)
    boards, optimization, edging_summary, stickers = run_optimization(cutting_req)
    pricing = calculate_pricing(cutting_req, optimization, edging_summary.total_meters)
    boq = build_boq(cutting_req, optimization, edging_summary, pricing)

    board_requirements = aggregate_board_requirements_from_layouts(boards)
    stock_impact = compute_stock_impact_from_selected_boards(db, board_requirements)

    report_id = f"RPT-{uuid4().hex[:10].upper()}"

    pdf_bytes = generate_report_pdf(
        request=cutting_req,
        layouts=boards,
        optimization=optimization,
        edging=edging_summary,
        boq=boq,
        stickers=stickers,
        stock_impact=stock_impact,
        report_id=report_id,
    )

    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# --- Labels PDF endpoint ---
@app.post("/api/optimize/labels")
async def export_labels_pdf(req: dict, db: Session = Depends(get_db)):
    from app.schemas import CuttingRequest
    from app.optimizer import run_optimization
    from app.pdf_generator import generate_labels_pdf

    cutting_req = CuttingRequest(**req)
    boards, optimization, edging_summary, stickers = run_optimization(cutting_req)

    report_id = f"RPT-{uuid4().hex[:10].upper()}"
    seed_sticker_tracking(db, report_id, stickers)

    pdf_bytes = generate_labels_pdf(stickers)

    filename = f"labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# --- Tracking endpoints ---
@app.get("/api/tracking/{serial_number}")
async def get_tracking(serial_number: str, db: Session = Depends(get_db)):
    from app.models import StickerTracking
    from app.schemas import StickerTrackingResponse

    item = db.query(StickerTracking).filter(
        StickerTracking.serial_number == serial_number
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tracking label not found")

    return StickerTrackingResponse(**serialize_tracking(item))


@app.post("/api/tracking/{serial_number}/status")
async def update_tracking_status(
    serial_number: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None),
):
    from app.models import StickerTracking

    require_admin_api_key(x_api_key)

    item = db.query(StickerTracking).filter(
        StickerTracking.serial_number == serial_number
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tracking label not found")

    new_status = payload.get("status")
    if new_status not in {"in_store", "out_for_delivery", "delivered"}:
        raise HTTPException(status_code=400, detail="Invalid status")

    item.status = new_status
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)

    return {"status": "ok", "tracking": serialize_tracking(item)}


@app.post("/api/tracking/{serial_number}/advance")
async def advance_tracking_status(
    serial_number: str,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None),
):
    from app.models import StickerTracking

    require_admin_api_key(x_api_key)

    item = db.query(StickerTracking).filter(
        StickerTracking.serial_number == serial_number
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tracking label not found")

    if item.status == "in_store":
        item.status = "out_for_delivery"
    elif item.status == "out_for_delivery":
        item.status = "delivered"
    else:
        item.status = "delivered"

    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)

    return {"status": "ok", "tracking": serialize_tracking(item)}


# --- Startup event ---
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 50)
    logger.info("PanelPro API started successfully!")
    logger.info(f"Listening on port: {PORT}")
    logger.info("API Documentation: /docs")
    logger.info("=" * 50)


# --- Shutdown event ---
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("PanelPro API shutting down...")


# --- For local development ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=True,
        log_level="info",
    )
