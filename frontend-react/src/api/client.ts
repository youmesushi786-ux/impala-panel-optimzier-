import type {
  BackendCuttingRequest,
  BoardCatalog,
  BoardItem,
  StockAdjustmentRequest,
  StockTransaction,
  JobConfirmResponse,
  StickerTrackingResponse,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

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

export const api = {
  optimize: (payload: BackendCuttingRequest) =>
    request<any>('/api/optimize', { method: 'POST', body: JSON.stringify(payload) }),

  exportReportPdf: async (payload: BackendCuttingRequest): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/api/optimize/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`Failed to export report PDF (${response.status})`);
    return response.blob();
  },

  exportLabelsPdf: async (payload: BackendCuttingRequest): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/api/optimize/labels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
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
      headers: adminApiKey ? { 'x-api-key': adminApiKey } : {},
      body: JSON.stringify({ status }),
    }),

  advanceTrackingStatus: (
    serialNumber: string,
    adminApiKey?: string,
  ): Promise<any> =>
    request(`/api/tracking/${encodeURIComponent(serialNumber)}/advance`, {
      method: 'POST',
      headers: adminApiKey ? { 'x-api-key': adminApiKey } : {},
    }),
};