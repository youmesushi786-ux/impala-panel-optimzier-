import { useEffect, useMemo, useState } from 'react';
import { MainLayout } from './components/layout/MainLayout';
import { StepPanels } from './pages/StepPanels';
import { StepResults } from './pages/StepResults';
import AdminStockPage from './pages/AdminStockPage';
import TrackingPage from './pages/TrackingPage';
import { ToastContainer, ToastProps } from './components/ui/Toast';
import { api } from './api/client';
import { mapToCuttingRequest } from './utils/mapToCuttingRequest';
import type { Panel, OptimizationOptions, CustomerDetails, CuttingResponse } from './types';

export default function App() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const h = () => setHash(window.location.hash);
    window.addEventListener('hashchange', h);
    return () => window.removeEventListener('hashchange', h);
  }, []);

  const trackingSerial = useMemo(() => {
    const m = hash.match(/^#\/track\/(.+)$/);
    return m ? decodeURIComponent(m[1]) : null;
  }, [hash]);

  const [view, setView] = useState('optimize');
  const [panels, setPanels] = useState<Panel[]>([]);
  const [results, setResults] = useState<CuttingResponse | null>(null);
  const [toasts, setToasts] = useState<ToastProps[]>([]);
  const [optimizing, setOptimizing] = useState(false);

  const [options, setOptions] = useState<OptimizationOptions>({
    kerf: 3, labels_on_panels: true, use_single_sheet: false,
    consider_material: true, edge_banding: true, consider_grain: false,
  });
  const [customer, setCustomer] = useState<CustomerDetails>({ project_name: '', customer_name: '', notes: '' });

  const addToast = (type: ToastProps['type'], message: string, title?: string) => {
    const id = Date.now().toString();
    setToasts((t) => [...t, { id, type, message, title, onClose: () => removeToast(id) }]);
  };
  const removeToast = (id: string) => setToasts((t) => t.filter((x) => x.id !== id));

  const handleOptimize = async () => {
    if (panels.length === 0) return addToast('error', 'Add at least one panel');
    if (!customer.project_name || !customer.customer_name) return addToast('error', 'Fill project & customer name');
    setOptimizing(true);
    try {
      const payload = mapToCuttingRequest({ panels, options, customer });
      const res = await api.optimize(payload);
      setResults(res);
      setView('results');
      addToast('success', 'Optimization complete!', 'Success');
    } catch (e: any) {
      addToast('error', e.message || 'Optimization failed');
    } finally { setOptimizing(false); }
  };

  const requestData = panels.length > 0 ? mapToCuttingRequest({ panels, options, customer }) : null;

  if (trackingSerial) return <TrackingPage serialNo={trackingSerial} />;

  const renderView = () => {
    switch (view) {
      case 'results': return <StepResults results={results} requestData={requestData} onBack={() => setView('optimize')} />;
      case 'stock': return <AdminStockPage onBack={() => setView('optimize')} />;
      case 'tracking': return <div className="p-8 text-center text-slate-500">Scan a QR code or navigate to #/track/[serial]</div>;
      default: return (
        <StepPanels
          panels={panels} onPanelsChange={setPanels}
          options={options} onOptionsChange={setOptions}
          customer={customer} onCustomerChange={setCustomer}
          onNext={handleOptimize}
          onOpenAdminStock={() => setView('stock')}
        />
      );
    }
  };

  return (
    <>
      <MainLayout currentView={view} onViewChange={setView} projectName={customer.project_name}>
        {renderView()}
      </MainLayout>

      {optimizing && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center">
          <div className="text-center">
            <div className="relative w-24 h-24 mx-auto mb-4">
              <div className="absolute inset-0 border-4 border-amber-500/20 rounded-full" />
              <div className="absolute inset-0 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
            </div>
            <p className="text-xl font-display font-bold text-white">Optimizing Layout</p>
            <p className="text-sm text-slate-400 mt-2">Computing best material arrangement...</p>
          </div>
        </div>
      )}

      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </>
  );
}
