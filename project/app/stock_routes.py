from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import BoardItem

logger = logging.getLogger("panelpro")
router = APIRouter(tags=["boards"])


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────
class BoardCreate(BaseModel):
    board_type: str = "MDF"
    thickness_mm: float = 18.0
    color_name: str = "White"
    company: str = "Generic"
    width_mm: float = 2440.0
    length_mm: float = 1220.0
    price_per_board: float = 0.0
    quantity: int = 0
    low_stock_threshold: int = 5
    is_active: bool = True


class BoardUpdate(BaseModel):
    board_type: Optional[str] = None
    thickness_mm: Optional[float] = None
    color_name: Optional[str] = None
    company: Optional[str] = None
    width_mm: Optional[float] = None
    length_mm: Optional[float] = None
    price_per_board: Optional[float] = None
    quantity: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    is_active: Optional[bool] = None


class StockAdjustment(BaseModel):
    board_item_id: int
    quantity: int = 0
    reason: str = ""


def _row_to_dict(row: BoardItem) -> Dict[str, Any]:
    return {
        "id": row.id,
        "board_type": row.board_type,
        "thickness_mm": row.thickness_mm,
        "color_name": row.color_name,
        "company": row.company,
        "width_mm": row.width_mm,
        "length_mm": row.length_mm,
        "price_per_board": row.price_per_board,
        "quantity": row.quantity,
        "low_stock_threshold": row.low_stock_threshold,
        "is_active": row.is_active,
    }


# ─────────────────────────────────────────────
# ✅ CATALOG — MUST BE BEFORE {board_id}
# ─────────────────────────────────────────────
@router.get("/boards/catalog")
def board_catalog(db: Session = Depends(get_db)) -> Dict[str, Any]:
    items = db.query(BoardItem).filter(BoardItem.is_active.is_(True)).all()
    return {"items": [_row_to_dict(i) for i in items]}


# ─────────────────────────────────────────────
# ✅ STOCK ADD — MUST BE BEFORE {board_id}
# ─────────────────────────────────────────────
@router.post("/boards/add-stock")
def add_board_stock(
    payload: StockAdjustment,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    item = db.query(BoardItem).filter(BoardItem.id == payload.board_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board not found")

    before = item.quantity
    item.quantity += payload.quantity
    db.commit()
    db.refresh(item)

    logger.info(f"Added {payload.quantity} to board #{item.id} ({before} → {item.quantity})")
    result = _row_to_dict(item)
    result["previous_quantity"] = before
    return result


# ─────────────────────────────────────────────
# ✅ STOCK DEDUCT — MUST BE BEFORE {board_id}
# ─────────────────────────────────────────────
@router.post("/boards/deduct-stock")
def deduct_board_stock(
    payload: StockAdjustment,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    item = db.query(BoardItem).filter(BoardItem.id == payload.board_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board not found")

    before = item.quantity
    item.quantity = max(0, item.quantity - payload.quantity)
    db.commit()
    db.refresh(item)

    logger.info(f"Deducted {payload.quantity} from board #{item.id} ({before} → {item.quantity})")
    result = _row_to_dict(item)
    result["previous_quantity"] = before
    return result


# ─────────────────────────────────────────────
# ✅ TRANSACTIONS (stub)
# ─────────────────────────────────────────────
@router.get("/boards/transactions/{board_item_id}")
def get_board_transactions(
    board_item_id: int,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    item = db.query(BoardItem).filter(BoardItem.id == board_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board not found")
    # Stub — return empty for now
    return []


# ─────────────────────────────────────────────
# ✅ PRINT PDF
# ─────────────────────────────────────────────
@router.get("/boards/print-pdf")
def print_inventory_pdf(db: Session = Depends(get_db)):
    items = db.query(BoardItem).order_by(BoardItem.id).all()

    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Board Inventory Report", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ln=True)
        pdf.ln(4)

        # Table header
        pdf.set_font("Helvetica", "B", 8)
        col_w = [10, 25, 15, 25, 25, 20, 20, 20, 15, 15]
        headers = ["ID", "Type", "Thick", "Color", "Company", "W(mm)", "L(mm)", "Price", "Qty", "Active"]
        for i, h in enumerate(headers):
            pdf.cell(col_w[i], 7, h, border=1)
        pdf.ln()

        # Table rows
        pdf.set_font("Helvetica", "", 7)
        for item in items:
            row = [
                str(item.id),
                str(item.board_type or "")[:12],
                str(item.thickness_mm),
                str(item.color_name or "")[:12],
                str(item.company or "")[:12],
                str(item.width_mm),
                str(item.length_mm),
                str(item.price_per_board),
                str(item.quantity),
                "Y" if item.is_active else "N",
            ]
            for i, val in enumerate(row):
                pdf.cell(col_w[i], 6, val, border=1)
            pdf.ln()

        pdf_bytes = bytes(pdf.output())

    except ImportError:
        # fpdf2 not installed — return simple text
        lines = ["Board Inventory\n"]
        for item in items:
            lines.append(
                f"#{item.id} {item.board_type} {item.color_name} "
                f"{item.company} {item.width_mm}x{item.length_mm} "
                f"qty={item.quantity}\n"
            )
        pdf_bytes = "".join(lines).encode("utf-8")
        return Response(
            content=pdf_bytes,
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=inventory.txt"},
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=inventory.pdf"},
    )


# ─────────────────────────────────────────────
# ✅ BULK IMPORT — MUST BE BEFORE {board_id}
# ─────────────────────────────────────────────
@router.post("/boards/bulk", status_code=201)
def bulk_create_boards(
    payload: List[BoardCreate],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    created = []
    for p in payload:
        item = BoardItem(**p.model_dump())
        db.add(item)
        created.append(item)
    db.commit()
    for c in created:
        db.refresh(c)
    return {"created": len(created), "items": [_row_to_dict(c) for c in created]}


# ─────────────────────────────────────────────
# List all boards
# ─────────────────────────────────────────────
@router.get("/boards")
def list_boards(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    q = db.query(BoardItem)
    if active_only:
        q = q.filter(BoardItem.is_active.is_(True))
    items = q.order_by(BoardItem.id).all()
    return {"items": [_row_to_dict(i) for i in items]}


# ─────────────────────────────────────────────
# Create board
# ─────────────────────────────────────────────
@router.post("/boards", status_code=201)
def create_board(
    payload: BoardCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    item = BoardItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    logger.info(f"Created board #{item.id}")
    return _row_to_dict(item)


# ─────────────────────────────────────────────
# Get single board — ⚠️ MUST BE AFTER /catalog, /bulk, etc.
# ─────────────────────────────────────────────
@router.get("/boards/{board_id}")
def get_board(board_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    item = db.query(BoardItem).filter(BoardItem.id == board_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board not found")
    return _row_to_dict(item)


# ─────────────────────────────────────────────
# Update board
# ─────────────────────────────────────────────
@router.put("/boards/{board_id}")
def update_board(
    board_id: int,
    payload: BoardUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    item = db.query(BoardItem).filter(BoardItem.id == board_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board not found")

    data = payload.model_dump(exclude_unset=True)
    for key, val in data.items():
        setattr(item, key, val)

    db.commit()
    db.refresh(item)
    logger.info(f"Updated board #{item.id}")
    return _row_to_dict(item)


# ─────────────────────────────────────────────
# Delete board
# ─────────────────────────────────────────────
@router.delete("/boards/{board_id}")
def delete_board(board_id: int, db: Session = Depends(get_db)) -> Dict[str, str]:
    item = db.query(BoardItem).filter(BoardItem.id == board_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board not found")
    db.delete(item)
    db.commit()
    logger.info(f"Deleted board #{board_id}")
    return {"status": "deleted", "id": str(board_id)}
