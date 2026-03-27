import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import BoardItem

logger = logging.getLogger("panelpro.stock")
router = APIRouter(tags=["Stock Management"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/boards")
async def list_boards(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = db.query(BoardItem)
    if active_only:
        query = query.filter(BoardItem.is_active.is_(True))
    items = query.all()
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


@router.post("/boards")
async def create_board(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    board = BoardItem(
        board_type=payload.get("board_type", "MDF"),
        thickness_mm=payload.get("thickness_mm", 18.0),
        color_name=payload.get("color_name", "White"),
        company=payload.get("company", "Generic"),
        width_mm=payload.get("width_mm", 2440.0),
        length_mm=payload.get("length_mm", 1220.0),
        price_per_board=payload.get("price_per_board", 0.0),
        quantity=payload.get("quantity", 0),
        low_stock_threshold=payload.get("low_stock_threshold", 5),
        is_active=payload.get("is_active", True),
    )
    db.add(board)
    db.commit()
    db.refresh(board)
    return {"id": board.id, "status": "created"}


@router.put("/boards/{board_id}")
async def update_board(
    board_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    board = db.query(BoardItem).filter(BoardItem.id == board_id).first()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    updatable = {
        "board_type",
        "thickness_mm",
        "color_name",
        "company",
        "width_mm",
        "length_mm",
        "price_per_board",
        "quantity",
        "low_stock_threshold",
        "is_active",
    }
    for key in updatable:
        if key in payload:
            setattr(board, key, payload[key])

    db.commit()
    db.refresh(board)
    return {"id": board.id, "status": "updated"}


@router.delete("/boards/{board_id}")
async def delete_board(board_id: int, db: Session = Depends(get_db)):
    board = db.query(BoardItem).filter(BoardItem.id == board_id).first()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    db.delete(board)
    db.commit()
    return {"id": board_id, "status": "deleted"}


@router.get("/boards/low-stock")
async def low_stock_boards(db: Session = Depends(get_db)):
    items = (
        db.query(BoardItem)
        .filter(
            BoardItem.is_active.is_(True),
            BoardItem.quantity <= BoardItem.low_stock_threshold,
        )
        .all()
    )
    return {
        "items": [
            {
                "id": i.id,
                "board_type": i.board_type,
                "thickness_mm": i.thickness_mm,
                "color_name": i.color_name,
                "company": i.company,
                "quantity": i.quantity,
                "low_stock_threshold": i.low_stock_threshold,
            }
            for i in items
        ]
    }
