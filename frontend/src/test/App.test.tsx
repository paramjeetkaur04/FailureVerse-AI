import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { api } from '../api';
import { config, overview } from './fixtures';
// Compile the real chart before timed tests; importing Recharts on first render can
// exceed a test's budget on busy Windows/WSL hosts even when the UI is correct.
import '../components/LatencyChart';

vi.mock('../api', () => ({ api: { overview: vi.fn(), config: vi.fn(), runCheck: vi.fn() } }));

beforeEach(() => {
  vi.mocked(api.overview).mockResolvedValue(overview);
  vi.mocked(api.config).mockResolvedValue(config);
  vi.mocked(api.runCheck).mockResolvedValue(overview.latest!);
});

describe('connected workspace', () => {
  it('shows loading until the backend resolves', () => {
    vi.mocked(api.overview).mockReturnValue(new Promise(() => {}));
    render(<App />);
    expect(screen.getByRole('status')).toHaveTextContent('Connecting to your workspace');
    expect(screen.getByRole('button', { name: 'Run health check' })).toBeDisabled();
  });

  it('renders real backend values and clearly labels future capabilities', async () => {
    render(<App />);
    expect(await screen.findByText('Backend connected')).toBeInTheDocument();
    expect(screen.getByText('1.25')).toBeInTheDocument();
    expect(screen.getByText('1 service needs attention')).toBeInTheDocument();
    expect(screen.getByText('Demo check failed.')).toBeInTheDocument();
    // Await the actual lazy import, rather than timing Vite's transform against a 1s DOM query.
    await act(async () => { await vi.dynamicImportSettled(); });
    expect(screen.queryByText('Waiting for measurements')).not.toBeInTheDocument();
    expect(await screen.findByText('One observation collected')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'AI Investigation Center' })).toBeInTheDocument();
  });

  it('runs a backend check and refreshes saved observations', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Backend connected');
    await user.click(screen.getByRole('button', { name: 'Run health check' }));
    await waitFor(() => expect(api.runCheck).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(api.overview).toHaveBeenCalledTimes(2));
  });

  it('opens service evidence and provider configuration', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Backend connected');
    await user.click(screen.getByRole('button', { name: 'Infrastructure' }));
    expect(screen.getByRole('heading', { name: 'Service health' })).toBeInTheDocument();
    expect(screen.getByText('Restricted by design')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Configuration' }));
    expect(screen.getByText('http://127.0.0.1:5001/health')).toBeInTheDocument();
    expect(screen.getByText('qwen3:8b')).toBeInTheDocument();
    expect(screen.getByText('Not enabled')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Copy startup command' }));
    await expect(navigator.clipboard.readText()).resolves.toBe('docker compose up --build --wait');
  });

  it('expands persisted observations and filters history', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Backend connected');
    await user.click(screen.getByRole('button', { name: 'Health-check history' }));
    await user.click(screen.getByRole('button', { name: /Startup service check/ }));
    expect(screen.getByText('Demo check failed.')).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Show'), 'healthy');
    expect(screen.getByText('No matching observations')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export JSON' })).toBeDisabled();
  });

  it('keeps old observations visibly marked when a check fails', async () => {
    vi.mocked(api.runCheck).mockRejectedValue(new Error('Health service unavailable.'));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Backend connected');
    await user.click(screen.getByRole('button', { name: 'Run health check' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Showing the last saved observations.');
    expect(screen.getByText('Backend connected')).toBeInTheDocument();
  });

  it('marks the connection disconnected when refreshing backend data fails', async () => {
    vi.mocked(api.overview).mockResolvedValueOnce(overview).mockRejectedValueOnce(new Error('Backend offline'));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Backend connected');
    await user.click(screen.getByRole('button', { name: 'Run health check' }));
    expect(await screen.findByText('Backend disconnected')).toBeInTheDocument();
  });
});

it('shows a disconnected state without fabricated metrics, then supports retry', async () => {
  vi.mocked(api.overview).mockRejectedValueOnce(new Error('Connection refused'));
  const user = userEvent.setup();
  render(<App />);
  expect(await screen.findByText('Workspace disconnected')).toBeInTheDocument();
  expect(screen.queryByText('Services observed')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Retry connection' }));
  expect(await screen.findByText('Backend connected')).toBeInTheDocument();
});

it('renders the empty state without inventing observations', async () => {
  vi.mocked(api.overview).mockResolvedValue({ ...overview, latest: null, history: [], healthy_services: 0, total_services: 0, saved_checks: 0 });
  render(<App />);
  expect(await screen.findByText('No health checks recorded')).toBeInTheDocument();
  expect(screen.getByText('No observations yet')).toBeInTheDocument();
  expect(await screen.findByText('Waiting for measurements')).toBeInTheDocument();
});
