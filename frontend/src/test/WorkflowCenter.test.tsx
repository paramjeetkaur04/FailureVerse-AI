import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import WorkflowCenter from '../components/WorkflowCenter';
import { investigationApi, workflowApi, type AgentStatus, type AgentWorkflow } from '../api';

vi.mock('../api', () => ({ investigationApi: { status: vi.fn() }, workflowApi: {
  list: vi.fn(), get: vi.fn(), start: vi.fn(), cancel: vi.fn(), resume: vi.fn(),
} }));
const provider: AgentStatus = { ready: true, enabled: true, state: 'ready', detail: 'Test provider', model: 'test-model',
  active_run_id: null, active_workflow_id: null, targets: [], limits: { model_calls: 4, tool_calls: 6, deadline_seconds: 180 } };
const run: AgentWorkflow = {
  id: 'test-workflow', target: 'demo', question: 'Investigate demo health', investigate_healthy: false,
  model: 'test-model', status: 'observed_healthy', created_at: '2026-11-15T12:00:00Z', expires_at: '2026-11-15T12:05:00Z',
  finished_at: '2026-11-15T12:00:10Z', error: null, resumable: false, execution_enabled: false,
  limits: { model_calls: 7, tool_calls: 9, deadline_seconds: 300 },
  checkpoint: { version: 1, next_stage: 'done', model_calls: 0, tool_calls: 3, role_models: {}, role_tools: { monitoring: 3 },
    evidence: [{ id: 'test.M1', tool: 'inspect_container', measurement: 'actual', observed_at: '2026-11-15T12:00:01Z', data: { running: true } }],
    investigation_evidence: [], monitoring: { state: 'healthy', signals: [], missing: [], evidence_ids: ['test.M1'] },
    investigation: null, specialists: {}, outcome: 'observed_healthy' },
  events: [{ sequence: 1, at: '2026-11-15T12:00:10Z', role: 'monitoring', kind: 'checkpoint', title: 'Monitoring stage completed; checkpoint saved' }],
};

beforeEach(() => {
  vi.mocked(investigationApi.status).mockResolvedValue(provider);
  vi.mocked(workflowApi.list).mockResolvedValue([]);
  vi.mocked(workflowApi.get).mockResolvedValue(run);
  vi.mocked(workflowApi.start).mockResolvedValue(run);
  vi.mocked(workflowApi.cancel).mockResolvedValue({ ...run, status: 'cancelled', error: 'Workflow cancelled. Evidence retained.' });
  vi.mocked(workflowApi.resume).mockResolvedValue({ ...run, status: 'running', finished_at: null, resumable: false });
});

it('allows monitoring while the model is offline but requires readiness for forced investigation', async () => {
  vi.mocked(investigationApi.status).mockResolvedValue({ ...provider, ready: false, state: 'unavailable', detail: 'Ollama unavailable.' });
  const user = userEvent.setup();
  render(<WorkflowCenter />);
  expect(await screen.findByText(/AI provider: Ollama unavailable/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Start workflow' })).toBeEnabled();
  await user.click(screen.getByRole('checkbox'));
  expect(screen.getByRole('button', { name: 'Start workflow' })).toBeDisabled();
});

it('starts through the API and honestly skips AI stages after healthy monitoring', async () => {
  const user = userEvent.setup();
  render(<WorkflowCenter />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Start workflow' })).toBeEnabled());
  await user.click(screen.getByRole('button', { name: 'Start workflow' }));
  expect(workflowApi.start).toHaveBeenCalledWith('Investigate current demo container health.', false);
  expect(await screen.findByText(/Configured health and memory checks detected no failure signal/)).toBeInTheDocument();
  expect(screen.getAllByText('skipped')).toHaveLength(4);
  expect(screen.queryByRole('heading', { name: 'Recovery planning' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'M1' })).toHaveAttribute('href', '#workflow-evidence-test.M1');
});

it('shows planning proposals with explicit execution boundaries and their source citations', async () => {
  const planned: AgentWorkflow = { ...run, status: 'awaiting_review', checkpoint: { ...run.checkpoint, outcome: 'awaiting_review',
    specialists: { recovery: { role: 'recovery', method: 'ollama_catalog_selection', execution_enabled: false, plan_hash: 'a'.repeat(64),
      items: [{ claim_id: 'P1', action: 'repeat_read_only_checks', statement: 'Proposed repeat of read-only checks.', evidence_ids: ['test.M1'], execution_enabled: false }] } } } };
  vi.mocked(workflowApi.list).mockResolvedValue([{ ...planned, next_stage: 'done', model_calls: 4, tool_calls: 5 }]);
  vi.mocked(workflowApi.get).mockResolvedValue(planned);
  render(<WorkflowCenter />);
  expect(await screen.findByRole('heading', { name: 'Recovery planning' })).toBeInTheDocument();
  expect(screen.getByText('Proposed repeat of read-only checks.')).toBeInTheDocument();
  expect(screen.getByText(/Execution is disabled/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /execute|approve|restart/i })).not.toBeInTheDocument();
});

it('blocks starting when a legacy investigation owns the shared slot', async () => {
  vi.mocked(investigationApi.status).mockResolvedValue({ ...provider, active_run_id: 'legacy-run' });
  render(<WorkflowCenter />);
  expect(await screen.findByText(/Another run owns the execution slot/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Start workflow' })).toBeDisabled();
});

it('cancels the actual selected workflow and keeps partial evidence visible', async () => {
  const running = { ...run, status: 'running', finished_at: null, checkpoint: { ...run.checkpoint, next_stage: 'investigation' as const, outcome: null } };
  vi.mocked(workflowApi.list).mockResolvedValue([{ ...running, next_stage: 'investigation', model_calls: 0, tool_calls: 3 }]);
  vi.mocked(workflowApi.get).mockResolvedValue(running);
  const user = userEvent.setup();
  render(<WorkflowCenter />);
  await user.click(await screen.findByRole('button', { name: 'Cancel workflow' }));
  expect(workflowApi.cancel).toHaveBeenCalledWith('test-workflow');
  expect(await screen.findByRole('alert')).toHaveTextContent('Workflow cancelled. Evidence retained.');
  expect(screen.getByRole('heading', { name: 'Shared evidence' })).toBeInTheDocument();
});

it('resumes only a server-validated checkpoint through the resume endpoint', async () => {
  const interrupted = { ...run, status: 'interrupted', resumable: true, checkpoint: { ...run.checkpoint, model_calls: 3, next_stage: 'simulation' as const, outcome: null } };
  vi.mocked(workflowApi.list).mockResolvedValue([{ ...interrupted, next_stage: 'simulation', model_calls: 3, tool_calls: 3 }]);
  vi.mocked(workflowApi.get).mockResolvedValue(interrupted);
  const user = userEvent.setup();
  render(<WorkflowCenter />);
  await user.click(await screen.findByRole('button', { name: 'Resume saved checkpoint' }));
  expect(workflowApi.resume).toHaveBeenCalledWith('test-workflow');
  expect(workflowApi.start).not.toHaveBeenCalled();
  expect(screen.getByText(/Resume preserves this deadline and consumed budgets/)).toBeInTheDocument();
});

it('follows the server active ID after a lost response and preserves action errors across polling', async () => {
  vi.useFakeTimers();
  try {
    vi.mocked(investigationApi.status).mockResolvedValueOnce(provider).mockResolvedValue({ ...provider, active_workflow_id: run.id });
    vi.mocked(workflowApi.start).mockRejectedValue(new Error('Workflow start response lost.'));
    render(<WorkflowCenter />);
    await act(async () => { await Promise.resolve(); });
    await act(async () => { screen.getByRole('button', { name: 'Start workflow' }).click(); });
    expect(workflowApi.get).toHaveBeenCalledWith(run.id);
    expect(screen.getByRole('alert')).toHaveTextContent('Workflow start response lost.');
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(screen.getByRole('alert')).toHaveTextContent('Workflow start response lost.');
    expect(workflowApi.start).toHaveBeenCalledTimes(1);
  } finally { vi.useRealTimers(); }
});

it('does not let successful detail polling hide a status-connection failure', async () => {
  vi.useFakeTimers();
  try {
    vi.mocked(workflowApi.list).mockResolvedValue([{ ...run, next_stage: 'done', model_calls: 0, tool_calls: 3 }]);
    vi.mocked(investigationApi.status).mockResolvedValueOnce(provider).mockRejectedValue(new Error('Provider status endpoint unavailable.'));
    render(<WorkflowCenter />);
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    expect(screen.getByRole('alert')).toHaveTextContent('Provider status endpoint unavailable.');
    expect(workflowApi.get).toHaveBeenCalled();
  } finally { vi.useRealTimers(); }
});
