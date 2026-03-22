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

from app.db import SessionLocal, engine
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
)
from app.pdf_generator import generate_report_pdf, generate_labels_pdf
from app.job_service import (
    save_job_report,
    aggregate_board_requirements_from_layouts,
    compute_stock_impact_from_selected_boards,
)
from app.stock_routes import router as board_router
from app.job_routes import router as job_router

logger = logging.getLogger("panelpro")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
REQUIRE_ADMIN_API_KEY = os.getenv("REQUIRE_ADMIN_API_KEY", "false").lower() == "true"
FRONTEND_PUBLIC_URL = os.getenv("FRONTEND_PUBLIC_URL", "http://localhost:5173").rstrip("/")

app = FastAPI(title="PanelPro - Cutting Optimizer")
Base.metadata.create_all(bind=engine)

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if _allowed_origins_env:
    origins = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
else:
    origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(board_router, prefix="/api")
app.include_router(job_router, prefix="/api")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin_api_key(x_api_key: str | None):
    if not REQUIRE_ADMIN_API_KEY:
        return

    if not x_api_key:
        raise HTTPException(status_code=403, detail="Missing admin API key")

    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin API key")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.get("/api/boards/catalog")
async def boards_catalog(db: Session = Depends(get_db)) -> Dict[str, Any]:
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


def seed_sticker_tracking(db: Session, report_id: str, stickers):
    for s in stickers:
        existing = db.query(StickerTracking).filter(StickerTracking.serial_number == s.serial_number).first()
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


@app.post("/api/optimize", response_model=CuttingResponse)
async def api_optimize(req: CuttingRequest, db: Session = Depends(get_db)) -> CuttingResponse:
    try:
        boards, optimization, edging_summary, stickers = run_optimization(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Optimization failed: {str(e)}")

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

    seed_sticker_tracking(db, report_id, stickers)

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


@app.post("/api/optimize/report")
async def export_report_pdf(req: CuttingRequest, db: Session = Depends(get_db)):
    boards, optimization, edging_summary, stickers = run_optimization(req)
    pricing = calculate_pricing(req, optimization, edging_summary.total_meters)
    boq = build_boq(req, optimization, edging_summary, pricing)

    board_requirements = aggregate_board_requirements_from_layouts(boards)
    stock_impact = compute_stock_impact_from_selected_boards(db, board_requirements)

    report_id = f"RPT-{uuid4().hex[:10].upper()}"

    pdf_bytes = generate_report_pdf(
        request=req,
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
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/api/optimize/labels")
async def export_labels_pdf(req: CuttingRequest, db: Session = Depends(get_db)):
    boards, optimization, edging_summary, stickers = run_optimization(req)

    report_id = f"RPT-{uuid4().hex[:10].upper()}"
    seed_sticker_tracking(db, report_id, stickers)

    pdf_bytes = generate_labels_pdf(stickers)

    filename = f"labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/tracking/{serial_number}", response_model=StickerTrackingResponse)
async def get_tracking(serial_number: str, db: Session = Depends(get_db)):
    item = db.query(StickerTracking).filter(StickerTracking.serial_number == serial_number).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tracking label not found")

    return StickerTrackingResponse(
        serial_number=item.serial_number,
        report_id=item.report_id,
        panel_label=item.panel_label,
        status=item.status,
        qr_url=item.qr_url,
        updated_at=item.updated_at,
        board_number=item.board_number,
    )


@app.post("/api/tracking/{serial_number}/status")
async def update_tracking_status(
    serial_number: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None),
):
    require_admin_api_key(x_api_key)

    item = db.query(StickerTracking).filter(StickerTracking.serial_number == serial_number).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tracking label not found")

    new_status = payload.get("status")
    if new_status not in {"in_store", "out_for_delivery", "delivered"}:
        raise HTTPException(status_code=400, detail="Invalid status")

    item.status = new_status
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)

    return {
        "status": "ok",
        "tracking": {
            "serial_number": item.serial_number,
            "report_id": item.report_id,
            "panel_label": item.panel_label,
            "status": item.status,
            "qr_url": item.qr_url,
            "updated_at": item.updated_at.isoformat(),
            "board_number": item.board_number,
        },
    }


@app.post("/api/tracking/{serial_number}/advance")
async def advance_tracking_status(
    serial_number: str,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None),
):
    require_admin_api_key(x_api_key)

    item = db.query(StickerTracking).filter(StickerTracking.serial_number == serial_number).first()
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

    return {
        "status": "ok",
        "tracking": {
            "serial_number": item.serial_number,
            "report_id": item.report_id,
            "panel_label": item.panel_label,
            "status": item.status,
            "qr_url": item.qr_url,
            "updated_at": item.updated_at.isoformat(),
            "board_number": item.board_number,
        },
    }
