import type { ReactNode } from 'react';
import { Layers3, ClipboardList, Wifi, WifiOff, Loader } from 'lucide-react'; // ✅ replaced LoaderCircle with Loader
import { useApiStatus } from '../../hooks/useApiStatus';

interface MainLayoutProps {
  children: ReactNode;
  currentStep: number;
  onStepChange: (step: number) => void;
  projectName?: string;
  canNavigate?: boolean;
}

export function MainLayout({
  children,
  currentStep,
  onStepChange,
  projectName,
  canNavigate = false,
}: MainLayoutProps) {
  const { isOnline, checking } = useApiStatus();

  return (
    <div className="min-h-screen bg-gray-100 flex">
      {/* Sidebar */}
      <aside className="w-[320px] bg-[#07142b] text-white flex flex-col shadow-2xl">
        <div className="px-6 py-8 border-b border-white/10">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-orange-500 flex items-center justify-center text-white font-bold text-lg shadow">
              /
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">PanelPro</h1>
              <p className="text-sm text-gray-300">CUTTING OPTIMIZER</p>
            </div>
          </div>

          {/* API Status */}
          <div className="flex items-center gap-2 mt-4">
            <span className="text-sm text-gray-300">API:</span>

            <div
              className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${
                checking
                  ? 'bg-yellow-100 text-yellow-700'
                  : isOnline
                  ? 'bg-green-100 text-green-700'
                  : 'bg-red-100 text-red-700'
              }`}
            >
              {checking ? (
                <>
                  <Loader className="w-4 h-4 animate-spin" /> {/* ✅ updated */}
                  Checking...
                </>
              ) : isOnline ? (
                <>
                  <Wifi className="w-4 h-4" />
                  Online
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4" />
                  Offline
                </>
              )}
            </div>
          </div>
        </div>

        {/* Workflow */}
        <div className="px-6 py-6 border-b border-white/10">
          <h2 className="text-sm uppercase tracking-wider text-gray-400 mb-4">Workflow</h2>

          <div className="space-y-3">
            <button
              type="button"
              onClick={() => onStepChange(1)}
              className={`w-full flex items-center gap-3 px-4 py-4 rounded-2xl text-left transition-all ${
                currentStep === 1
                  ? 'bg-orange-600 text-white shadow-lg'
                  : 'bg-transparent text-gray-300 hover:bg-white/5'
              }`}
            >
              <Layers3 className="w-5 h-5" />
              <span className="font-medium text-lg">Panels & Board</span>
            </button>

            <button
              type="button"
              onClick={() => onStepChange(2)}
              disabled={!canNavigate}
              className={`w-full flex items-center gap-3 px-4 py-4 rounded-2xl text-left transition-all ${
                currentStep === 2
                  ? 'bg-orange-600 text-white shadow-lg'
                  : canNavigate
                  ? 'bg-transparent text-gray-300 hover:bg-white/5'
                  : 'bg-transparent text-gray-500 cursor-not-allowed opacity-60'
              }`}
            >
              <ClipboardList className="w-5 h-5" />
              <span className="font-medium text-lg">Results & Payment</span>
            </button>
          </div>
        </div>

        {/* Project info */}
        <div className="px-6 py-6">
          <h2 className="text-sm uppercase tracking-wider text-gray-400 mb-4">Project</h2>
          <div className="text-xl text-gray-300 leading-relaxed">
            {projectName ? projectName : 'No project yet'}
          </div>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Footer */}
        <div className="px-6 py-4 border-t border-white/10 text-xs text-gray-400">
          PanelPro Production Suite
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0">
        {children}
      </main>
    </div>
  );
}