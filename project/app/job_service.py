from __future__ import annotations

import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import JobReport, BoardItem, OffcutItem, JobStockMovement
from app.schemas import StockImpactSummary, CuttingRequest

logger = logging.getLogger("panelpro")


def save_job_report(
    db: Session,
    report_id: str,
    request: CuttingRequest,
    stock_impact_detail: StockImpactSummary,
    total_boards: int = 0,
    total_offcuts_used: int = 0,
    total_offcuts_created: int = 0,
    efficiency_percent: float = 0.0,
) -> JobReport:
    # Flat legacy full sheet impact list for backward compatibility
    legacy_impact = [i.model_dump() for i in stock_impact_detail.full_sheets]

    job = JobReport(
        report_id=report_id,
        project_name=request.project_name,
        customer_name=request.customer_name,
        request_json=request.model_dump_json(),
        stock_impact_json=json.dumps(legacy_impact, default=str),
        result_summary_json=stock_impact_detail.model_dump_json(),
        status="pending",
        total_boards_used=total_boards,
        total_offcuts_used=total_offcuts_used,
        total_offcuts_created=total_offcuts_created,
        efficiency_percent=efficiency_percent,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info(f"Saved job report #{report_id}")
    return job


def confirm_job_and_update_stock(db: Session, report_id: str) -> JobReport:
    """
    ATOMIC TRANSACTION:
    1. Deducts full-sheet stock from BoardItem.
    2. Marks used OffcutItems as consumed.
    3. Inserts new OffcutItems generated from waste.
    4. Logs all inventory transactions in JobStockMovement.
    """
    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job:
        raise ValueError("Job report not found")
    if job.status == "confirmed":
        raise ValueError("Job is already confirmed")
    if job.status == "cancelled":
        raise ValueError("Cannot confirm a cancelled job")

    impact_detail = StockImpactSummary.model_validate_json(job.result_summary_json)

    # 1. Deduct Full Sheets
    for sheet in impact_detail.full_sheets:
        if sheet.quantity_needed > 0:
            board = None
            if sheet.board_item_id:
                board = db.query(BoardItem).filter(BoardItem.id == sheet.board_item_id).first()
            if not board:
                board = db.query(BoardItem).filter(
                    BoardItem.board_type == sheet.board_type,
                    BoardItem.thickness_mm == sheet.thickness_mm,
                    BoardItem.color_name == sheet.color_name,
                    BoardItem.company == sheet.company,
                ).first()

            if board:
                board.quantity = max(0, board.quantity - sheet.quantity_needed)
                db.add(JobStockMovement(
                    report_id=report_id, movement_type="consume_full_board",
                    board_type=sheet.board_type, thickness_mm=sheet.thickness_mm,
                    color_name=sheet.color_name, company=sheet.company,
                    width_mm=sheet.width_mm, length_mm=sheet.length_mm,
                    quantity=sheet.quantity_needed, board_item_id=board.id
                ))

    # 2. Consume Used Offcuts
    for used in impact_detail.offcuts_used:
        if used.offcut_id:
            offcut = db.query(OffcutItem).filter(OffcutItem.id == used.offcut_id).first()
            if offcut:
                offcut.status = "consumed"
                offcut.consumed_at = datetime.utcnow()
                offcut.consumed_report_id = report_id
                db.add(JobStockMovement(
                    report_id=report_id, movement_type="consume_offcut",
                    board_type=offcut.board_type, thickness_mm=offcut.thickness_mm,
                    color_name=offcut.color_name, company=offcut.company,
                    width_mm=offcut.width_mm, length_mm=offcut.length_mm,
                    quantity=1, offcut_item_id=offcut.id
                ))

    # 3. Create New Remnants from Waste
    counter = 1
    for new_off in impact_detail.offcuts_to_create:
        code = f"OFF-{datetime.utcnow().strftime('%Y%m%d')}-{str(job.id).zfill(4)}-{counter:02d}"
        db_offcut = OffcutItem(
            offcut_code=code, board_type=new_off.board_type,
            thickness_mm=new_off.thickness_mm, color_name=new_off.color_name,
            company=new_off.company, width_mm=new_off.width_mm,
            length_mm=new_off.length_mm, area_mm2=new_off.area_mm2,
            status="available", source_report_id=report_id,
            source_board_number=new_off.source_board_number,
        )
        db.add(db_offcut)
        db.flush()

        db.add(JobStockMovement(
            report_id=report_id, movement_type="create_offcut",
            board_type=new_off.board_type, thickness_mm=new_off.thickness_mm,
            color_name=new_off.color_name, company=new_off.company,
            width_mm=new_off.width_mm, length_mm=new_off.length_mm,
            quantity=1, offcut_item_id=db_offcut.id
        ))
        counter += 1

    job.status = "confirmed"
    job.confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


# Keep legacy deduct_stock function for backward compatibility
def deduct_stock(db: Session, stock_impact: list) -> list:
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
