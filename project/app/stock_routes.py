from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import BoardItem

logger = logging.getLogger("panelpro")
router = APIRouter(tags=["boards"])


# ── Schemas ──────────────────────────────────────────────
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


# ── List boards ─────────────────────────────────────────
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


# ── Create board ─────────────────────────────────────────
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


# ── Get single board ────────────────────────────────────
@router.get("/boards/{board_id}")
def get_board(board_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    item = db.query(BoardItem).filter(BoardItem.id == board_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board not found")
    return _row_to_dict(item)


# ── Update board ─────────────────────────────────────────
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


# ── Delete board ─────────────────────────────────────────
@router.delete("/boards/{board_id}")
def delete_board(board_id: int, db: Session = Depends(get_db)) -> Dict[str, str]:
    item = db.query(BoardItem).filter(BoardItem.id == board_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board not found")
    db.delete(item)
    db.commit()
    logger.info(f"Deleted board #{board_id}")
    return {"status": "deleted", "id": str(board_id)}


# ── Bulk import ──────────────────────────────────────────
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
