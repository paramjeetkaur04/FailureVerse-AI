import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import InvestigationCenter from '../components/InvestigationCenter';
import { investigationApi, type AgentStatus, type Investigation } from '../api';

vi.mock('../api', () => ({ investigationApi: { status: vi.fn(), list: vi.fn(), get: vi.fn(), start: vi.fn(), cancel: vi.fn() } }));
const status: AgentStatus = { ready: true, enabled: true, state: 'ready', detail: 'Test transport', model: 'test-model', active_run_id: null, targets: [{ id: 'demo', name: 'Demo' }], limits: { model_calls: 4, tool_calls: 6, deadline_seconds: 180 } };
const run: Investigation = {
  id: 'test-run', target: 'demo', question: 'Investigate this demo', model: 'test-model', status: 'completed',
  created_at: '2026-11-14T07:00:00Z', finished_at: '2026-11-14T07:00:30Z', model_calls: 3, tool_calls: 2, limits: status.limits, error: null,
  evidence: [{ id: 'E1', tool: 'inspect_container', measurement: 'actual', observed_at: '2026-11-14T07:00:10Z', data: { running: true } }],
  events: [{ sequence: 1, at: '2026-11-14T07:00:10Z', kind: 'tool_call', title: 'Executing model-selected read-only diagnostic', tool: 'inspect_container' }],
  report: { summary: 'Test report based on collected observations.', observations: [{ statement: 'Container is running.', evidence_ids: ['E1'] }], suspected_root_causes: [], uncertainties: ['Point-in-time observation.'], recommended_actions: [{ statement: 'Review future health checks.', evidence_ids: ['E1'] }] },
};

beforeEach(() => {
  vi.mocked(investigationApi.status).mockResolvedValue(status);
  vi.mocked(investigationApi.list).mockResolvedValue([]);
  vi.mocked(investigationApi.get).mockResolvedValue(run);
  vi.mocked(investigationApi.start).mockResolvedValue(run);
  vi.mocked(investigationApi.cancel).mockResolvedValue({ ...run, status: 'cancelled', report: null, error: 'Cancelled by user.' });
});

it('shows unavailable provider honestly and disables starting', async () => {
  vi.mocked(investigationApi.status).mockResolvedValue({ ...status, ready: false, state: 'unavailable', detail: 'Ollama is unavailable.' });
  render(<InvestigationCenter />);
  expect(await screen.findByText('Ollama is unavailable.')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Start investigation' })).toBeDisabled();
  expect(screen.queryByRole('heading', { name: 'Investigation report' })).not.toBeInTheDocument();
});

it('starts a real API request and displays tools, evidence and returned report', async () => {
  const user = userEvent.setup();
  render(<InvestigationCenter />);
  await screen.findByText('Model ready');
  await user.click(screen.getByRole('button', { name: 'Start investigation' }));
  await waitFor(() => expect(investigationApi.start).toHaveBeenCalledTimes(1));
  expect(await screen.findByText('Test report based on collected observations.')).toBeInTheDocument();
  expect(screen.getByText('Container is running.')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Execution trail' })).toBeInTheDocument();
  expect(screen.getAllByText('inspect_container').length).toBeGreaterThan(0);
  expect(screen.getByText('Point-in-time observation.')).toBeInTheDocument();
});

it('cancels an active investigation through the backend', async () => {
  const running = { ...run, status: 'running', report: null, finished_at: null };
  vi.mocked(investigationApi.list).mockResolvedValue([running]);
  vi.mocked(investigationApi.get).mockResolvedValue(running);
  const user = userEvent.setup();
  render(<InvestigationCenter />);
  await screen.findByRole('button', { name: 'Cancel investigation' });
  await user.click(screen.getByRole('button', { name: 'Cancel investigation' }));
  expect(await screen.findByText('Cancelled by user.')).toBeInTheDocument();
  expect(investigationApi.cancel).toHaveBeenCalledWith('test-run');
});

it('surfaces API failure without fabricating a report', async () => {
  vi.mocked(investigationApi.start).mockRejectedValue(new Error('An investigation is already running.'));
  const user = userEvent.setup();
  render(<InvestigationCenter />);
  await screen.findByText('Model ready');
  await user.click(screen.getByRole('button', { name: 'Start investigation' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('An investigation is already running.');
  expect(screen.queryByRole('heading', { name: 'Investigation report' })).not.toBeInTheDocument();
});

it('shows insufficient evidence and source-field citations without a success claim', async () => {
  vi.mocked(investigationApi.list).mockResolvedValue([{ ...run, status: 'insufficient_evidence' }]);
  vi.mocked(investigationApi.get).mockResolvedValue({ ...run, status: 'insufficient_evidence', report: { ...run.report!,
    grounding_version: '2.1', outcome: 'insufficient_evidence', model_selection_accepted: false,
    summary_evidence_ids: ['E1'], validation_notes: ['Model selection failed validation.'],
    observations: [{ statement: 'Container is running.', evidence_ids: ['E1'], source_fields: ['data.running'] }],
  } });
  render(<InvestigationCenter />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Insufficient evidence');
  expect(screen.getByText('Source fields: data.running')).toBeInTheDocument();
  expect(screen.getByText('Model selection failed validation.')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Hypotheses · unconfirmed' })).toBeInTheDocument();
  expect(screen.getAllByRole('link', { name: 'E1' })[0]).toHaveAttribute('href', '#evidence-E1');
});

it('warns that historical reports did not have factual validation', async () => {
  vi.mocked(investigationApi.list).mockResolvedValue([run]);
  render(<InvestigationCenter />);
  expect(await screen.findByRole('alert')).toHaveTextContent('predates source-field validation');
});

it('polls running progress and then renders the persisted completed report', async () => {
  vi.useFakeTimers();
  try {
    const running = { ...run, status: 'running', report: null, finished_at: null,
      events: [{ sequence: 1, at: run.created_at, kind: 'state', title: 'Model selecting diagnostic tools' }] };
    vi.mocked(investigationApi.list).mockResolvedValue([running]);
    vi.mocked(investigationApi.get).mockResolvedValueOnce(running).mockResolvedValue(run);
    render(<InvestigationCenter />);
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByRole('heading', { name: 'Investigation in progress' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Investigation report' })).not.toBeInTheDocument();
    expect(screen.getAllByText('Model selecting diagnostic tools').length).toBeGreaterThan(0);
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(screen.getByText('Test report based on collected observations.')).toBeInTheDocument();
    expect(investigationApi.get).toHaveBeenCalledTimes(2);
  } finally { vi.useRealTimers(); }
});

it('recovers the actual active run after a lost creation response and retains the error across polling', async () => {
  vi.useFakeTimers();
  try {
    const running = { ...run, id: 'accepted-run', status: 'running', report: null, finished_at: null };
    vi.mocked(investigationApi.status).mockResolvedValueOnce(status).mockResolvedValue({ ...status, active_run_id: running.id });
    vi.mocked(investigationApi.get).mockResolvedValue(running);
    vi.mocked(investigationApi.start).mockRejectedValue(new Error('Creation response was lost.'));
    render(<InvestigationCenter />);
    await act(async () => { await Promise.resolve(); });
    await act(async () => { screen.getByRole('button', { name: 'Start investigation' }).click(); });
    expect(investigationApi.get).toHaveBeenCalledWith('accepted-run');
    expect(screen.getByRole('heading', { name: 'Investigation in progress' })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Creation response was lost.');
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(screen.getByRole('alert')).toHaveTextContent('Creation response was lost.');
    expect(investigationApi.start).toHaveBeenCalledTimes(1);
  } finally { vi.useRealTimers(); }
});

it('keeps a cancellation error visible until an explicit retry', async () => {
  vi.useFakeTimers();
  try {
    const running = { ...run, status: 'running', report: null, finished_at: null };
    vi.mocked(investigationApi.list).mockResolvedValue([running]);
    vi.mocked(investigationApi.get).mockResolvedValue(running);
    vi.mocked(investigationApi.cancel).mockRejectedValue(new Error('Cancellation request failed.'));
    render(<InvestigationCenter />);
    await act(async () => { await Promise.resolve(); });
    await act(async () => { screen.getByRole('button', { name: 'Cancel investigation' }).click(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(screen.getByRole('alert')).toHaveTextContent('Cancellation request failed.');
    await act(async () => { screen.getByRole('button', { name: 'Retry agent connection' }).click(); });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  } finally { vi.useRealTimers(); }
});
