import type {
  BackendCuttingRequest,
  BoardCatalog,
  BoardItem,
  StockAdjustmentRequest,
  StockTransaction,
  JobConfirmResponse,
  StickerTrackingResponse,
  PanelEdges,
} from '../types';

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || 'https://impala-panel-optimzier-v1.onrender.com';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      message = data?.detail || data?.message || message;
    } catch {}
    throw new Error(message);
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

function getAdminHeaders(adminApiKey?: string): HeadersInit {
  const trimmed = adminApiKey?.trim();
  if (!trimmed) return {};
  return {
    'x-api-key': trimmed,
  };
}

function normalizeEdges(edges?: PanelEdges) {
  return {
    top: !!edges?.top,
    right: !!edges?.right,
    bottom: !!edges?.bottom,
    left: !!edges?.left,
  };
}

function normalizeOptimizePayload(payload: BackendCuttingRequest) {
  const primaryBoard =
    payload.board ||
    payload.panels?.[0]?.board || {
      board_item_id: undefined,
      board_type: '',
      thickness_mm: 18,
      company: '',
      color_name: '',
      width_mm: 2440,
      length_mm: 1220,
      price_per_board: 0,
    };

  return {
    project_name: payload.project_name || 'Untitled Project',
    customer_name: payload.customer_name || 'Customer',
    notes: payload.notes || '',
    board: {
      board_item_id: primaryBoard.board_item_id,
      board_type: primaryBoard.board_type,
      thickness_mm: Number(primaryBoard.thickness_mm || 0),
      company: primaryBoard.company || '',
      color_name: primaryBoard.color_name || '',
      width_mm: Number(primaryBoard.width_mm || 0),
      length_mm: Number(primaryBoard.length_mm || 0),
      price_per_board: Number(primaryBoard.price_per_board || 0),
    },
    panels: (payload.panels || []).map((p) => {
      const board = p.board || primaryBoard;
      return {
        label: p.label,
        width: Number(p.width || 0),
        length: Number(p.length || 0),
        quantity: Number(p.quantity || 1),
        alignment: p.alignment || 'none',
        notes: p.notes || '',
        edging: normalizeEdges(p.edging),
        board_item_id: board?.board_item_id,
        board_type: board?.board_type || '',
        thickness_mm: Number(board?.thickness_mm || 0),
        company: board?.company || '',
        color_name: board?.color_name || '',
        price_per_board: Number(board?.price_per_board || 0),
      };
    }),
    options: {
      kerf: Number(payload.options?.kerf || 3),
      allow_rotation: true,
      consider_grain: !!payload.options?.consider_grain,
      generate_cuts: true,
    },
  };
}

export const api = {
  checkHealth: () =>
    request<{ status: string; timestamp?: string; version?: string }>('/health'),

  optimize: (payload: BackendCuttingRequest) =>
    request<any>('/api/optimize', {
      method: 'POST',
      body: JSON.stringify(normalizeOptimizePayload(payload)),
    }),

  exportReportPdf: async (payload: BackendCuttingRequest): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/api/optimize/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(normalizeOptimizePayload(payload)),
    });
    if (!response.ok) throw new Error(`Failed to export report PDF (${response.status})`);
    return response.blob();
  },

  exportLabelsPdf: async (payload: BackendCuttingRequest): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/api/optimize/labels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(normalizeOptimizePayload(payload)),
    });
    if (!response.ok) throw new Error(`Failed to export labels PDF (${response.status})`);
    return response.blob();
  },

  getBoardCatalog: (): Promise<BoardCatalog> => request('/api/boards/catalog'),

  getBoardItems: (): Promise<BoardItem[]> => request('/api/boards-admin/'),

  createBoardItem: (payload: Omit<BoardItem, 'id'>): Promise<BoardItem> =>
    request('/api/boards-admin/', { method: 'POST', body: JSON.stringify(payload) }),

  updateBoardItem: (id: number, payload: Partial<BoardItem>): Promise<BoardItem> =>
    request(`/api/boards-admin/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  deleteBoardItem: (id: number): Promise<void> =>
    request(`/api/boards-admin/${id}`, { method: 'DELETE' }),

  addBoardStock: (payload: StockAdjustmentRequest): Promise<BoardItem> =>
    request('/api/boards-admin/add', { method: 'POST', body: JSON.stringify(payload) }),

  deductBoardStock: (payload: StockAdjustmentRequest): Promise<BoardItem> =>
    request('/api/boards-admin/deduct', { method: 'POST', body: JSON.stringify(payload) }),

  getBoardTransactions: (boardItemId: number): Promise<StockTransaction[]> =>
    request(`/api/boards-admin/transactions/${boardItemId}`),

  openInventoryPdf: () => {
    window.open(`${API_BASE}/api/boards-admin/print-pdf`, '_blank');
  },

  getJob: (reportId: string): Promise<any> => request(`/api/jobs/${reportId}`),

  confirmJob: (reportId: string): Promise<JobConfirmResponse> =>
    request(`/api/jobs/confirm/${reportId}`, { method: 'POST' }),

  getTracking: (serialNumber: string): Promise<StickerTrackingResponse> =>
    request(`/api/tracking/${encodeURIComponent(serialNumber)}`),

  updateTrackingStatus: (
    serialNumber: string,
    status: 'in_store' | 'out_for_delivery' | 'delivered',
    adminApiKey?: string,
  ): Promise<any> =>
    request(`/api/tracking/${encodeURIComponent(serialNumber)}/status`, {
      method: 'POST',
      headers: getAdminHeaders(adminApiKey),
      body: JSON.stringify({ status }),
    }),

  advanceTrackingStatus: (
    serialNumber: string,
    adminApiKey?: string,
  ): Promise<any> =>
    request(`/api/tracking/${encodeURIComponent(serialNumber)}/advance`, {
      method: 'POST',
      headers: getAdminHeaders(adminApiKey),
      body: JSON.stringify({}),
    }),
};
