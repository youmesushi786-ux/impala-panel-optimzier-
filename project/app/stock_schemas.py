from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class BoardItemBase(BaseModel):
    board_type: str
    thickness_mm: int = Field(ge=1, le=100)
    color_name: str
    company: str
    width_mm: float = Field(gt=0, le=10000)
    length_mm: float = Field(gt=0, le=10000)
    price_per_board: float = Field(ge=0)
    quantity: int = Field(ge=0)
    low_stock_threshold: int = Field(ge=0, default=3)
    is_active: bool = True


class BoardItemCreate(BoardItemBase):
    pass


class BoardItemUpdate(BaseModel):
    board_type: Optional[str] = None
    thickness_mm: Optional[int] = Field(default=None, ge=1, le=100)
    color_name: Optional[str] = None
    company: Optional[str] = None
    width_mm: Optional[float] = Field(default=None, gt=0, le=10000)
    length_mm: Optional[float] = Field(default=None, gt=0, le=10000)
    price_per_board: Optional[float] = Field(default=None, ge=0)
    quantity: Optional[int] = Field(default=None, ge=0)
    low_stock_threshold: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class BoardItemOut(BoardItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StockTransactionOut(BaseModel):
    id: int
    board_item_id: int
    transaction_type: str
    quantity: int
    balance_before: int
    balance_after: int
    report_id: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class StockAdjustmentRequest(BaseModel):
    board_item_id: int
    quantity: int = Field(gt=0)
    notes: Optional[str] = None
    reference: Optional[str] = None


class BoardCatalogResponse(BaseModel):
    items: List[BoardItemOut]