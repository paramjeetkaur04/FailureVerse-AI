import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type Config, type Overview } from './api';

export function useWorkspace() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const checking = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const [next, settings] = await Promise.all([api.overview(), api.config()]);
      setOverview(next);
      setConfig(settings);
      setError(null);
      setConnected(true);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Unable to reach the backend.');
      setConnected(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      if (!checking.current) void refresh();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const runCheck = async () => {
    if (checking.current) return;
    checking.current = true;
    setBusy(true);
    try {
      await api.runCheck();
      await refresh();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The health check failed.');
    } finally {
      checking.current = false;
      setBusy(false);
    }
  };

  return { overview, config, loading, busy, connected, error, refresh, runCheck };
}
