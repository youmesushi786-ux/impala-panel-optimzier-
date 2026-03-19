from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import SessionLocal
from .job_service import get_job_report, parse_stock_impact, confirm_job_stock_deduction
from .schemas import JobConfirmResponse

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/{report_id}")
def get_job(report_id: str, db: Session = Depends(get_db)):
    job = get_job_report(db, report_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job report not found")

    return {
        "report_id": job.report_id,
        "request_json": json.loads(job.request_json),
        "stock_impact": parse_stock_impact(job),
        "confirmed": job.confirmed,
        "confirmed_at": job.confirmed_at,
        "created_at": job.created_at,
    }


@router.post("/confirm/{report_id}", response_model=JobConfirmResponse)
def confirm_job(report_id: str, db: Session = Depends(get_db)):
    job = get_job_report(db, report_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job report not found")

    try:
        total_deducted, remaining_stock = confirm_job_stock_deduction(db, job)
        return JobConfirmResponse(
            success=True,
            message=f"Job {report_id} confirmed successfully. Stock deducted.",
            boards_deducted=total_deducted,
            remaining_stock=remaining_stock,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))