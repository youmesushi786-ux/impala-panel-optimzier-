from __future__ import annotations

import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import JobReport
from app.job_service import confirm_job_and_update_stock

router = APIRouter(tags=["Job Management"])


@router.get("/jobs")
def list_jobs(status: Optional[str] = None, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    q = db.query(JobReport)
    if status: q = q.filter(JobReport.status == status)
    jobs = q.order_by(JobReport.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "jobs": [
            {
                "report_id": j.report_id,
                "project_name": j.project_name,
                "customer_name": j.customer_name,
                "status": j.status,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "confirmed_at": j.confirmed_at.isoformat() if j.confirmed_at else None,
                "total_boards_used": j.total_boards_used,
                "total_offcuts_used": j.total_offcuts_used,
                "total_offcuts_created": j.total_offcuts_created,
                "efficiency_percent": j.efficiency_percent,
            }
            for j in jobs
        ]
    }


@router.get("/jobs/{report_id}")
def get_job(report_id: str, db: Session = Depends(get_db)):
    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job: raise HTTPException(status_code=404, detail="Job report not found")
    return {
        "report_id": job.report_id,
        "project_name": job.project_name,
        "customer_name": job.customer_name,
        "status": job.status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "confirmed_at": job.confirmed_at.isoformat() if job.confirmed_at else None,
        "request": json.loads(job.request_json) if job.request_json else {},
        "stock_impact": json.loads(job.stock_impact_json) if job.stock_impact_json else [],
        "result_summary": json.loads(job.result_summary_json) if job.result_summary_json else {},
    }


@router.post("/jobs/confirm/{report_id}")
@router.post("/jobs/{report_id}/confirm")
def confirm_job(report_id: str, db: Session = Depends(get_db)):
    try:
        job = confirm_job_and_update_stock(db, report_id)
        return {
            "status": "ok",
            "report_id": report_id,
            "message": "Job confirmed and stock updated successfully",
            "job_status": job.status,
            "confirmed_at": job.confirmed_at.isoformat(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/jobs/cancel/{report_id}")
@router.post("/jobs/{report_id}/cancel")
def cancel_job(report_id: str, db: Session = Depends(get_db)):
    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job: raise HTTPException(status_code=404, detail="Job report not found")
    if job.status == "confirmed": raise HTTPException(status_code=400, detail="Cannot cancel confirmed job")

    job.status = "cancelled"
    job.cancelled_at = datetime.utcnow()
    db.commit()
    return {"status": "ok", "report_id": report_id, "message": "Job cancelled"}


@router.delete("/jobs/{report_id}")
def delete_job(report_id: str, db: Session = Depends(get_db)):
    job = db.query(JobReport).filter(JobReport.report_id == report_id).first()
    if not job: raise HTTPException(status_code=404, detail="Job report not found")
    db.delete(job)
    db.commit()
    return {"status": "deleted", "report_id": report_id}
