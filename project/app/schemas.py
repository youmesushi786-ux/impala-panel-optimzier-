from __future__ import annotations

from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class GrainAlignment(str, Enum):
    none = "none"
    horizontal = "horizontal"
    vertical = "vertical"


class BoardSelection(BaseModel):
    board_item_id: int
    board_type: str
    thickness_mm: int
    company: str
    color_name: str
    width_mm: float
    length_mm: float
    price_per_board: float = 0.0


class EdgingSpec(BaseModel):
    left: bool = False
    right: bool = False
    top: bool = False
    bottom: bool = False


class PanelDetail(BaseModel):
    width: float = Field(gt=0, le=5000)
    length: float = Field(gt=0, le=5000)
    quantity: int = Field(gt=0, le=500)
    edging: EdgingSpec = Field(default_factory=EdgingSpec)
    alignment: GrainAlignment = GrainAlignment.none
    label: Optional[str] = None
    notes: Optional[str] = None
    board: Optional[BoardSelection] = None

    @property
    def area_mm2(self) -> float:
        return self.width * self.length

    @property
    def total_area_mm2(self) -> float:
        return self.area_mm2 * self.quantity

    @property
    def edge_length_mm(self) -> float:
        total = 0.0
        if self.edging.left:
            total += self.length
        if self.edging.right:
            total += self.length
        if self.edging.top:
            total += self.width
        if self.edging.bottom:
            total += self.width
        return total

    @property
    def total_edge_length_mm(self) -> float:
        return self.edge_length_mm * self.quantity

    def get_effective_board(self, default_board: BoardSelection) -> BoardSelection:
        return self.board or default_board


class StockSheet(BaseModel):
    length: float = Field(gt=0, le=5000)
    width: float = Field(gt=0, le=5000)
    qty: int = Field(gt=0, le=1000)


class Options(BaseModel):
    kerf: float = Field(default=3.0, ge=1, le=10)
    labels_on_panels: bool = False
    use_single_sheet: bool = False
    consider_material: bool = True
    edge_banding: bool = True
    consider_grain: bool = False

    # Added to match optimizer.py
    allow_rotation: bool = True
    strict_validation: bool = True
    generate_cuts: bool = True


class CuttingRequest(BaseModel):
    panels: List[PanelDetail]
    board: BoardSelection
    stock_sheets: Optional[List[StockSheet]] = None
    options: Optional[Options] = None
    project_name: Optional[str] = None
    customer_name: Optional[str] = None
    notes: Optional[str] = None


class PlacedPanel(BaseModel):
    panel_index: int
    x: float
    y: float
    width: float
    length: float
    rotated: bool = False
    label: Optional[str] = None
    notes: Optional[str] = None
    grain_aligned: Optional[GrainAlignment] = None
    board_number: Optional[int] = None


class CutSegment(BaseModel):
    id: int
    orientation: str
    x1: float
    y1: float
    x2: float
    y2: float
    length: float
    board_number: Optional[int] = None
    sequence: Optional[int] = None
    direction: Optional[str] = None
    label: Optional[str] = None


class BoardLayout(BaseModel):
    board_number: int
    board_width: float
    board_length: float
    used_area_mm2: float
    waste_area_mm2: float
    efficiency_percent: float
    panel_count: int
    source: Optional[str] = None
    material: Optional[Dict[str, Any]] = None
    panels: List[PlacedPanel]
    cuts: List[CutSegment] = Field(default_factory=list)


class OptimizationSummary(BaseModel):
    total_boards: int
    total_panels: int
    unique_panel_types: int
    total_edging_meters: float
    total_cuts: int
    total_cut_length: float
    total_waste_mm2: float
    total_waste_percent: float
    board_width: float
    board_length: float

    # Added to match optimizer.py
    total_used_area_mm2: float = 0.0
    overall_efficiency_percent: float = 0.0
    kerf_mm: float = 0.0
    grain_considered: bool = False
    material_groups: int = 1
    impossible_panels: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class EdgingDetail(BaseModel):
    panel_label: str
    quantity: int
    edge_per_panel_m: float
    total_edge_m: float
    edges_applied: str


class EdgingSummary(BaseModel):
    total_meters: float
    details: List[EdgingDetail]


class StickerLabel(BaseModel):
    serial_number: str
    panel_label: str
    width: float
    length: float
    board_number: int
    x: float
    y: float
    rotated: bool
    project_name: Optional[str] = None
    customer_name: Optional[str] = None
    company_name: Optional[str] = None
    company_logo_url: Optional[str] = None
    company_phone: Optional[str] = None
    board_type: Optional[str] = None
    thickness_mm: Optional[int] = None
    company: Optional[str] = None
    color_name: Optional[str] = None
    notes: Optional[str] = None
    qr_url: Optional[str] = None


class StickerTrackingResponse(BaseModel):
    serial_number: str
    report_id: str
    panel_label: str
    status: str
    qr_url: Optional[str] = None
    updated_at: datetime
    board_number: Optional[int] = None


class StockImpactItem(BaseModel):
    board_item_id: int
    board_label: str
    current_quantity: int
    required_quantity: int
    projected_balance: int
    price_per_board: float
    stock_status: str


class RemainingStockItem(BaseModel):
    board_item_id: int
    quantity: int


class JobConfirmResponse(BaseModel):
    success: bool
    message: str
    boards_deducted: int
    remaining_stock: List[RemainingStockItem]


class PricingLine(BaseModel):
    item: str
    description: str
    quantity: float
    unit: str
    unit_price: float
    amount: float


class BOQItem(BaseModel):
    item_no: int
    description: str
    size: str
    quantity: int
    unit: str
    edges: str
    board_type: Optional[str] = None
    thickness_mm: Optional[int] = None
    company: Optional[str] = None
    colour: Optional[str] = None
    material_amount: Optional[float] = None


class PricingSummary(BaseModel):
    lines: List[PricingLine]
    subtotal: float
    tax_name: str
    tax_rate: float
    tax_amount: float
    total: float
    currency: str


class BOQSummary(BaseModel):
    project_name: Optional[str]
    customer_name: Optional[str]
    date: str
    items: List[BOQItem]
    materials: Dict[str, Any]
    services: Dict[str, Any]
    pricing: PricingSummary


class CuttingResponse(BaseModel):
    request_summary: Dict[str, Any]
    optimization: OptimizationSummary
    layouts: List[BoardLayout]
    edging: EdgingSummary
    boq: BOQSummary
    stickers: List[StickerLabel] = Field(default_factory=list)
    stock_impact: List[StockImpactItem] = Field(default_factory=list)
    report_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
