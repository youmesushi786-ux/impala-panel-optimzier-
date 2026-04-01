from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime,
)
from app.db import Base


class BoardItem(Base):
    __tablename__ = "board_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    board_type = Column(String, nullable=False, default="MDF")
    thickness_mm = Column(Float, nullable=False, default=18.0)
    color_name = Column(String, nullable=False, default="White")
    company = Column(String, nullable=False, default="Generic")
    width_mm = Column(Float, nullable=False, default=2440)
    length_mm = Column(Float, nullable=False, default=1220)
    price_per_board = Column(Float, nullable=False, default=0.0)
    quantity = Column(Integer, nullable=False, default=0)
    low_stock_threshold = Column(Integer, nullable=False, default=5)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StickerTracking(Base):
    __tablename__ = "sticker_tracking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_number = Column(String, unique=True, nullable=False, index=True)
    report_id = Column(String, nullable=False, index=True)
    panel_label = Column(String, nullable=False, default="Panel")
    board_number = Column(Integer, nullable=False, default=1)
    qr_url = Column(String, nullable=True)
    status = Column(String, nullable=False, default="in_store")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobReport(Base):
    __tablename__ = "job_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String, unique=True, nullable=False, index=True)
    project_name = Column(String, nullable=True)
    customer_name = Column(String, nullable=True)
    request_json = Column(Text, nullable=False)
    stock_impact_json = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="pending")   # pending / confirmed / cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
