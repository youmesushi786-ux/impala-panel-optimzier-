from __future__ import annotations

import logging
import os
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any

from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.models import Base, BoardItem, StickerTracking
from app.schemas import (
    CuttingRequest,
    CuttingResponse,
    HealthResponse,
    BOQSummary,
    BOQItem,
    StickerTrackingResponse,
)
from app.optimizer import run_optimization
from app.pricing import calculate_pricing
from app.config import (
    CUTTING_PRICE_PER_BOARD,
    EDGING_PRICE_PER_METER,
    ADMIN_API_KEY,
)
from app.pdf_generator import generate_report_pdf, generate_labels_pdf
from app.job_service import (
    save_job_report,
    aggregate_board_requirements_from_layouts,
    compute_stock_impact_from_selected_boards,
)
from app.stock_routes import router as board_router
from app.job_routes import router as job_router

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("panelpro")

# ─────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────
app = FastAPI(title="PanelPro - Cutting Optimizer")

# Create DB tables
Base.metadata.create_all(bind=engine)

# ─────────────────────────────────────────────────────────────
# Static
# ─────────────────────────────────────────────────────────────
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# ─────────────────────────────────────────────────────────────
# ✅ PRODUCTION SAFE CORS
# ─────────────────────────────────────────────────────────────
ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS")

if ALLOWED_ORIGINS_ENV:
    origins = [o.strip() for o in ALLOWED_ORIGINS_ENV.split(",") if o.strip()]
else:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "https://impala-panel-optimzier.onrender.com",
        "https://impala-panel-optimzier-v1.onrender.com",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS enabled for: {origins}")

# ─────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────
app.include_router(board_router, prefix="/api")
app.include_router(job_router, prefix="/api")

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def require_admin_api_key(x_api_key: str | None):
    if ADMIN_API_KEY and x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# ─────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", timestamp=datetime.utcnow())

# ─────────────────────────────────────────────────────────────
# Public Board Catalog
# ─────────────────────────────────────────────────────────────
@app.get("/api/boards/catalog")
async def boards_catalog(db: Session = Depends(get_db)) -> Dict[str, Any]:
    items = db.query(BoardItem).filter(BoardItem.is_active.is_(True)).all()
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

# ─────────────────────────────────────────────────────────────
# BOQ Builder
# ─────────────────────────────────────────────────────────────
def build_boq(request: CuttingRequest, optimization, edging, pricing) -> BOQSummary:
    items: list[BOQItem] = []

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

        items.append(
            BOQItem(
                item_no=idx,
                description=p.label or f"Panel {idx}",
                size=f"{p.width}×{p.length} mm",
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

    return BOQSummary(
        project_name=request.project_name,
        customer_name=request.customer_name,
        date=datetime.utcnow().strftime("%Y-%m-%d"),
        items=items,
        materials={},
        services={},
        pricing=pricing,
    )

# ─────────────────────────────────────────────────────────────
# Optimize Endpoint
# ─────────────────────────────────────────────────────────────
@app.post("/api/optimize", response_model=CuttingResponse)
async def api_optimize(
    req: CuttingRequest,
    db: Session = Depends(get_db),
) -> CuttingResponse:

    boards, optimization, edging_summary, stickers = run_optimization(req)

    pricing = calculate_pricing(req, optimization, edging_summary.total_meters)
    boq = build_boq(req, optimization, edging_summary, pricing)

    report_id = f"RPT-{uuid4().hex[:10].upper()}"
    request_json = req.model_dump()

    board_requirements = aggregate_board_requirements_from_layouts(boards)
    stock_impact = compute_stock_impact_from_selected_boards(db, board_requirements)

    save_job_report(
        db=db,
        report_id=report_id,
        request_json=request_json,
        stock_impact=stock_impact,
    )

    return CuttingResponse(
        request_summary={
            "project_name": req.project_name,
            "customer_name": req.customer_name,
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

# ─────────────────────────────────────────────────────────────
# PDF Export
# ─────────────────────────────────────────────────────────────
@app.post("/api/optimize/report")
async def export_report_pdf(req: CuttingRequest, db: Session = Depends(get_db)):
    boards, optimization, edging_summary, stickers = run_optimization(req)
    pricing = calculate_pricing(req, optimization, edging_summary.total_meters)
    boq = build_boq(req, optimization, edging_summary, pricing)

    pdf_bytes = generate_report_pdf(
        request=req,
        layouts=boards,
        optimization=optimization,
        edging=edging_summary,
        boq=boq,
        stickers=stickers,
        stock_impact=[],
        report_id=f"RPT-{uuid4().hex[:10].upper()}",
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=report.pdf"},
    )
