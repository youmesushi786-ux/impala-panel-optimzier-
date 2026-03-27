import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import BoardItem, JobReport
from app.schemas import BoardLayout, StockImpactItem

logger = logging.getLogger("panelpro.job_service")


def aggregate_board_requirements_from_layouts(
    layouts: List[BoardLayout],
) -> List[Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}

    for layout in layouts:
        key = (
            f"{layout.board_type}|{layout.thickness_mm}|"
            f"{layout.color_name}|{layout.company}|"
            f"{layout.board_width}|{layout.board_length}"
        )
        if key not in groups:
            groups[key] = {
                "board_type": layout.board_type,
                "thickness_mm": layout.thickness_mm,
                "color_name": layout.color_name,
                "company": layout.company,
                "width_mm": layout.board_width,
                "length_mm": layout.board_length,
                "count": 0,
            }
        groups[key]["count"] += 1

    return list(groups.values())


def compute_stock_impact_from_selected_boards(
    db: Session,
    board_requirements: List[Dict[str, Any]],
) -> List[StockImpactItem]:
    impact: List[StockImpactItem] = []

    for req in board_requirements:
        board_item = (
            db.query(BoardItem)
            .filter(
                BoardItem.board_type == req["board_type"],
                BoardItem.thickness_mm == req["thickness_mm"],
                BoardItem.color_name == req["color_name"],
                BoardItem.company == req["company"],
                BoardItem.width_mm == req["width_mm"],
                BoardItem.length_mm == req["length_mm"],
                BoardItem.is_active.is_(True),
            )
            .first()
        )

        if board_item:
            after = board_item.quantity - req["count"]
            impact.append(
                StockImpactItem(
                    board_item_id=board_item.id,
                    board_type=req["board_type"],
                    thickness_mm=req["thickness_mm"],
                    color_name=req["color_name"],
                    company=req["company"],
                    width_mm=req["width_mm"],
                    length_mm=req["length_mm"],
                    boards_needed=req["count"],
                    current_stock=board_item.quantity,
                    stock_after=after,
                    sufficient=after >= 0,
                )
            )
        else:
            impact.append(
                StockImpactItem(
                    board_item_id=0,
                    board_type=req["board_type"],
                    thickness_mm=req["thickness_mm"],
                    color_name=req["color_name"],
                    company=req["company"],
                    width_mm=req["width_mm"],
                    length_mm=req["length_mm"],
                    boards_needed=req["count"],
                    current_stock=0,
                    stock_after=-req["count"],
                    sufficient=False,
                )
            )

    return impact


def save_job_report(
    db: Session,
    report_id: str,
    request_json: dict,
    stock_impact: List[StockImpactItem],
) -> None:
    impact_data = [item.model_dump() for item in stock_impact]

    report = JobReport(
        report_id=report_id,
        request_json=request_json,
        stock_impact_json=impact_data,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(report)
    db.commit()
    logger.info("Job report %s saved", report_id)


def confirm_job(db: Session, report_id: str) -> bool:
    report = (
        db.query(JobReport).filter(JobReport.report_id == report_id).first()
    )
    if not report:
        return False
    if report.status == "confirmed":
        return True

    for entry in report.stock_impact_json or []:
        bid = entry.get("board_item_id", 0)
        if bid > 0:
            board_item = db.query(BoardItem).filter(BoardItem.id == bid).first()
            if board_item:
                board_item.quantity = max(
                    0, board_item.quantity - entry.get("boards_needed", 0)
                )

    report.status = "confirmed"
    report.confirmed_at = datetime.utcnow()
    db.commit()
    return True
