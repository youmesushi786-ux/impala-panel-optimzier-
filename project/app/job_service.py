from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

logger = logging.getLogger("panelpro")


def aggregate_board_requirements_from_layouts(boards) -> List[Dict[str, Any]]:
    """
    Group placed boards by material info and count how many
    boards of each type are needed.
    """
    requirements: Dict[str, Dict[str, Any]] = {}

    for board_layout in boards:
        material = getattr(board_layout, "material", None) or {}

        # Handle both dict and object-style access
        if isinstance(material, dict):
            board_item_id = material.get("board_item_id", "")
            board_type = material.get("board_type", "")
            thickness = material.get("thickness_mm", 0)
            company = material.get("company", "")
            color_name = material.get("color_name", "")
            price = material.get("price_per_board", 0.0)
        else:
            board_item_id = getattr(material, "board_item_id", "")
            board_type = getattr(material, "board_type", "")
            thickness = getattr(material, "thickness_mm", 0)
            company = getattr(material, "company", "")
            color_name = getattr(material, "color_name", "")
            price = getattr(material, "price_per_board", 0.0)

        key = f"{board_item_id}|{board_type}|{thickness}|{company}|{color_name}"

        if key not in requirements:
            requirements[key] = {
                "board_item_id": board_item_id,
                "board_type": board_type,
                "thickness_mm": thickness,
                "company": company,
                "color_name": color_name,
                "price_per_board": price,
                "quantity_needed": 0,
            }
        requirements[key]["quantity_needed"] += 1

    return list(requirements.values())


def compute_stock_impact_from_selected_boards(
    db: Session,
    board_requirements: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    For each board requirement, check current stock and compute impact.
    Does NOT deduct stock — just reports what would happen.
    """
    from app.models import BoardItem

    impact: List[Dict[str, Any]] = []

    for req in board_requirements:
        board_item_id = req.get("board_item_id")
        quantity_needed = req.get("quantity_needed", 0)

        item = None
        if board_item_id:
            item = db.query(BoardItem).filter(BoardItem.id == board_item_id).first()

        current_stock = item.quantity if item else 0
        after_stock = current_stock - quantity_needed
        sufficient = after_stock >= 0

        impact.append({
            "board_item_id": board_item_id,
            "board_type": req.get("board_type", ""),
            "company": req.get("company", ""),
            "color_name": req.get("color_name", ""),
            "thickness_mm": req.get("thickness_mm", 0),
            "price_per_board": req.get("price_per_board", 0.0),
            "quantity_needed": quantity_needed,
            "current_stock": current_stock,
            "stock_after": after_stock,
            "sufficient": sufficient,
        })

    return impact


def save_job_report(
    db: Session,
    report_id: str,
    request_json: dict,
    stock_impact: List[Dict[str, Any]],
) -> None:
    """
    Persist job report to the database.
    Matches JobReport model: report_id, request_json, stock_impact_json,
    confirmed, confirmed_at, created_at, updated_at.
    NO 'status' column exists — use 'confirmed' instead.
    """
    from app.models import JobReport

    # Check if report already exists
    existing = (
        db.query(JobReport)
        .filter(JobReport.report_id == report_id)
        .first()
    )
    if existing:
        logger.warning("Job report %s already exists, skipping save", report_id)
        return

    # Serialize dicts to JSON strings since columns are Text, not JSON type
    if isinstance(request_json, dict):
        request_json_str = json.dumps(request_json, default=str)
    else:
        request_json_str = str(request_json)

    if isinstance(stock_impact, list):
        stock_impact_str = json.dumps(stock_impact, default=str)
    else:
        stock_impact_str = str(stock_impact) if stock_impact else None

    job = JobReport(
        report_id=report_id,
        request_json=request_json_str,
        stock_impact_json=stock_impact_str,
        confirmed=False,
    )
    db.add(job)
    db.commit()
    logger.info("Job report saved: %s", report_id)


def confirm_job_report(db: Session, report_id: str) -> bool:
    """
    Mark a job report as confirmed and deduct stock.
    """
    from datetime import datetime
    from app.models import BoardItem, JobReport, StockTransaction

    job = (
        db.query(JobReport)
        .filter(JobReport.report_id == report_id)
        .first()
    )
    if not job:
        return False

    if job.confirmed:
        logger.warning("Job %s already confirmed", report_id)
        return True

    # Parse stock impact
    stock_impact = []
    if job.stock_impact_json:
        try:
            stock_impact = json.loads(job.stock_impact_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Could not parse stock_impact_json for %s", report_id)

    # Deduct stock for each requirement
    for impact in stock_impact:
        board_item_id = impact.get("board_item_id")
        qty_needed = impact.get("quantity_needed", 0)

        if not board_item_id or qty_needed <= 0:
            continue

        item = db.query(BoardItem).filter(BoardItem.id == board_item_id).first()
        if not item:
            logger.warning("Board item %s not found during confirmation", board_item_id)
            continue

        balance_before = item.quantity
        item.quantity = max(0, item.quantity - qty_needed)
        balance_after = item.quantity

        # Record the transaction
        txn = StockTransaction(
            board_item_id=board_item_id,
            transaction_type="deduct",
            quantity=qty_needed,
            balance_before=balance_before,
            balance_after=balance_after,
            report_id=report_id,
            reference=f"Job confirmation: {report_id}",
            notes=f"Auto-deducted for confirmed job",
        )
        db.add(txn)

        logger.info(
            "Stock deducted: item=%s qty=%d (%d -> %d)",
            board_item_id, qty_needed, balance_before, balance_after,
        )

    # Mark confirmed
    job.confirmed = True
    job.confirmed_at = datetime.utcnow()
    db.commit()

    logger.info("Job %s confirmed, stock deducted", report_id)
    return True


def get_job_report(db: Session, report_id: str) -> dict | None:
    """
    Retrieve a job report by report_id.
    """
    from app.models import JobReport

    job = (
        db.query(JobReport)
        .filter(JobReport.report_id == report_id)
        .first()
    )
    if not job:
        return None

    # Parse JSON fields back to dicts
    request_data = None
    if job.request_json:
        try:
            request_data = json.loads(job.request_json)
        except (json.JSONDecodeError, TypeError):
            request_data = job.request_json

    stock_impact_data = None
    if job.stock_impact_json:
        try:
            stock_impact_data = json.loads(job.stock_impact_json)
        except (json.JSONDecodeError, TypeError):
            stock_impact_data = job.stock_impact_json

    return {
        "id": job.id,
        "report_id": job.report_id,
        "request_json": request_data,
        "stock_impact_json": stock_impact_data,
        "confirmed": job.confirmed,
        "confirmed_at": job.confirmed_at.isoformat() if job.confirmed_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }
