import { useMemo, useState } from 'react';
import { MainLayout } from './components/layout/MainLayout';
import { StepPanels } from './pages/StepPanels';
import { StepResults } from './pages/StepResults';
import AdminStockPage from './pages/AdminStockPage';
import TrackingPage from './pages/TrackingPage';
import { ToastContainer, ToastProps } from './components/ui/Toast';
import { api } from './api/client';
import { mapToCuttingRequest } from './utils/mapToCuttingRequest';

import type {
  Panel,
  OptimizationOptions,
  CustomerDetails,
  CuttingResponse,
  BackendCuttingRequest,
} from './types';

type ViewMode = 'main' | 'admin-stock';

function App() {
  const pathname = window.location.pathname;
  const trackingSerial = useMemo(() => {
    const match = pathname.match(/^\/track\/(.+)$/);
    return match ? decodeURIComponent(match[1]) : null;
  }, [pathname]);

  const [viewMode, setViewMode] = useState<ViewMode>('main');
  const [currentStep, setCurrentStep] = useState(1);
  const [panels, setPanels] = useState<Panel[]>([]);
  const [options, setOptions] = useState<OptimizationOptions>({
    kerf: 3,
    labels_on_panels: true,
    use_single_sheet: false,
    consider_material: true,
    edge_banding: true,
    consider_grain: false,
  });
  const [customer, setCustomer] = useState<CustomerDetails>({
    project_name: '',
    customer_name: '',
    notes: '',
  });
  const [results, setResults] = useState<CuttingResponse | null>(null);
  const [toasts, setToasts] = useState<ToastProps[]>([]);
  const [isOptimizing, setIsOptimizing] = useState(false);

  const addToast = (type: 'success' | 'error' | 'info', message: string) => {
    const id = Date.now().toString();
    setToasts((prev) => [...prev, { id, type, message, onClose: () => removeToast(id) }]);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const handleOptimize = async () => {
    if (panels.length === 0) {
      addToast('error', 'Please add at least one panel before optimizing');
      return;
    }

    if (!customer.project_name || !customer.customer_name) {
      addToast('error', 'Please fill in project name and customer name');
      return;
    }

    setIsOptimizing(true);

    try {
      const payload: BackendCuttingRequest = mapToCuttingRequest({
        panels,
        options,
        customer,
      });

      const response = await api.optimize(payload);
      setResults(response);
      setCurrentStep(2);
      addToast('success', 'Optimization completed successfully!');
    } catch (error) {
      addToast('error', error instanceof Error ? error.message : 'Optimization failed');
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleStepChange = (step: number) => {
    if (step === 2 && !results) {
      addToast('info', 'Please complete optimization first');
      return;
    }
    setCurrentStep(step);
  };

  const requestData: BackendCuttingRequest | null =
    panels.length > 0
      ? mapToCuttingRequest({
          panels,
          options,
          customer,
        })
      : null;

  if (trackingSerial) {
    return <TrackingPage serialNo={trackingSerial} />;
  }

  if (viewMode === 'admin-stock') {
    return (
      <>
        <AdminStockPage onBack={() => setViewMode('main')} />
        <ToastContainer toasts={toasts} onRemove={removeToast} />
      </>
    );
  }

  return (
    <>
      <MainLayout
        currentStep={currentStep}
        onStepChange={handleStepChange}
        projectName={customer.project_name}
        canNavigate={results !== null}
      >
        {currentStep === 1 ? (
          <StepPanels
            panels={panels}
            onPanelsChange={setPanels}
            options={options}
            onOptionsChange={setOptions}
            customer={customer}
            onCustomerChange={setCustomer}
            onNext={handleOptimize}
            onOpenAdminStock={() => setViewMode('admin-stock')}
          />
        ) : (
          <StepResults
            results={results}
            requestData={requestData}
            onBack={() => setCurrentStep(1)}
            projectName={customer.project_name}
            customerName={customer.customer_name}
          />
        )}

        {isOptimizing && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-8 shadow-2xl">
              <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-orange-600 mx-auto mb-4"></div>
              <p className="text-lg font-semibold text-gray-900">Optimizing layout...</p>
              <p className="text-sm text-gray-500 mt-2">This may take a moment</p>
            </div>
          </div>
        )}
      </MainLayout>

      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </>
  );
}

export default App;