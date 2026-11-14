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

export type Evidence = { id: string; tool: string; observed_at: string; measurement: 'actual' | 'simulated'; data: Record<string, unknown> };
export type Finding = { statement: string; evidence_ids: string[]; claim_id?: string | null; source_fields?: string[] };
export type Report = { summary: string; observations: Finding[]; suspected_root_causes: Finding[]; uncertainties: string[]; recommended_actions: Finding[];
  grounding_version?: 'legacy' | '2.1'; outcome?: 'conclusions' | 'insufficient_evidence'; summary_evidence_ids?: string[];
  limitations?: Finding[]; model_selection_accepted?: boolean | null; validation_notes?: string[] };
export type Investigation = {
  id: string; target: string; question: string; model: string; status: string;
  created_at: string; finished_at: string | null; model_calls: number; tool_calls: number;
  report: Report | null; error: string | null; evidence: Evidence[];
  events: { sequence: number; at: string; kind: string; title: string; tool?: string; selected_tools?: string[]; duration_ms?: number }[];
  limits: { model_calls: number; tool_calls: number; deadline_seconds: number };
};
export type RunSummary = Pick<Investigation, 'id' | 'question' | 'status' | 'model' | 'created_at' | 'model_calls' | 'tool_calls'>;
export type AgentStatus = {
  ready: boolean; enabled: boolean; state: string; detail: string; model: string;
  active_run_id: string | null; limits: Investigation['limits'];
  targets: { id: string; name: string }[];
};
export const investigationApi = {
  status: () => request<AgentStatus>('/ai/status'),
  list: () => request<RunSummary[]>('/investigations'),
  get: (id: string) => request<Investigation>(`/investigations/${encodeURIComponent(id)}`),
  start: (question: string) => request<Investigation>('/investigations', { method: 'POST', body: JSON.stringify({ target: 'demo', question }) }),
  cancel: (id: string) => request<Investigation>(`/investigations/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
};
