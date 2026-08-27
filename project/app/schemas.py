from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, computed_field


class GrainAlignment(str, Enum):
    none = "none"
    horizontal = "horizontal"
    vertical = "vertical"


class OffcutStatus(str, Enum):
    available = "available"
    reserved = "reserved"
    consumed = "consumed"
    scrapped = "scrapped"


class EdgeConfig(BaseModel):
    top: bool = False
    right: bool = False
    bottom: bool = False
    left: bool = False


class Options(BaseModel):
    kerf: float = 3.0
    allow_rotation: bool = True
    consider_grain: bool = False
    generate_cuts: bool = True
    prefer_offcuts: bool = True
    use_offcuts: bool = True
    min_offcut_width_mm: float = 300.0
    min_offcut_length_mm: float = 300.0
    min_offcut_area_mm2: float = 90000.0
    edge_thickness_mm: float = 0.0
    trim_margin_mm: float = 0.0


class BoardSpec(BaseModel):
    board_item_id: Optional[int] = None
    board_type: str = "MDF"
    thickness_mm: float = 18.0
    color_name: str = "White"
    company: str = "Generic"
    width_mm: float = 1220.0
    length_mm: float = 2440.0
    price_per_board: float = 0.0


class PanelSpec(BaseModel):
    width: float
    length: float
    quantity: int = 1
    label: Optional[str] = None
    notes: Optional[str] = None
    edging: EdgeConfig = Field(default_factory=EdgeConfig)
    alignment: GrainAlignment = GrainAlignment.none
    board_override: Optional[BoardSpec] = None

    @computed_field
    @property
    def edge_length_mm(self) -> float:
        total = 0.0
        if self.edging.top: total += self.width
        if self.edging.bottom: total += self.width
        if self.edging.left: total += self.length
        if self.edging.right: total += self.length
        return total

    @computed_field
    @property
    def total_edge_length_mm(self) -> float:
        return self.edge_length_mm * self.quantity

    def get_effective_board(self, default_board: BoardSpec) -> BoardSpec:
        return self.board_override or default_board


class OffcutSpec(BaseModel):
    offcut_id: Optional[int] = None
    offcut_code: Optional[str] = None
    board_type: str = "MDF"
    thickness_mm: float = 18.0
    color_name: str = "White"
    company: str = "Generic"
    width_mm: float
    length_mm: float
    location: Optional[str] = None
    estimated_value: float = 0.0


class CuttingRequest(BaseModel):
    project_name: str = "Untitled Project"
    customer_name: str = "Customer"
    board: BoardSpec = Field(default_factory=BoardSpec)
    panels: List[PanelSpec] = Field(default_factory=list)
    options: Optional[Options] = None
    available_offcuts: List[OffcutSpec] = Field(default_factory=list)
    auto_load_offcuts_from_stock: bool = True


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
    board_number: int = 1


class CutSegment(BaseModel):
    id: int = 0
    sequence: int = 0
    orientation: str = "vertical"
    direction: str = "vertical"
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    length: float = 0.0
    label: str = ""


class BoardLayout(BaseModel):
    board_number: int = 1
    board_width: float = 0.0
    board_length: float = 0.0
    used_area_mm2: float = 0.0
    waste_area_mm2: float = 0.0
    efficiency_percent: float = 0.0
    panel_count: int = 0
    source: str = "full_sheet"  # full_sheet | offcut
    offcut_id: Optional[int] = None
    offcut_code: Optional[str] = None
    remnant_width_mm: float = 0.0
    remnant_length_mm: float = 0.0
    material: Dict[str, Any] = Field(default_factory=dict)
    panels: List[PlacedPanel] = Field(default_factory=list)
    cuts: List[CutSegment] = Field(default_factory=list)


class EdgingDetail(BaseModel):
    panel_label: str = ""
    quantity: int = 0
    edge_per_panel_m: float = 0.0
    total_edge_m: float = 0.0
    edges_applied: str = "None"


class EdgingSummary(BaseModel):
    total_meters: float = 0.0
    details: List[EdgingDetail] = Field(default_factory=list)


class OptimizationSummary(BaseModel):
    total_boards: int = 0
    total_full_sheets: int = 0
    total_offcuts_used: int = 0
    total_offcuts_created: int = 0
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
    kerf_mm: float = 3.0
    grain_considered: bool = False
    impossible_panels: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    offcuts_available_considered: int = 0


class StickerLabel(BaseModel):
    serial_number: str = ""
    panel_label: str = "Panel"
    width: float = 0.0
    length: float = 0.0
    board_number: int = 1
    x: float = 0.0
    y: float = 0.0
    rotated: bool = False
    project_name: str = ""
    customer_name: str = ""
    board_type: str = ""
    thickness_mm: float = 0.0
    company: str = ""
    color_name: str = ""
    notes: Optional[str] = None
    qr_url: str = ""
    source: str = "full_sheet"
    offcut_code: Optional[str] = None


class PricingLine(BaseModel):
    item: str = ""
    description: str = ""
    quantity: float = 0.0
    unit_price: float = 0.0
    amount: float = 0.0


class PricingBreakdown(BaseModel):
    lines: List[PricingLine] = Field(default_factory=list)
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0


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
    pricing: PricingBreakdown = Field(default_factory=PricingBreakdown)


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


class OffcutUsedItem(BaseModel):
    offcut_id: Optional[int] = None
    offcut_code: Optional[str] = None
    width_mm: float = 0.0
    length_mm: float = 0.0
    board_number: int = 0
    used_area_mm2: float = 0.0
    efficiency_percent: float = 0.0


class OffcutCreatedItem(BaseModel):
    width_mm: float
    length_mm: float
    area_mm2: float = 0.0
    board_type: str = "MDF"
    thickness_mm: float = 18.0
    color_name: str = "White"
    company: str = "Generic"
    source_board_number: int = 0
    source: str = "waste"
    suggested_location: Optional[str] = None
    estimated_value: float = 0.0


class StockImpactSummary(BaseModel):
    full_sheets: List[StockImpactItem] = Field(default_factory=list)
    offcuts_used: List[OffcutUsedItem] = Field(default_factory=list)
    offcuts_to_create: List[OffcutCreatedItem] = Field(default_factory=list)
    estimated_material_saving: float = 0.0
    warnings: List[str] = Field(default_factory=list)


class CuttingResponse(BaseModel):
    request_summary: Dict[str, Any] = Field(default_factory=dict)
    optimization: OptimizationSummary
    layouts: List[BoardLayout] = Field(default_factory=list)
    edging: EdgingSummary = Field(default_factory=EdgingSummary)
    boq: BOQSummary
    stickers: List[StickerLabel] = Field(default_factory=list)
    stock_impact: List[StockImpactItem] = Field(default_factory=list)
    stock_impact_detail: Optional[StockImpactSummary] = None
    offcuts_used: List[OffcutUsedItem] = Field(default_factory=list)
    offcuts_to_create: List[OffcutCreatedItem] = Field(default_factory=list)
    report_id: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class BoardItemCreate(BaseModel):
    board_type: str = "MDF"
    thickness_mm: float = 18.0
    color_name: str = "White"
    company: str = "Generic"
    width_mm: float = 1220.0
    length_mm: float = 2440.0
    price_per_board: float = 0.0
    quantity: int = 0
    low_stock_threshold: int = 5
    location: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None


class BoardItemUpdate(BaseModel):
    price_per_board: Optional[float] = None
    quantity: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class BoardItemResponse(BaseModel):
    id: int
    board_type: str
    thickness_mm: float
    color_name: str
    company: str
    width_mm: float
    length_mm: float
    price_per_board: float
    quantity: int
    low_stock_threshold: int
    location: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OffcutResponse(BaseModel):
    id: int
    offcut_code: str
    board_type: str
    thickness_mm: float
    color_name: str
    company: str
    width_mm: float
    length_mm: float
    area_mm2: float
    status: str
    location: Optional[str] = None
    source_report_id: Optional[str] = None

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StickerTrackingResponse(BaseModel):
    serial_number: str
    report_id: str
    panel_label: str
    status: str
    qr_url: Optional[str] = None
    updated_at: Optional[datetime] = None
    board_number: int = 1
