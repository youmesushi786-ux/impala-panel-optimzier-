export interface PanelEdges {
  top: boolean;
  right: boolean;
  bottom: boolean;
  left: boolean;
}

export interface BoardSelection {
  board_item_id: number;
  board_type: string;
  thickness_mm: number;
  company: string;
  color_name: string;
  width_mm: number;
  length_mm: number;
  price_per_board: number;
}

export interface Panel {
  id: string;
  label: string;
  width: number;
  length: number;
  quantity: number;
  alignment: 'none' | 'horizontal' | 'vertical';
  notes?: string;
  board: BoardSelection;
  edges: PanelEdges;
}

export interface OptimizationOptions {
  kerf: number;
  labels_on_panels: boolean;
  use_single_sheet: boolean;
  consider_material: boolean;
  edge_banding: boolean;
  consider_grain: boolean;
}

export interface CustomerDetails {
  project_name: string;
  customer_name: string;
  notes: string;
}

export interface BackendCuttingRequest {
  project_name?: string;
  customer_name?: string;
  notes?: string;
  board: BoardSelection;
  panels: Array<{
    label: string;
    width: number;
    length: number;
    quantity: number;
    alignment?: 'none' | 'horizontal' | 'vertical';
    notes?: string;
    edging: PanelEdges;
    board?: BoardSelection;
    board_item_id?: number;
  }>;
  options: OptimizationOptions;
  stock_sheets?: Array<{
    length: number;
    width: number;
    qty: number;
  }>;
}

export interface BoardItem {
  id: number;
  board_type: string;
  thickness_mm: number;
  color_name: string;
  company: string;
  width_mm: number;
  length_mm: number;
  price_per_board: number;
  quantity: number;
  low_stock_threshold: number;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface StockTransaction {
  id: number;
  board_item_id: number;
  transaction_type: string;
  quantity: number;
  balance_before: number;
  balance_after: number;
  report_id?: string;
  reference?: string;
  notes?: string;
  created_at: string;
}

export interface StockAdjustmentRequest {
  board_item_id: number;
  quantity: number;
  notes?: string;
  reference?: string;
}

export interface BoardCatalog {
  items: BoardItem[];
}

export interface RemainingStockItem {
  board_item_id: number;
  quantity: number;
}

export interface JobConfirmResponse {
  success: boolean;
  message: string;
  boards_deducted: number;
  remaining_stock: RemainingStockItem[];
}

export interface StockImpactItem {
  board_item_id: number;
  board_label: string;
  current_quantity: number;
  required_quantity: number;
  projected_balance: number;
  price_per_board: number;
  stock_status: string;
}

export interface CutSegment {
  id: number;
  orientation: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  length: number;
  board_number?: number;
  sequence?: number;
}

export interface PlacedPanel {
  panel_index: number;
  x: number;
  y: number;
  width: number;
  length: number;
  footprint_width: number;
  footprint_length: number;
  original_width: number;
  original_length: number;
  rotated: boolean;
  label?: string;
  notes?: string;
  grain_aligned?: 'none' | 'horizontal' | 'vertical' | null;
}

export interface BoardLayout {
  board_number: number;
  board_width: number;
  board_length: number;
  used_area_mm2: number;
  waste_area_mm2: number;
  efficiency_percent: number;
  panel_count: number;
  source?: string;
  material?: Record<string, any>;
  panels: PlacedPanel[];
  cuts: CutSegment[];
}

export interface OptimizationSummary {
  total_boards: number;
  total_panels: number;
  unique_panel_types: number;
  total_edging_meters: number;
  total_cuts: number;
  total_cut_length: number;
  total_waste_mm2: number;
  total_waste_percent: number;
  board_width: number;
  board_length: number;
}

export interface EdgingDetail {
  panel_label: string;
  quantity: number;
  edge_per_panel_m: number;
  total_edge_m: number;
  edges_applied: string;
}

export interface EdgingSummary {
  total_meters: number;
  details: EdgingDetail[];
}

export interface BOQItem {
  item_no: number;
  description: string;
  size: string;
  quantity: number;
  unit: string;
  edges: string;
  board_type?: string;
  thickness_mm?: number;
  company?: string;
  colour?: string;
  material_amount?: number;
}

export interface PricingLine {
  item: string;
  description: string;
  quantity: number;
  unit: string;
  unit_price: number;
  amount: number;
}

export interface PricingSummary {
  lines: PricingLine[];
  subtotal: number;
  tax_name: string;
  tax_rate: number;
  tax_amount: number;
  total: number;
  currency: string;
}

export interface BOQSummary {
  project_name?: string;
  customer_name?: string;
  date: string;
  items: BOQItem[];
  materials: Record<string, any>;
  services: Record<string, any>;
  pricing: PricingSummary;
}

export interface StickerLabel {
  serial_number: string;
  panel_label: string;
  width: number;
  length: number;
  board_number: number;
  x: number;
  y: number;
  rotated: boolean;
  project_name?: string;
  customer_name?: string;
  company_name?: string;
  company_logo_url?: string;
  board_type?: string;
  thickness_mm?: number;
  company?: string;
  color_name?: string;
  notes?: string;
  qr_url?: string;
}

export interface StickerTrackingResponse {
  serial_number: string;
  report_id: string;
  panel_label: string;
  status: 'in_store' | 'out_for_delivery' | 'delivered';
  qr_url?: string;
  updated_at: string;
  board_number?: number;
}

export interface CuttingResponse {
  request_summary: Record<string, any>;
  optimization: OptimizationSummary;
  layouts: BoardLayout[];
  edging: EdgingSummary;
  boq: BOQSummary;
  stickers: StickerLabel[];
  stock_impact: StockImpactItem[];
  report_id: string;
  generated_at: string;
}