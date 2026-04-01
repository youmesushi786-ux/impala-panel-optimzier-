from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import JobReport, BoardItem
from app.job_service import deduct_stock

logger = logging.getLogger("panelpro")
router = APIRouter(tags=["jobs"])


def _job_to_dict(job: JobReport) -> Dict[str, Any]:
    return {
        "report_id": job.report_id,
        "project_name": job.project_name,
        "customer_name": job.customer_name,
        "status": job.status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "confirmed_at": job.confirmed_at.isoformat() if job.confirmed_at else None,
    }


# ── List all jobs ────────────────────────────────────────
@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)) -> Dict[str, Any]:
    jobs = db.query(JobReport).order_by(JobReport.created_at.desc()).all()
    return {"jobs": [_job_to_dict(j) for j in jobs]}


# ── Get single job ───────────────────────────────────────
@router.get("/jobs/{report_id}")
def get_job(report_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job report not found")

    result = _job_to_dict(job)
    result["stock_impact"] = json.loads(job.stock_impact_json) if job.stock_impact_json else []
    return result


# ──────────────────────────────────────────────────────────
#  ★  THIS IS THE MISSING ROUTE THAT CAUSED THE 404  ★
# ──────────────────────────────────────────────────────────
@router.post("/jobs/confirm/{report_id}")
def confirm_job(report_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Confirm an optimization job and deduct board stock.
    Called when user clicks "Confirm Job & Deduct Stock".
    """
    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job report not found")

    if job.status == "confirmed":
        raise HTTPException(status_code=400, detail="Job already confirmed")

    if job.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot confirm a cancelled job")

    # Parse the stored stock impact
    stock_impact = []
    if job.stock_impact_json:
        try:
            stock_impact = json.loads(job.stock_impact_json)
        except json.JSONDecodeError:
            logger.error(f"Bad stock_impact_json for {report_id}")

    # Deduct stock from board inventory
    deduction_results = []
    if stock_impact:
        deduction_results = deduct_stock(db, stock_impact)

    # Mark job as confirmed
    job.status = "confirmed"
    job.confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(job)

    logger.info(f"Job {report_id} confirmed — stock deducted")

    return {
        "status": "ok",
        "report_id": report_id,
        "message": "Job confirmed and stock deducted successfully",
        "job": _job_to_dict(job),
        "deductions": deduction_results,
    }


# ── Cancel a job ─────────────────────────────────────────
@router.post("/jobs/cancel/{report_id}")
def cancel_job(report_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job report not found")

    if job.status == "confirmed":
        raise HTTPException(status_code=400, detail="Cannot cancel a confirmed job")

    job.status = "cancelled"
    db.commit()
    db.refresh(job)
    logger.info(f"Job {report_id} cancelled")

    return {
        "status": "ok",
        "report_id": report_id,
        "message": "Job cancelled",
        "job": _job_to_dict(job),
    }


# ── Delete a job ─────────────────────────────────────────
@router.delete("/jobs/{report_id}")
def delete_job(report_id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job report not found")

    db.delete(job)
    db.commit()
    logger.info(f"Job {report_id} deleted")
    return {"status": "deleted", "report_id": report_id}
