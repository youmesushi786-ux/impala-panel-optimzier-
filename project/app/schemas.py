"""Pydantic schemas. DO NOT add `from __future__ import annotations`."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class GrainAlignment(str, Enum):
    none = "none"
    horizontal = "horizontal"
    vertical = "vertical"


# ─────────────────────────────────────────────
# Basic Specs
# ─────────────────────────────────────────────

class EdgeSpec(BaseModel):
    top: bool = False
    right: bool = False
    bottom: bool = False
    left: bool = False


class Options(BaseModel):
    kerf: float = 3.0
    allow_rotation: bool = True
    consider_grain: bool = False
    generate_cuts: bool = True


class BoardSpec(BaseModel):
    board_item_id: Optional[int] = None
    board_type: str = "MDF"
    thickness_mm: float = 18.0
    color_name: str = "White"
    company: str = "Generic"
    width_mm: float = 2440.0
    length_mm: float = 1220.0
    price_per_board: float = 0.0


class PanelSpec(BaseModel):
    width: float
    length: float
    quantity: int = 1
    label: str = ""
    edging: EdgeSpec = Field(default_factory=EdgeSpec)
    alignment: GrainAlignment = GrainAlignment.none
    notes: Optional[str] = None

    @property
    def edge_length_mm(self) -> float:
        total = 0.0
        if self.edging.top:    total += self.width
        if self.edging.bottom: total += self.width
        if self.edging.left:   total += self.length
        if self.edging.right:  total += self.length
        return total

    @property
    def total_edge_length_mm(self) -> float:
        return self.edge_length_mm * self.quantity


# ─────────────────────────────────────────────
# Request
# ─────────────────────────────────────────────

class CuttingRequest(BaseModel):
    project_name: str = "Untitled Project"
    customer_name: str = "Customer"
    board: BoardSpec = Field(default_factory=BoardSpec)
    panels: List[PanelSpec] = Field(default_factory=list)
    options: Optional[Options] = None


# ─────────────────────────────────────────────
# Layout Models
# ─────────────────────────────────────────────

class PlacedPanel(BaseModel):
    panel_index: int = 0
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    length: float = 0.0
    footprint_width: float = 0.0
    footprint_length: float = 0.0
    original_width: float = 0.0
    original_length: float = 0.0
    label: str = ""
    notes: Optional[str] = None
    rotated: bool = False
    grain_aligned: GrainAlignment = GrainAlignment.none
    board_number: int = 0


class CutSegment(BaseModel):
    id: int = 0
    sequence: int = 0
    orientation: str = ""
    direction: str = ""
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    length: float = 0.0
    label: str = ""


class BoardLayout(BaseModel):
    board_number: int = 0
    board_width: float = 0.0
    board_length: float = 0.0
    used_area_mm2: float = 0.0
    waste_area_mm2: float = 0.0
    efficiency_percent: float = 0.0
    panel_count: int = 0
    source: str = ""
    material: Dict[str, Any] = Field(default_factory=dict)
    panels: List[PlacedPanel] = Field(default_factory=list)
    cuts: List[CutSegment] = Field(default_factory=list)


# ─────────────────────────────────────────────
# Edging
# ─────────────────────────────────────────────

class EdgingDetail(BaseModel):
    panel_label: str = ""
    quantity: int = 0
    edge_per_panel_m: float = 0.0
    total_edge_m: float = 0.0
    edges_applied: str = "None"


class EdgingSummary(BaseModel):
    total_meters: float = 0.0
    details: List[EdgingDetail] = Field(default_factory=list)


# ─────────────────────────────────────────────
# Optimization Summary
# ─────────────────────────────────────────────

class OptimizationSummary(BaseModel):
    total_boards: int = 0
    total_panels: int = 0
    unique_panel_types: int = 0
    total_edging_meters: float = 0.0
    total_cuts: int = 0
    total_cut_length: float = 0.0
    total_waste_mm2: float = 0.0
    total_waste_percent: float = 0.0
    board_width: float = 0.0
    board_length: float = 0.0
    total_used_area_mm2: float = 0.0
    overall_efficiency_percent: float = 0.0
    kerf_mm: float = 0.0
    grain_considered: bool = False
    material_groups: int = 1
    impossible_panels: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ─────────────────────────────────────────────
# Pricing
# ─────────────────────────────────────────────

class PricingLine(BaseModel):
    item: str = ""
    description: str = ""
    quantity: float = 0.0
    unit_price: float = 0.0
    amount: float = 0.0


class PricingSummary(BaseModel):
    lines: List[PricingLine] = Field(default_factory=list)
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0


# ─────────────────────────────────────────────
# BOQ
# ─────────────────────────────────────────────

class BOQItem(BaseModel):
    item_no: int = 0
    description: str = ""
    size: str = ""
    quantity: int = 0
    unit: str = "pcs"
    edges: str = "None"
    board_type: str = ""
    thickness_mm: float = 0.0
    company: str = ""
    colour: str = ""
    material_amount: float = 0.0


class BOQSummary(BaseModel):
    project_name: str = ""
    customer_name: str = ""
    date: str = ""
    items: List[BOQItem] = Field(default_factory=list)
    materials: Dict[str, Any] = Field(default_factory=dict)
    services: Dict[str, Any] = Field(default_factory=dict)
    pricing: Optional[PricingSummary] = None


# ─────────────────────────────────────────────
# Stock Impact
# ─────────────────────────────────────────────

class StockImpactItem(BaseModel):
    board_item_id: Optional[int] = None
    board_type: str = ""
    thickness_mm: float = 0.0
    color_name: str = ""
    company: str = ""
    width_mm: float = 0.0
    length_mm: float = 0.0
    price_per_board: float = 0.0
    quantity_needed: int = 0
    current_stock: int = 0
    stock_after: int = 0
    sufficient: bool = False


# ─────────────────────────────────────────────
# ✅ FIXED HEALTH RESPONSE
# ─────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
# Tracking
# ─────────────────────────────────────────────

class StickerTrackingResponse(BaseModel):
    serial_number: str = ""
    report_id: str = ""
    panel_label: Optional[str] = None
    status: str = "in_store"
    qr_url: Optional[str] = None
    updated_at: Optional[datetime] = None
    board_number: Optional[int] = None


# ─────────────────────────────────────────────
# Full Response
# ─────────────────────────────────────────────

class CuttingResponse(BaseModel):
    report_id: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    request_summary: Dict[str, Any] = Field(default_factory=dict)
    optimization: OptimizationSummary = Field(default_factory=OptimizationSummary)
    layouts: List[BoardLayout] = Field(default_factory=list)
    edging: EdgingSummary = Field(default_factory=EdgingSummary)
    pricing: Optional[PricingSummary] = None
    boq: Optional[BOQSummary] = None
    stickers: List[StickerLabel] = Field(default_factory=list)
    stock_impact: List[StockImpactItem] = Field(default_factory=list)
