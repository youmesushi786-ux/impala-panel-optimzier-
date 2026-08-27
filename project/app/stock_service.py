from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import asc

from app.models import BoardItem, OffcutItem, JobStockMovement
from app.schemas import StockImpactSummary, StockImpactItem, OffcutUsedItem, OffcutCreatedItem

logger = logging.getLogger("panelpro")


def list_board_items(db: Session) -> List[BoardItem]:
    return db.query(BoardItem).filter(BoardItem.is_active.is_(True)).order_by(
        asc(BoardItem.board_type), asc(BoardItem.thickness_mm), asc(BoardItem.company), asc(BoardItem.color_name)
    ).all()


def list_available_offcuts(db: Session, board_type: Optional[str] = None, thickness_mm: Optional[float] = None, color_name: Optional[str] = None) -> List[OffcutItem]:
    q = db.query(OffcutItem).filter(OffcutItem.status == "available", OffcutItem.is_active.is_(True))
    if board_type: q = q.filter(OffcutItem.board_type == board_type)
    if thickness_mm: q = q.filter(OffcutItem.thickness_mm == thickness_mm)
    if color_name: q = q.filter(OffcutItem.color_name == color_name)
    return q.order_by(OffcutItem.created_at.asc()).all()


def compute_stock_impact_from_selected_boards(
    db: Session,
    request,
    layouts,
    offcuts_used: List[OffcutUsedItem],
    offcuts_to_create: List[OffcutCreatedItem],
) -> StockImpactSummary:
    full_sheet_layouts = [l for l in layouts if getattr(l, "source", "full_sheet") != "offcut"]
    quantity_needed = len(full_sheet_layouts)

    current_stock = 0
    board_item_id = getattr(request.board, "board_item_id", None)
    item = None

    if board_item_id:
        item = db.query(BoardItem).filter(BoardItem.id == board_item_id).first()
    if not item:
        item = db.query(BoardItem).filter(
            BoardItem.board_type == request.board.board_type,
            BoardItem.thickness_mm == request.board.thickness_mm,
            BoardItem.color_name == request.board.color_name,
            BoardItem.company == request.board.company,
        ).first()

    if item:
        board_item_id = item.id
        current_stock = item.quantity

    stock_after = current_stock - quantity_needed

    full_sheet_impact = [
        StockImpactItem(
            board_item_id=board_item_id,
            board_type=request.board.board_type,
            thickness_mm=request.board.thickness_mm,
            color_name=request.board.color_name,
            company=request.board.company,
            width_mm=request.board.width_mm,
            length_mm=request.board.length_mm,
            price_per_board=request.board.price_per_board,
            quantity_needed=quantity_needed,
            current_stock=current_stock,
            stock_after=max(stock_after, 0),
            sufficient=stock_after >= 0,
        )
    ]

    saving = sum((o.width_mm * o.length_mm / (request.board.width_mm * request.board.length_mm)) * request.board.price_per_board for o in offcuts_used)

    return StockImpactSummary(
        full_sheets=full_sheet_impact,
        offcuts_used=offcuts_used,
        offcuts_to_create=offcuts_to_create,
        estimated_material_saving=round(saving, 2),
        warnings=[] if stock_after >= 0 else ["Insufficient full-sheet inventory in stock."]
    )
