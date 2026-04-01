from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import BoardItem, JobReport

logger = logging.getLogger("panelpro")


def save_job_report(
    *,
    db: Session,
    report_id: str,
    request_json: dict,
    stock_impact: list,
    project_name: str = "",
    customer_name: str = "",
) -> JobReport:
    """Persist an optimization result so it can be confirmed later."""
    report = JobReport(
        report_id=report_id,
        project_name=request_json.get("project_name", project_name),
        customer_name=request_json.get("customer_name", customer_name),
        request_json=json.dumps(request_json, default=str),
        stock_impact_json=json.dumps(stock_impact, default=str),
        status="pending",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    logger.info(f"Saved job report {report_id}")
    return report


def aggregate_board_requirements_from_layouts(
    layouts,
) -> List[Dict[str, Any]]:
    """
    Walk the list of BoardLayout objects and count how many physical boards
    are needed, grouped by material.
    """
    buckets: Dict[tuple, Dict[str, Any]] = {}

    for layout in layouts:
        mat = layout.material if isinstance(layout.material, dict) else {}
        key = (
            mat.get("board_item_id"),
            mat.get("board_type", ""),
            mat.get("thickness_mm", 0),
            mat.get("company", ""),
            mat.get("color_name", ""),
        )

        if key not in buckets:
            buckets[key] = {
                "board_item_id": mat.get("board_item_id"),
                "board_type": mat.get("board_type", ""),
                "thickness_mm": mat.get("thickness_mm", 0),
                "company": mat.get("company", ""),
                "color_name": mat.get("color_name", ""),
                "width_mm": layout.board_width,
                "length_mm": layout.board_length,
                "price_per_board": mat.get("price_per_board", 0),
                "quantity_needed": 0,
            }
        buckets[key]["quantity_needed"] += 1

    return list(buckets.values())


def compute_stock_impact_from_selected_boards(
    db: Session,
    board_requirements: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    For each material group compare required qty against current stock.
    Returns a list of dicts with before/after quantities.
    """
    impact: List[Dict[str, Any]] = []

    for req in board_requirements:
        board_item_id = req.get("board_item_id")
        current_stock = 0

        if board_item_id:
            item = db.query(BoardItem).filter(BoardItem.id == board_item_id).first()
            if item:
                current_stock = item.quantity

        needed = req["quantity_needed"]
        after = current_stock - needed

        impact.append({
            "board_item_id": board_item_id,
            "board_type": req.get("board_type", ""),
            "thickness_mm": req.get("thickness_mm", 0),
            "color_name": req.get("color_name", ""),
            "company": req.get("company", ""),
            "width_mm": req.get("width_mm", 0),
            "length_mm": req.get("length_mm", 0),
            "price_per_board": req.get("price_per_board", 0),
            "quantity_needed": needed,
            "current_stock": current_stock,
            "after_stock": max(after, 0),
            "sufficient": after >= 0,
        })

    return impact


def deduct_stock(db: Session, stock_impact: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Actually subtract quantities from BoardItem rows.
    Returns updated impact list.
    """
    results = []
    for item in stock_impact:
        board_item_id = item.get("board_item_id")
        needed = item.get("quantity_needed", 0)
        if board_item_id and needed > 0:
            board = db.query(BoardItem).filter(BoardItem.id == board_item_id).first()
            if board:
                before = board.quantity
                board.quantity = max(0, board.quantity - needed)
                results.append({
                    **item,
                    "previous_stock": before,
                    "new_stock": board.quantity,
                    "deducted": before - board.quantity,
                })
            else:
                results.append({**item, "error": "Board not found in catalog"})
        else:
            results.append({**item, "skipped": True})

    db.commit()
    return results
