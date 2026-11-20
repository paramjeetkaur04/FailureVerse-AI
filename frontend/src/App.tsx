import { lazy, Suspense, useState } from 'react';
import { Activity, ArrowRight, Box, Cable, Check, ChevronRight, CircleHelp, Clipboard, Cpu, FileClock, FlaskConical, GitBranch, LayoutDashboard, LoaderCircle, LockKeyhole, Menu, Network, RefreshCw, SearchCheck, Settings2, ShieldCheck, Workflow } from 'lucide-react';
import { useWorkspace } from './useWorkspace';
import { Status, latency, time } from './components/Status';
import { ServiceTable } from './components/ServiceTable';
import { CheckHistory } from './components/CheckHistory';
import type { Config } from './api';

const LatencyChart = lazy(() => import('./components/LatencyChart').then(module => ({ default: module.LatencyChart })));

const InvestigationCenter = lazy(() => import('./components/InvestigationCenter'));
const WorkflowCenter = lazy(() => import('./components/WorkflowCenter'));

type Page = 'overview' | 'infrastructure' | 'history' | 'investigations' | 'workflows' | 'settings';
const pages = [
  { id: 'overview' as Page, title: 'Overview', icon: LayoutDashboard },
  { id: 'infrastructure' as Page, title: 'Infrastructure', icon: Network },
  { id: 'history' as Page, title: 'Health-check history', icon: FileClock },
  { id: 'investigations' as Page, title: 'AI Investigation Center', icon: SearchCheck },
  { id: 'workflows' as Page, title: 'Agent workflows', icon: Workflow },
  { id: 'settings' as Page, title: 'Configuration', icon: Settings2 },
];
const planned = [
  { title: 'Failure simulation lab', icon: FlaskConical, phase: 4 },
  { title: 'Recovery strategies', icon: ShieldCheck, phase: 4 },
];

function Configuration({ config }: { config: Config }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const command = 'docker compose up --build --wait';
  async function copy() {
    try { await navigator.clipboard.writeText(command); setCopied(true); setCopyError(false); }
    catch { setCopyError(true); }
  }
  return <div className="config-grid"><section className="panel"><div className="panel-heading"><div><h2>Runtime configuration</h2><p>Read from backend environment variables</p></div><Settings2 size={18} /></div>
    <dl className="config-list">{[
      ['Environment', config.environment], ['Database', config.database],
      ['Demo health target', config.demo_health_url], ['Request timeout', `${config.check_timeout_seconds} seconds`],
      ['Observation retention', `${config.history_limit} checks`], ['Docker mutations', 'Disabled; diagnostics are read-only'],
    ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    <div className="config-note"><LockKeyhole size={16} /><p>Edit the root <code>.env</code> file and restart the backend to apply changes. API keys are never returned by this endpoint.</p></div>
  </section><div className="stack"><section className="panel"><div className="panel-heading"><div><h2>AI provider</h2><p>Local inference configuration</p></div><span className="quiet-badge">{config.ai_enabled ? 'Enabled' : 'Not enabled'}</span></div><dl className="config-list"><div><dt>Provider</dt><dd>{config.ai_provider} · local</dd></div><div><dt>Model</dt><dd>{config.ollama_model}</dd></div></dl><p className="panel-copy">Open the AI Investigation Center to check actual model availability and run a bounded read-only investigation.</p></section>
    <section className="panel"><div className="panel-heading"><div><h2>Start the local stack</h2><p>From the repository root</p></div><Box size={18} /></div><div className="command"><code>{command}</code><button aria-label="Copy startup command" onClick={copy}>{copied ? <Check size={16} /> : <Clipboard size={16} />}</button></div>{copyError && <p className="panel-copy" role="alert">Clipboard access is unavailable. Select and copy the command above.</p>}<p className="panel-copy">Open <code>http://localhost:8080</code> after all containers are healthy. This is a local demonstration environment.</p></section></div></div>;
}

export default function App() {
  const [page, setPage] = useState<Page>('overview');
  const [menuOpen, setMenuOpen] = useState(false);
  const workspace = useWorkspace();
  const { overview, config, loading, busy, connected, error } = workspace;
  const services = overview?.latest?.services ?? [];
  const database = services.find(service => service.id === 'database');
  const pageTitle = pages.find(item => item.id === page)!.title;
  function navigate(next: Page) { setPage(next); setMenuOpen(false); }

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    {menuOpen && <button className="sidebar-backdrop" onClick={() => setMenuOpen(false)} aria-label="Close navigation" />}
    <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
      <a className="brand" href="#overview" onClick={() => navigate('overview')}><span className="brand-mark"><Activity size={24} strokeWidth={1.8} /></span><span>FailureVerse <span className="brand-ai">AI</span><small>Reliability workspace</small></span></a>
      <div className="workspace-selector"><span className="workspace-icon"><Box size={18} /></span><div>Local workspace<small>Development environment</small></div><span className="mono">01</span></div>
      <nav aria-label="Main navigation"><p className="nav-label">Workspace</p>{pages.slice(0, 3).map(item => <button key={item.id} onClick={() => navigate(item.id)} aria-current={page === item.id ? 'page' : undefined} className={`nav-item ${page === item.id ? 'active' : ''}`}><item.icon size={18} />{item.title}{page === item.id && <span className="nav-indicator" />}</button>)}
        <p className="nav-label">Intelligence</p><button className={`nav-item ${page === 'investigations' ? 'active' : ''}`} onClick={() => navigate('investigations')} aria-current={page === 'investigations' ? 'page' : undefined}><SearchCheck size={18} />AI Investigation Center</button><button className={`nav-item ${page === 'workflows' ? 'active' : ''}`} onClick={() => navigate('workflows')} aria-current={page === 'workflows' ? 'page' : undefined}><Workflow size={18} />Agent workflows</button>{planned.map(item => <div className="nav-planned" key={item.title} title={`Available after Phase ${item.phase} is implemented and tested`}><item.icon size={18} /><span>{item.title}</span><LockKeyhole size={12} /></div>)}
        <p className="nav-label">System</p><button className={`nav-item ${page === 'settings' ? 'active' : ''}`} onClick={() => navigate('settings')} aria-current={page === 'settings' ? 'page' : undefined}><Settings2 size={18} />Configuration</button>
      </nav>
      <div className="sidebar-bottom"><div className="phase-card"><GitBranch size={17} /><div>Agent coordination<small>Phase 3 of 6</small></div><span className="mono">v0.3</span></div><div className="local-boundary"><ShieldCheck size={15} />Local test environment</div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumb"><button className="mobile-menu" aria-label="Open navigation" onClick={() => setMenuOpen(true)}><Menu size={20} /></button><span className="breadcrumb-root">Workspace</span><ChevronRight size={14} /><span>{pageTitle}</span></div><div className="topbar-right"><span className="environment-label"><i />Local development</span><span className="topbar-divider" /><span className="phase-label">Phase 3</span><button className="help-button" aria-label="View configuration and startup help" onClick={() => navigate('settings')}><CircleHelp size={18} /></button></div></header>
      <main id="main-content" tabIndex={-1}>
        <div className="page-heading"><div><p className="eyebrow">Infrastructure reliability</p><h1>{page === 'overview' ? 'Infrastructure overview' : page === 'infrastructure' ? 'Service health' : page === 'history' ? 'Observation history' : page === 'investigations' ? 'AI Investigation Center' : page === 'workflows' ? 'Agent workflows' : 'Workspace configuration'}</h1><p>{page === 'overview' ? 'A clear view of your local services. Every observation backed by a real check.' : page === 'infrastructure' ? 'Read-only checks against explicitly configured local services.' : page === 'history' ? 'Inspect saved health checks and the evidence behind each result.' : page === 'investigations' ? 'Model-selected diagnostics, actual observations, and evidence-backed reports.' : page === 'workflows' ? 'Shared evidence, bounded specialist handoffs, and proposals for review.' : 'Local runtime settings, safety boundaries, and provider readiness.'}</p></div><button className="button primary" onClick={() => void workspace.runCheck()} disabled={busy || loading}><RefreshCw size={16} className={busy ? 'spin' : ''} />{busy ? 'Checking services…' : 'Run health check'}</button></div>
        {error && <div className="connection-error" role="alert"><Cable size={20} /><div><strong>{connected ? 'Health check needs attention' : 'Backend connection needs attention'}</strong><p>{error} {overview ? 'Showing the last saved observations.' : 'Start the backend on port 8000 and retry.'}</p></div><button className="button secondary small" onClick={() => void workspace.refresh()}>Retry connection</button></div>}
        {loading ? <div className="loading-state" role="status"><LoaderCircle className="spin" size={28} /><h2>Connecting to your workspace</h2><p>Loading real service observations from the backend.</p></div> : !overview || !config ? <section className="panel empty disconnected"><Cable size={32} /><h2>Workspace disconnected</h2><p>No monitoring values are available until the backend responds.</p><code>uvicorn app.main:app --host 127.0.0.1 --port 8000</code></section> : <>
          <div className="observation-strip"><Status value={connected ? 'healthy' : 'unavailable'} label={connected ? 'Backend connected' : 'Backend disconnected'} /><span className="strip-divider" /><span>{overview.latest ? `Last check ${time(overview.latest.checked_at, true)}` : 'No health checks recorded'}</span><span className="strip-note">Read-only service checks</span></div>
          {page === 'overview' && <>
            <div className="stats-grid"><div className="stat"><span>Services observed</span><strong>{overview.total_services}</strong><small>API, database, demo application</small></div><div className="stat"><span>Healthy services</span><strong>{overview.healthy_services}<em> / {overview.total_services}</em></strong><small>{!overview.total_services ? 'Awaiting the first health check' : overview.total_services - overview.healthy_services ? `${overview.total_services - overview.healthy_services} service needs attention` : 'All observed services responding'}</small></div><div className="stat"><span>Database response</span><strong className="latency-stat">{database?.latency_ms?.toFixed(2) ?? '—'}<em> ms</em></strong><small>Actual SQLite query latency</small></div><div className="stat"><span>Saved health checks</span><strong>{overview.saved_checks}</strong><small>Latest {config.history_limit} retained locally</small></div></div>
            <div className="overview-grid"><Suspense fallback={<section className="panel chart-loading" role="status">Loading measured latency chart…</section>}><LatencyChart history={overview.history} /></Suspense><section className="panel readiness-panel"><div className="panel-heading"><div><h2>Service readiness</h2><p>Latest observed state</p></div><span className="quiet-badge">{services.length} services</span></div><div className="readiness-list">{services.map(service => <div key={service.id}><span>{service.name}<small>{service.kind === 'database' ? 'Persistent storage' : service.kind === 'api' ? 'FastAPI backend' : 'Isolated test target'}</small></span><Status value={service.status} /></div>)}</div><div className="readiness-note"><ShieldCheck size={19} /><div>Observe first. Act with approval.<p>Investigations are read-only. Infrastructure changes are not enabled.</p></div></div><button className="panel-link" onClick={() => navigate('infrastructure')}>Inspect service evidence<ArrowRight size={16} /></button></section></div>
            <section className="panel services-panel"><div className="panel-heading"><div><h2>Infrastructure services</h2><p>Health checks · resource snapshots are available through AI investigations</p></div><button className="text-button" onClick={() => navigate('infrastructure')}>View services<ArrowRight size={15} /></button></div><ServiceTable services={services} /></section>
            <div className="bottom-grid"><CheckHistory history={overview.history} compact /><section className="panel next-phase"><span className="phase-number mono">03 / Agent coordination</span><h2>From observation to a reviewed proposal</h2><p>Coordinate monitoring, investigation, simulation planning, risk analysis and recovery planning with shared evidence and bounded execution.</p><div className="future-line"><LockKeyhole size={15} />Proposals never execute infrastructure changes</div><button className="text-button" onClick={() => navigate('workflows')}>Open agent workflows<ArrowRight size={15} /></button></section></div>
          </>}
          {page === 'infrastructure' && <><section className="panel"><div className="panel-heading"><div><h2>Designated services</h2><p>Last observation {overview.latest ? time(overview.latest.checked_at, true) : 'not available'}</p></div><Status value="actual" label="Actual measurements" /></div><ServiceTable services={services} /></section><div className="infrastructure-notes"><section className="panel"><ShieldCheck size={24} /><h2>Restricted by design</h2><p>The web backend has no Docker socket. A separate diagnostic broker validates the exact test container and labels on every read-only tool call.</p></section><section className="panel"><Activity size={24} /><h2>What this phase measures</h2><p>API readiness, a real SQLite query, and the demo application's HTTP response. Agent investigations can also collect actual container resource counters; prediction and simulation remain planned.</p></section></div></>}
          {page === 'history' && <><div className="history-notice"><FileClock size={17} /><span>Showing the latest {overview.history.length} of {overview.saved_checks} retained health checks. These are observations; incident history begins with the incident workflow.</span></div><CheckHistory history={overview.history} /></>}
          {page === 'investigations' && <Suspense fallback={<div className="panel loading-state" role="status">Loading investigation center…</div>}><InvestigationCenter /></Suspense>}
          {page === 'workflows' && <Suspense fallback={<div className="panel loading-state" role="status">Loading agent workflows…</div>}><WorkflowCenter /></Suspense>}
          {page === 'settings' && <Configuration config={config} />}
          <footer className="content-footer"><span>FailureVerse AI <span className="footer-separator">/</span> Coordination v0.3.0</span><span><ShieldCheck size={13} />Test infrastructure only</span></footer>
        </>}
      </main>
    </div>
  </div>;
}
