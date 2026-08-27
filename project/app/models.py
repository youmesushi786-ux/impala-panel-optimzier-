from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from app.db import Base


class BoardItem(Base):
    """Catalog and quantity of identical FULL raw sheets."""
    __tablename__ = "board_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    board_type = Column(String, nullable=False, default="MDF", index=True)
    thickness_mm = Column(Float, nullable=False, default=18.0, index=True)
    color_name = Column(String, nullable=False, default="White", index=True)
    company = Column(String, nullable=False, default="Generic", index=True)

    width_mm = Column(Float, nullable=False, default=1220.0)
    length_mm = Column(Float, nullable=False, default=2440.0)
    price_per_board = Column(Float, nullable=False, default=0.0)
    quantity = Column(Integer, nullable=False, default=0)
    low_stock_threshold = Column(Integer, nullable=False, default=5)

    location = Column(String, nullable=True, default=None)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    offcuts = relationship("OffcutItem", back_populates="source_board_sku")

    __table_args__ = (
        Index("ix_board_material_lookup", "board_type", "thickness_mm", "color_name", "company"),
    )


class OffcutItem(Base):
    """Individual physical remnant pieces in the workshop pool."""
    __tablename__ = "offcut_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    offcut_code = Column(String, unique=True, nullable=False, index=True)

    board_type = Column(String, nullable=False, index=True)
    thickness_mm = Column(Float, nullable=False, index=True)
    color_name = Column(String, nullable=False, index=True)
    company = Column(String, nullable=False, default="Generic", index=True)

    width_mm = Column(Float, nullable=False)
    length_mm = Column(Float, nullable=False)
    area_mm2 = Column(Float, nullable=False, default=0.0)

    # available | reserved | consumed | scrapped
    status = Column(String, nullable=False, default="available", index=True)
    location = Column(String, nullable=True, default=None, index=True)

    source_report_id = Column(String, nullable=True, index=True)
    source_board_number = Column(Integer, nullable=True)
    source_board_item_id = Column(Integer, ForeignKey("board_items.id"), nullable=True)

    reserved_report_id = Column(String, nullable=True, index=True)
    consumed_report_id = Column(String, nullable=True, index=True)
    estimated_value = Column(Float, nullable=True, default=0.0)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    consumed_at = Column(DateTime, nullable=True)

    source_board_sku = relationship("BoardItem", back_populates="offcuts")

    __table_args__ = (
        Index("ix_offcut_material_status", "board_type", "thickness_mm", "color_name", "company", "status"),
    )


class StickerTracking(Base):
    """Tracks QR code tracking labels for individual cut panels."""
    __tablename__ = "sticker_tracking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_number = Column(String, unique=True, nullable=False, index=True)
    report_id = Column(String, nullable=False, index=True)
    panel_label = Column(String, nullable=False, default="Panel")
    board_number = Column(Integer, nullable=False, default=1)
    qr_url = Column(String, nullable=True)
    # in_store | in_production | out_for_delivery | delivered
    status = Column(String, nullable=False, default="in_store", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobReport(Base):
    """Persisted optimization reports and execution state."""
    __tablename__ = "job_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String, unique=True, nullable=False, index=True)
    project_name = Column(String, nullable=True)
    customer_name = Column(String, nullable=True)

    request_json = Column(Text, nullable=False)
    stock_impact_json = Column(Text, nullable=True)
    result_summary_json = Column(Text, nullable=True)

    # pending | confirmed | cancelled
    status = Column(String, nullable=False, default="pending", index=True)

    total_boards_used = Column(Integer, nullable=True, default=0)
    total_offcuts_used = Column(Integer, nullable=True, default=0)
    total_offcuts_created = Column(Integer, nullable=True, default=0)
    efficiency_percent = Column(Float, nullable=True, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    confirmed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)


class JobStockMovement(Base):
    """Immutable factory inventory movement audit log."""
    __tablename__ = "job_stock_movements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String, nullable=False, index=True)
    # consume_full_board | consume_offcut | create_offcut | scrap_offcut | restock_full_board
    movement_type = Column(String, nullable=False, index=True)

    board_type = Column(String, nullable=False)
    thickness_mm = Column(Float, nullable=False)
    color_name = Column(String, nullable=False)
    company = Column(String, nullable=False, default="Generic")

    width_mm = Column(Float, nullable=True)
    length_mm = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False, default=1)

    board_item_id = Column(Integer, ForeignKey("board_items.id"), nullable=True)
    offcut_item_id = Column(Integer, ForeignKey("offcut_items.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
