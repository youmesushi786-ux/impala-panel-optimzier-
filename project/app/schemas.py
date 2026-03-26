from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class GrainAlignment(str, enum.Enum):
    none = "none"
    horizontal = "horizontal"
    vertical = "vertical"


class Edging(BaseModel):
    top: bool = False
    right: bool = False
    bottom: bool = False
    left: bool = False


class BoardSpec(BaseModel):
    board_item_id: Optional[int] = None
    board_type: str = "MDF"
    thickness_mm: float = 18.0
    company: str = ""
    color_name: str = ""
    width_mm: float = 2440.0
    length_mm: float = 1220.0
    price_per_board: float = 0.0


class Options(BaseModel):
    kerf: float = 3.0
    allow_rotation: bool = True
    consider_grain: bool = False
    generate_cuts: bool = True


class Panel(BaseModel):
    width: float
    length: float
    quantity: int = 1
    label: Optional[str] = None
    alignment: GrainAlignment = GrainAlignment.none
    edging: Edging = Field(default_factory=Edging)

    board_item_id: Optional[int] = None
    board_type: Optional[str] = None
    thickness_mm: Optional[float] = None
    company: Optional[str] = None
    color_name: Optional[str] = None
    price_per_board: Optional[float] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _clamp_quantity(self):
        if self.quantity < 1:
            self.quantity = 1
        return self

    @property
    def edge_length_mm(self) -> float:
        total = 0.0
        if self.edging.top:
            total += self.width
        if self.edging.bottom:
            total += self.width
        if self.edging.left:
            total += self.length
        if self.edging.right:
            total += self.length
        return total

    @property
    def total_edge_length_mm(self) -> float:
        return self.edge_length_mm * self.quantity

    def get_effective_board(self, default_board: BoardSpec) -> BoardSpec:
        has_override = any([
            self.board_item_id is not None,
            self.board_type not in (None, ""),
            self.thickness_mm is not None and self.thickness_mm > 0,
            self.company not in (None, ""),
            self.color_name not in (None, ""),
            self.price_per_board is not None,
        ])
        if not has_override:
            return default_board

        return BoardSpec(
            board_item_id=self.board_item_id if self.board_item_id is not None else default_board.board_item_id,
            board_type=self.board_type or default_board.board_type,
            thickness_mm=(
                self.thickness_mm
                if self.thickness_mm is not None and self.thickness_mm > 0
                else default_board.thickness_mm
            ),
            company=self.company or default_board.company,
            color_name=self.color_name or default_board.color_name,
            width_mm=default_board.width_mm,
            length_mm=default_board.length_mm,
            price_per_board=(
                self.price_per_board
                if self.price_per_board is not None
                else default_board.price_per_board
            ),
        )


class CuttingRequest(BaseModel):
    project_name: str = "Untitled Project"
    customer_name: str = "Customer"
    board: BoardSpec = Field(default_factory=BoardSpec)
    panels: List[Panel] = Field(default_factory=list)
    options: Optional[Options] = Field(default_factory=Options)

    @model_validator(mode="after")
    def _ensure_options(self):
        if self.options is None:
            self.options = Options()
        return self


class PlacedPanel(BaseModel):
    panel_index: int
    x: float
    y: float
    width: float
    length: float
    footprint_width: float = 0.0
    footprint_length: float = 0.0
    original_width: float = 0.0
    original_length: float = 0.0
    label: str = ""
    notes: Optional[str] = None
    rotated: bool = False
    grain_aligned: GrainAlignment = GrainAlignment.none
    board_number: int = 1


class CutSegment(BaseModel):
    id: int
    orientation: str
    direction: str
    x1: float
    y1: float
    x2: float
    y2: float
    length: float
    label: str = ""
    sequence: Optional[int] = None


class BoardLayout(BaseModel):
    board_number: int
    board_width: float
    board_length: float
    used_area_mm2: float = 0.0
    waste_area_mm2: float = 0.0
    efficiency_percent: float = 0.0
    panel_count: int = 0
    source: str = ""
    material: Dict[str, Any] = Field(default_factory=dict)
    panels: List[PlacedPanel] = Field(default_factory=list)
    cuts: List[CutSegment] = Field(default_factory=list)


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


class EdgingDetail(BaseModel):
    panel_label: str
    quantity: int
    edge_per_panel_m: float
    total_edge_m: float
    edges_applied: str


class EdgingSummary(BaseModel):
    total_meters: float = 0.0
    details: List[EdgingDetail] = Field(default_factory=list)


class StickerLabel(BaseModel):
    serial_number: str
    panel_label: str
    width: float
    length: float
    board_number: int
    x: float
    y: float
    rotated: bool = False
    project_name: str = ""
    customer_name: str = ""
    board_type: str = ""
    thickness_mm: float = 0.0
    company: str = ""
    color_name: str = ""
    notes: Optional[str] = None
    qr_url: str = ""


class PricingLine(BaseModel):
    item: str
    description: str = ""
    quantity: float = 0.0
    unit: str = ""
    unit_price: float = 0.0
    amount: float = 0.0


class PricingSummary(BaseModel):
    lines: List[PricingLine] = Field(default_factory=list)
    subtotal: float = 0.0
    tax_name: str = ""
    tax_rate: float = 0.0
    tax_amount: float = 0.0
    total: float = 0.0
    currency: str = ""


class BOQItem(BaseModel):
    item_no: int
    description: str
    size: str
    quantity: int
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


class StockImpactItem(BaseModel):
    board_item_id: int
    board_label: str = ""
    current_quantity: int = 0
    required_quantity: int = 0
    projected_balance: int = 0
    price_per_board: float = 0.0
    stock_status: str = ""


class RemainingStockItem(BaseModel):
    board_item_id: int
    quantity: int = 0


class StickerTrackingResponse(BaseModel):
    serial_number: str
    report_id: str
    panel_label: str
    status: str
    qr_url: str
    updated_at: Optional[str] = None
    board_number: int


class HealthResponse(BaseModel):
    status: str = "healthy"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class JobConfirmResponse(BaseModel):
    success: bool = True
    message: str = ""
    boards_deducted: int = 0
    remaining_stock: List[RemainingStockItem] = Field(default_factory=list)


class CuttingResponse(BaseModel):
    request_summary: Dict[str, Any] = Field(default_factory=dict)
    optimization: OptimizationSummary = Field(default_factory=OptimizationSummary)
    layouts: List[BoardLayout] = Field(default_factory=list)
    edging: EdgingSummary = Field(default_factory=EdgingSummary)
    boq: Optional[BOQSummary] = None
    pricing: Optional[PricingSummary] = None
    stickers: List[StickerLabel] = Field(default_factory=list)
    stock_impact: Optional[List[StockImpactItem]] = None
    report_id: str = ""
    generated_at: Optional[datetime] = None
