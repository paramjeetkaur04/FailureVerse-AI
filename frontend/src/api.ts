export type Service = {
  id: string;
  name: string;
  kind: 'api' | 'database' | 'application';
  status: 'healthy' | 'unavailable' | 'degraded';
  latency_ms: number | null;
  detail: string;
  measurement: 'actual';
};

export type Check = {
  id: string;
  checked_at: string;
  source: 'startup' | 'manual';
  services: Service[];
};

export type Overview = {
  project: string;
  phase: number;
  environment: string;
  healthy_services: number;
  total_services: number;
  saved_checks: number;
  latest: Check | null;
  history: Check[];
};

export type Config = {
  environment: string;
  database: string;
  demo_health_url: string;
  check_timeout_seconds: number;
  history_limit: number;
  ai_provider: string;
  ollama_model: string;
  ai_enabled: boolean;
  docker_control_enabled: boolean;
  phase: number;
};

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
    signal: AbortSignal.timeout(12000),
  });
  if (!response.ok) {
    let detail = `Request failed (HTTP ${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') detail = body.detail;
    } catch { /* Preserve the HTTP error when a proxy returns HTML. */ }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  overview: () => request<Overview>('/overview'),
  config: () => request<Config>('/config'),
  runCheck: () => request<Check>('/checks', { method: 'POST', body: JSON.stringify({ source: 'manual' }) }),
};
