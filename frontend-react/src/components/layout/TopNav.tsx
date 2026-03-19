import { useEffect, useState } from 'react';
import { Box } from 'lucide-react';
import { api } from '../../api/client';

type ApiStatus = 'checking' | 'healthy' | 'offline';

export function TopNav() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking');

  useEffect(() => {
    let isMounted = true;

    const checkHealth = async () => {
      try {
        await api.checkHealth();
        if (isMounted) {
          setApiStatus('healthy');
        }
      } catch {
        if (isMounted) {
          setApiStatus('offline');
        }
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const statusColors: Record<ApiStatus, string> = {
    checking: 'bg-yellow-500',
    healthy: 'bg-green-500',
    offline: 'bg-red-500',
  };

  const statusLabels: Record<ApiStatus, string> = {
    checking: 'Checking',
    healthy: 'Healthy',
    offline: 'Offline',
  };

  return (
    <nav className="bg-gray-900 text-white shadow-lg z-50 sticky top-0">
      <div className="px-4 sm:px-6 py-3 sm:py-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4">
        <div className="flex items-center gap-3 sm:gap-4">
          <div className="w-9 h-9 sm:w-10 sm:h-10 perspective-1000">
            <div
              className="w-full h-full animate-rotate-cube"
              style={{ transformStyle: 'preserve-3d' }}
            >
              <Box className="w-9 h-9 sm:w-10 sm:h-10 text-orange-500" />
            </div>
          </div>
          <div>
            <h1 className="text-lg sm:text-xl font-bold">PanelPro</h1>
            <p className="text-[10px] sm:text-xs text-gray-400 uppercase tracking-wide">
              Cutting Optimizer
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] sm:text-xs text-gray-400 uppercase tracking-wide">
            API:
          </span>
          <div
            className={`px-2.5 sm:px-3 py-1 rounded-full text-[10px] sm:text-xs font-medium flex items-center gap-1.5 sm:gap-2 bg-opacity-20 ${statusColors[apiStatus]}`}
            role="status"
            aria-label={`API status: ${statusLabels[apiStatus]}`}
          >
            <span
              className={`w-2 h-2 rounded-full ${statusColors[apiStatus]}`}
            />
            <span>{statusLabels[apiStatus]}</span>
          </div>
        </div>
      </div>
    </nav>
  );
}