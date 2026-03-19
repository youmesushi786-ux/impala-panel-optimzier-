import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { StickerTrackingResponse } from '../types';

interface Props {
  serialNo: string;
}

export default function TrackingPage({ serialNo }: Props) {
  const [tracking, setTracking] = useState<StickerTrackingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [adminKey, setAdminKey] = useState('');
  const [updating, setUpdating] = useState(false);

  const loadTracking = async () => {
    try {
      setLoading(true);
      const data = await api.getTracking(serialNo);
      setTracking(data);
      setMessage('');
    } catch (error: any) {
      setMessage(error?.message || 'Failed to load tracking info');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTracking();
  }, [serialNo]);

  const handleAdvance = async () => {
    try {
      setUpdating(true);
      const resp = await api.advanceTrackingStatus(serialNo, adminKey || undefined);
      setTracking(resp.tracking);
      setMessage(`Status updated to ${resp.tracking.status}`);
    } catch (error: any) {
      setMessage(error?.message || 'Failed to update status');
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100">
        <div className="bg-white rounded-xl shadow p-6">Loading tracking info...</div>
      </div>
    );
  }

  if (!tracking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100">
        <div className="bg-white rounded-xl shadow p-6">
          <h2 className="text-xl font-bold mb-2">Tracking Not Found</h2>
          <p className="text-gray-600">{message || 'No tracking record found.'}</p>
        </div>
      </div>
    );
  }

  const statusColor =
    tracking.status === 'in_store'
      ? 'bg-yellow-100 text-yellow-800'
      : tracking.status === 'out_for_delivery'
      ? 'bg-blue-100 text-blue-800'
      : 'bg-green-100 text-green-800';

  return (
    <div className="min-h-screen bg-slate-100 py-10 px-4">
      <div className="max-w-2xl mx-auto bg-white rounded-2xl shadow-xl p-8 space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Sticker Tracking</h1>
          <p className="text-gray-500 mt-1">Serial: {tracking.serial_number}</p>
        </div>

        <div className="grid gap-4">
          <div className="bg-slate-50 rounded-xl p-4">
            <p className="text-sm text-gray-500">Panel Label</p>
            <p className="font-semibold text-lg">{tracking.panel_label}</p>
          </div>

          <div className="bg-slate-50 rounded-xl p-4">
            <p className="text-sm text-gray-500">Report ID</p>
            <p className="font-semibold text-lg">{tracking.report_id}</p>
          </div>

          <div className="bg-slate-50 rounded-xl p-4">
            <p className="text-sm text-gray-500">Board Number</p>
            <p className="font-semibold text-lg">{tracking.board_number ?? '-'}</p>
          </div>

          <div className="bg-slate-50 rounded-xl p-4">
            <p className="text-sm text-gray-500">Current Status</p>
            <span className={`inline-block mt-2 px-4 py-2 rounded-full font-semibold ${statusColor}`}>
              {tracking.status}
            </span>
          </div>

          <div className="bg-slate-50 rounded-xl p-4">
            <p className="text-sm text-gray-500">Last Updated</p>
            <p className="font-semibold text-lg">
              {new Date(tracking.updated_at).toLocaleString()}
            </p>
          </div>
        </div>

        <div className="border rounded-xl p-4 space-y-4">
          <h2 className="text-xl font-semibold text-gray-900">Advance Status</h2>
          <p className="text-sm text-gray-600">
            in_store → out_for_delivery → delivered
          </p>

          <input
            type="password"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            placeholder="Admin API Key (if required)"
            className="w-full border border-gray-300 rounded-xl px-4 py-3"
          />

          <button
            onClick={handleAdvance}
            disabled={updating || tracking.status === 'delivered'}
            className={`w-full px-4 py-3 rounded-xl text-white font-semibold ${
              tracking.status === 'in_store'
                ? 'bg-blue-600 hover:bg-blue-700'
                : tracking.status === 'out_for_delivery'
                ? 'bg-green-600 hover:bg-green-700'
                : 'bg-gray-400 cursor-not-allowed'
            }`}
          >
            {updating
              ? 'Updating...'
              : tracking.status === 'in_store'
              ? 'Mark Out For Delivery'
              : tracking.status === 'out_for_delivery'
              ? 'Mark Delivered'
              : 'Already Delivered'}
          </button>
        </div>

        {message && (
          <div className="p-4 rounded-xl bg-orange-50 text-orange-700">
            {message}
          </div>
        )}
      </div>
    </div>
  );
}