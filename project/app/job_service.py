from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("panelpro")


def aggregate_board_requirements_from_layouts(boards) -> List[Dict[str, Any]]:
    reqs: Dict[str, Dict[str, Any]] = {}
    for bl in boards:
        # handle both pydantic model and dict
        if hasattr(bl, "material"):
            mat = bl.material if isinstance(bl.material, dict) else {}
        elif isinstance(bl, dict):
            mat = bl.get("material", {})
        else:
            mat = {}

        bid = mat.get("board_item_id", "")
        key = (
            f"{bid}|{mat.get('board_type','')}|{mat.get('thickness_mm',0)}"
            f"|{mat.get('company','')}|{mat.get('color_name','')}"
        )
        if key not in reqs:
            reqs[key] = {
                "board_item_id": bid,
                "board_type": mat.get("board_type", ""),
                "thickness_mm": mat.get("thickness_mm", 0),
                "company": mat.get("company", ""),
                "color_name": mat.get("color_name", ""),
                "price_per_board": mat.get("price_per_board", 0),
                "quantity_needed": 0,
            }
        reqs[key]["quantity_needed"] += 1
    return list(reqs.values())


def compute_stock_impact_from_selected_boards(
    db: Session, board_reqs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    from app.models import BoardItem
    impact = []
    for r in board_reqs:
        bid = r.get("board_item_id")
        needed = r.get("quantity_needed", 0)
        item = None
        if bid:
            item = db.query(BoardItem).filter(BoardItem.id == bid).first()
        stock = item.quantity if item else 0
        after = stock - needed
        impact.append({
            "board_item_id": bid,
            "board_type": r.get("board_type", ""),
            "company": r.get("company", ""),
            "color_name": r.get("color_name", ""),
            "thickness_mm": r.get("thickness_mm", 0),
            "price_per_board": r.get("price_per_board", 0),
            "quantity_needed": needed,
            "current_stock": stock,
            "stock_after": after,
            "sufficient": after >= 0,
        })
    return impact


def save_job_report(
    db: Session,
    report_id: str,
    request_json: dict,
    stock_impact: List[Dict[str, Any]],
) -> None:
    from app.models import JobReport

    if db.query(JobReport).filter(JobReport.report_id == report_id).first():
        logger.warning("Job %s already exists", report_id)
        return

    def _ser(obj):
        if isinstance(obj, dict):
            return json.dumps(obj, default=str)
        return str(obj)

    db.add(JobReport(
        report_id=report_id,
        request_json=_ser(request_json),
        stock_impact_json=_ser(stock_impact),
        confirmed=False,
    ))
    db.commit()
    logger.info("Saved job %s", report_id)


def get_job_report(db: Session, report_id: str) -> Optional[Dict]:
    from app.models import JobReport
    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job:
        return None

    def _parse(val):
        if not val:
            return None
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return val
        return val

    return {
        "id": job.id,
        "report_id": job.report_id,
        "request_json": _parse(job.request_json),
        "stock_impact_json": _parse(job.stock_impact_json),
        "confirmed": job.confirmed,
        "confirmed_at": job.confirmed_at.isoformat() if job.confirmed_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def confirm_job_report(db: Session, report_id: str) -> bool:
    from app.models import BoardItem, JobReport, StockTransaction
    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job:
        return False
    if job.confirmed:
        logger.warning("Job %s already confirmed", report_id)
        return True

    impacts = []
    if job.stock_impact_json:
        try:
            impacts = json.loads(job.stock_impact_json) if isinstance(
                job.stock_impact_json, str) else job.stock_impact_json
        except Exception:
            pass

    for imp in impacts:
        bid = imp.get("board_item_id")
        needed = imp.get("quantity_needed", 0)
        if not bid or needed <= 0:
            continue
        item = db.query(BoardItem).filter(BoardItem.id == bid).first()
        if not item:
            continue
        before = item.quantity
        item.quantity = max(0, item.quantity - needed)
        db.add(StockTransaction(
            board_item_id=bid, transaction_type="deduct",
            quantity=needed, balance_before=before,
            balance_after=item.quantity, report_id=report_id,
            reference=f"Confirmed: {report_id}",
        ))
        logger.info("Deducted %d of item %s (%d→%d)", needed, bid, before, item.quantity)

    job.confirmed = True
    job.confirmed_at = datetime.utcnow()
    db.commit()
    logger.info("Job %s confirmed", report_id)
    return True
