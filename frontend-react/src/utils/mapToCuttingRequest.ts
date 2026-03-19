import type {
  Panel,
  OptimizationOptions,
  CustomerDetails,
  BackendCuttingRequest,
  BoardSelection,
} from '../types';

export function mapToCuttingRequest(params: {
  panels: Panel[];
  options: OptimizationOptions;
  customer: CustomerDetails;
}): BackendCuttingRequest {
  const { panels, options, customer } = params;

  if (!panels.length) {
    throw new Error('At least one panel is required.');
  }

  const defaultBoard = panels[0].board;
  if (!defaultBoard) {
    throw new Error('A default board selection is required.');
  }

  const cleanBoard = (board?: BoardSelection): BoardSelection | undefined => {
    if (!board) return undefined;
    return {
      board_item_id: board.board_item_id,
      board_type: board.board_type,
      thickness_mm: Number(board.thickness_mm),
      company: board.company,
      color_name: board.color_name,
      width_mm: Number(board.width_mm),
      length_mm: Number(board.length_mm),
      price_per_board: Number(board.price_per_board),
    };
  };

  return {
    project_name: customer.project_name || undefined,
    customer_name: customer.customer_name || undefined,
    notes: customer.notes || undefined,
    board: cleanBoard(defaultBoard)!,
    options: {
      kerf: Number(options.kerf),
      labels_on_panels: !!options.labels_on_panels,
      use_single_sheet: !!options.use_single_sheet,
      consider_material: !!options.consider_material,
      edge_banding: !!options.edge_banding,
      consider_grain: !!options.consider_grain,
    },
    panels: panels.map((panel) => ({
      label: panel.label,
      width: Number(panel.width),
      length: Number(panel.length),
      quantity: Number(panel.quantity),
      alignment: panel.alignment,
      notes: panel.notes || undefined,
      edging: {
        top: !!panel.edges.top,
        right: !!panel.edges.right,
        bottom: !!panel.edges.bottom,
        left: !!panel.edges.left,
      },
      board: cleanBoard(panel.board),
      board_item_id: panel.board.board_item_id,
    })),
  };
}