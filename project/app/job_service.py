from __future__ import annotations

import json
from datetime import datetime
from collections import defaultdict

from sqlalchemy.orm import Session

from .models import JobReport, BoardItem
from .schemas import StockImpactItem, RemainingStockItem
from .stock_service import deduct_stock, get_stock_status


def save_job_report(db: Session, report_id: str, request_json: dict, stock_impact: list[StockImpactItem]):
    job = JobReport(
        report_id=report_id,
        request_json=json.dumps(request_json),
        stock_impact_json=json.dumps([item.model_dump() for item in stock_impact]),
        confirmed=False,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job_report(db: Session, report_id: str) -> JobReport | None:
    return db.query(JobReport).filter(JobReport.report_id == report_id).first()


def parse_stock_impact(job: JobReport) -> list[dict]:
    if not job.stock_impact_json:
        return []
    return json.loads(job.stock_impact_json)


def confirm_job_stock_deduction(db: Session, job: JobReport):
    if job.confirmed:
        raise ValueError("This job has already been confirmed.")

    stock_impact = parse_stock_impact(job)
    if not stock_impact:
        raise ValueError("No stock impact found for this job.")

    remaining_stock: list[RemainingStockItem] = []
    total_deducted = 0

    item_map: dict[int, BoardItem] = {}

    for row in stock_impact:
        board_item_id = row["board_item_id"]
        required_quantity = row["required_quantity"]

        item = db.query(BoardItem).filter(BoardItem.id == board_item_id).first()
        if not item:
            raise ValueError(f"Board item {board_item_id} not found.")

        if item.quantity < required_quantity:
            raise ValueError(
                f"Insufficient stock for board item {board_item_id}. "
                f"Available: {item.quantity}, Required: {required_quantity}"
            )

        item_map[board_item_id] = item

    for row in stock_impact:
        board_item_id = row["board_item_id"]
        required_quantity = row["required_quantity"]
        item = item_map[board_item_id]

        deduct_stock(
            db=db,
            item=item,
            quantity=required_quantity,
            report_id=job.report_id,
            reference="JOB_CONFIRMATION",
            notes=f"Stock deducted for confirmed job {job.report_id}",
        )

        remaining_stock.append(
            RemainingStockItem(
                board_item_id=item.id,
                quantity=item.quantity,
            )
        )
        total_deducted += required_quantity

    job.confirmed = True
    job.confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(job)

    return total_deducted, remaining_stock


def aggregate_board_requirements_from_layouts(layouts: list) -> list[tuple[int, int]]:
    """
    Count actual boards used from optimization layouts.
    One layout row = one physical board consumed.
    """
    aggregated = defaultdict(int)

    for layout in layouts:
        material = getattr(layout, "material", None) or {}
        board_item_id = material.get("board_item_id")

        if board_item_id:
            aggregated[int(board_item_id)] += 1

    return [(board_item_id, qty) for board_item_id, qty in aggregated.items()]


def compute_stock_impact_from_selected_boards(db: Session, board_requirements: list[tuple[int, int]]) -> list[StockImpactItem]:
    result: list[StockImpactItem] = []

    for board_item_id, required_qty in board_requirements:
        item = db.query(BoardItem).filter(BoardItem.id == board_item_id).first()
        if not item:
            continue

        current_quantity = item.quantity
        projected_balance = current_quantity - required_qty
        label = f"{item.board_type} {item.thickness_mm}mm {item.color_name} {item.company} {int(item.width_mm)}x{int(item.length_mm)}"

        result.append(
            StockImpactItem(
                board_item_id=item.id,
                board_label=label,
                current_quantity=current_quantity,
                required_quantity=required_qty,
                projected_balance=projected_balance,
                price_per_board=item.price_per_board,
                stock_status=get_stock_status(item.quantity, item.low_stock_threshold),
            )
        )

    return result