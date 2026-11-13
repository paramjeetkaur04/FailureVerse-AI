import type { Config, Overview } from '../api';

// Test fixtures only. Production always requests the backend.
export const overview: Overview = {
  project: 'FailureVerse AI', phase: 1, environment: 'test',
  healthy_services: 2, total_services: 3, saved_checks: 1,
  latest: {
    id: 'test-record-1', checked_at: '2026-11-13T07:00:00Z', source: 'startup',
    services: [
      { id: 'backend', name: 'FailureVerse API', kind: 'api', status: 'healthy', latency_ms: null, detail: 'Backend responding.', measurement: 'actual' },
      { id: 'database', name: 'SQLite database', kind: 'database', status: 'healthy', latency_ms: 1.25, detail: 'Measured SELECT 1.', measurement: 'actual' },
      { id: 'demo', name: 'Flask demo application', kind: 'application', status: 'unavailable', latency_ms: null, detail: 'Demo check failed.', measurement: 'actual' },
    ],
  },
  history: [],
};
overview.history = [overview.latest!];

export const config: Config = {
  environment: 'test', database: 'SQLite', demo_health_url: 'http://127.0.0.1:5001/health',
  check_timeout_seconds: 2, history_limit: 120, ai_provider: 'Ollama', ollama_model: 'qwen3:8b',
  ai_enabled: false, docker_control_enabled: false, phase: 1,
};
