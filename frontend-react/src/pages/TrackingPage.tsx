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
      setMessage('');
      const resp = await api.advanceTrackingStatus(serialNo, adminKey || undefined);
      setTracking(resp.tracking);
      setMessage(`Status updated to ${resp.tracking.status}`);
    } catch (error: any) {
      setMessage(error?.message || 'Failed to update status');
    } finally {
      setUpdating(false);
    }
  };

  const handleSetStatus = async (status: 'in_store' | 'out_for_delivery' | 'delivered') => {
    try {
      setUpdating(true);
      setMessage('');
      const resp = await api.updateTrackingStatus(serialNo, status, adminKey || undefined);
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
      <div className="min-h-screen bg-slate-100 flex items-center justify-center px-4">
        <div className="bg-white rounded-2xl shadow-xl p-6 sm:p-8 w-full max-w-md text-center">
          Loading tracking info...
        </div>
      </div>
    );
  }

  if (!tracking) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center px-4">
        <div className="bg-white rounded-2xl shadow-xl p-6 sm:p-8 w-full max-w-lg">
          <h1 className="text-2xl font-bold mb-2">Tracking Not Found</h1>
          <p className="text-gray-600 break-words">{message || 'No tracking record found.'}</p>
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

  const autoButtonLabel =
    tracking.status === 'in_store'
      ? 'Mark Out For Delivery'
      : tracking.status === 'out_for_delivery'
      ? 'Mark Delivered'
      : 'Already Delivered';

  const autoButtonDisabled = tracking.status === 'delivered' || updating;

  const formattedUpdatedAt = tracking.updated_at
    ? new Date(tracking.updated_at).toLocaleString()
    : '-';

  return (
    <div className="min-h-screen bg-slate-100 py-6 sm:py-10 px-3 sm:px-4">
      <div className="max-w-2xl mx-auto bg-white rounded-2xl shadow-xl p-4 sm:p-6 lg:p-8 space-y-5 sm:space-y-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Sticker Tracking</h1>
          <p className="text-sm sm:text-base text-gray-500 mt-1 break-all">
            Serial: {tracking.serial_number}
          </p>
        </div>

        <div className="grid gap-4">
          <div className="bg-slate-50 rounded-xl p-4">
            <p className="text-sm text-gray-500">Panel Label</p>
            <p className="font-semibold text-base sm:text-lg break-words">{tracking.panel_label}</p>
          </div>

          <div className="bg-slate-50 rounded-xl p-4">
            <p className="text-sm text-gray-500">Report ID</p>
            <p className="font-semibold text-base sm:text-lg break-all">{tracking.report_id}</p>
          </div>

          <div className="bg-slate-50 rounded-xl p-4">
            <p className="text-sm text-gray-500">Board Number</p>
            <p className="font-semibold text-base sm:text-lg">{tracking.board_number ?? '-'}</p>
          </div>

          <div className="bg-slate-50 rounded-xl p-4">
            <p className="text-sm text-gray-500">Current Status</p>
            <span
              className={`inline-block mt-2 px-4 py-2 rounded-full font-semibold text-sm sm:text-base ${statusColor}`}
            >
              {tracking.status}
            </span>
          </div>

          <div className="bg-slate-50 rounded-xl p-4">
            <p className="text-sm text-gray-500">Last Updated</p>
            <p className="font-semibold text-base sm:text-lg break-words">
              {formattedUpdatedAt}
            </p>
          </div>
        </div>

        <div className="border rounded-xl p-4 space-y-4">
          <h2 className="text-lg sm:text-xl font-semibold text-gray-900">Quick Status Advance</h2>
          <p className="text-sm text-gray-600">
            This button advances:
            <strong> in_store → out_for_delivery → delivered</strong>
          </p>

          <input
            type="password"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            placeholder="Admin API Key (optional in test mode)"
            className="w-full border border-gray-300 rounded-xl px-4 py-3"
          />

          <button
            onClick={handleAdvance}
            disabled={autoButtonDisabled}
            className={`w-full px-4 py-3 rounded-xl text-white font-semibold transition ${
              tracking.status === 'in_store'
                ? 'bg-blue-600 hover:bg-blue-700'
                : tracking.status === 'out_for_delivery'
                ? 'bg-green-600 hover:bg-green-700'
                : 'bg-gray-400 cursor-not-allowed'
            }`}
          >
            {updating ? 'Updating...' : autoButtonLabel}
          </button>
        </div>

        <div className="border rounded-xl p-4 space-y-4">
          <h2 className="text-lg sm:text-xl font-semibold text-gray-900">Manual Status Override</h2>
          <p className="text-sm text-gray-600">
            Use only if you need to manually correct the status.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <button
              onClick={() => handleSetStatus('in_store')}
              disabled={updating}
              className="w-full px-4 py-3 rounded-xl bg-yellow-500 text-white font-semibold disabled:opacity-60"
            >
              Mark In Store
            </button>

            <button
              onClick={() => handleSetStatus('out_for_delivery')}
              disabled={updating}
              className="w-full px-4 py-3 rounded-xl bg-blue-600 text-white font-semibold disabled:opacity-60"
            >
              Mark Out For Delivery
            </button>

            <button
              onClick={() => handleSetStatus('delivered')}
              disabled={updating}
              className="w-full px-4 py-3 rounded-xl bg-green-600 text-white font-semibold disabled:opacity-60"
            >
              Mark Delivered
            </button>
          </div>
        </div>

        {tracking.qr_url && (
          <div className="bg-slate-50 rounded-xl p-4">
            <p className="text-sm text-gray-500 mb-1">QR URL</p>
            <a
              href={tracking.qr_url}
              className="text-blue-600 underline break-all text-sm sm:text-base"
              target="_blank"
              rel="noreferrer"
            >
              {tracking.qr_url}
            </a>
          </div>
        )}

        {message && (
          <div className="p-4 rounded-xl bg-orange-50 text-orange-700 text-sm sm:text-base break-words">
            {message}
          </div>
        )}
      </div>
    </div>
  );
}
