import { useEffect, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export function useApiStatus() {
  const [isOnline, setIsOnline] = useState<boolean>(false);
  const [checking, setChecking] = useState<boolean>(true);

  useEffect(() => {
    let active = true;

    const checkApi = async () => {
      try {
        const response = await fetch(`${API_BASE}/health`);
        if (!active) return;

        setIsOnline(response.ok);
      } catch {
        if (!active) return;
        setIsOnline(false);
      } finally {
        if (!active) return;
        setChecking(false);
      }
    };

    checkApi();

    const interval = setInterval(checkApi, 10000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return { isOnline, checking };
}