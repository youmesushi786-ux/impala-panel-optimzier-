import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.job_service import confirm_job
from app.models import JobReport

logger = logging.getLogger("panelpro.jobs")
router = APIRouter(tags=["Job Management"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/jobs")
async def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(JobReport).order_by(JobReport.created_at.desc()).all()
    return {
        "jobs": [
            {
                "report_id": j.report_id,
                "status": j.status,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "confirmed_at": j.confirmed_at.isoformat() if j.confirmed_at else None,
            }
            for j in jobs
        ]
    }


@router.get("/jobs/{report_id}")
async def get_job(report_id: str, db: Session = Depends(get_db)):
    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "report_id": job.report_id,
        "status": job.status,
        "request_json": job.request_json,
        "stock_impact_json": job.stock_impact_json,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "confirmed_at": job.confirmed_at.isoformat() if job.confirmed_at else None,
    }


@router.post("/jobs/{report_id}/confirm")
async def confirm_job_endpoint(report_id: str, db: Session = Depends(get_db)):
    success = confirm_job(db, report_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"report_id": report_id, "status": "confirmed"}
