from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class BoardItem(Base):
    __tablename__ = "board_items"

    id = Column(Integer, primary_key=True, index=True)

    board_type = Column(String, nullable=False, index=True)
    thickness_mm = Column(Integer, nullable=False, index=True)
    color_name = Column(String, nullable=False, index=True)
    company = Column(String, nullable=False, index=True)

    width_mm = Column(Float, nullable=False)
    length_mm = Column(Float, nullable=False)

    price_per_board = Column(Float, nullable=False, default=0.0)
    quantity = Column(Integer, nullable=False, default=0)
    low_stock_threshold = Column(Integer, nullable=False, default=3)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    transactions = relationship(
        "StockTransaction",
        back_populates="board_item",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "board_type",
            "thickness_mm",
            "color_name",
            "company",
            "width_mm",
            "length_mm",
            name="uq_board_item",
        ),
    )


class StockTransaction(Base):
    __tablename__ = "stock_transactions"

    id = Column(Integer, primary_key=True, index=True)
    board_item_id = Column(Integer, ForeignKey("board_items.id"), nullable=False, index=True)

    transaction_type = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)

    balance_before = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)

    report_id = Column(String, nullable=True, index=True)
    reference = Column(String, nullable=True)
    notes = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    board_item = relationship("BoardItem", back_populates="transactions")


class JobReport(Base):
    __tablename__ = "job_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String, unique=True, nullable=False, index=True)

    request_json = Column(Text, nullable=False)
    stock_impact_json = Column(Text, nullable=True)

    confirmed = Column(Boolean, default=False, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class StickerTracking(Base):
    __tablename__ = "sticker_tracking"

    id = Column(Integer, primary_key=True, index=True)
    serial_number = Column(String, unique=True, nullable=False, index=True)
    report_id = Column(String, nullable=False, index=True)
    panel_label = Column(String, nullable=False)
    board_number = Column(Integer, nullable=True)
    qr_url = Column(String, nullable=True)
    status = Column(String, nullable=False, default="in_store")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)