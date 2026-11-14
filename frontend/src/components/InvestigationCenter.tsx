import { useCallback, useEffect, useState } from 'react';
import { Activity, ArrowRight, Download, FileSearch, LoaderCircle, RefreshCw, ShieldCheck, Square, Terminal } from 'lucide-react';
import { investigationApi, type AgentStatus, type Finding, type Investigation, type RunSummary } from '../api';
import { Status, time } from './Status';

const active = (status?: string) => status === 'queued' || status === 'running';

function Findings({ title, items }: { title: string; items: Finding[] }) {
  return <section className="report-section"><h3>{title}</h3>{items.length ? <ul>{items.map((item, index) => <li key={index}>{item.statement}<span className="evidence-links">{item.evidence_ids.map(id => <a href={`#evidence-${id}`} key={id}>{id}</a>)}</span></li>)}</ul> : <p>No specific causes were established by the model.</p>}</section>;
}

export default function InvestigationCenter() {
  const [provider, setProvider] = useState<AgentStatus | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [run, setRun] = useState<Investigation | null>(null);
  const [question, setQuestion] = useState('Investigate the demo application’s current health and possible reliability issues.');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [status, history] = await Promise.all([investigationApi.status(), investigationApi.list()]);
      setProvider(status);
      setRuns(history);
      setSelected(previous => previous ?? history[0]?.id ?? null);
      setError(null);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Agent services are unavailable.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (!selected) return;
    let mounted = true;
    const poll = async () => {
      try {
        const result = await investigationApi.get(selected);
        if (mounted) { setRun(result); setError(null); }
      } catch (failure) {
        if (mounted) setError(failure instanceof Error ? failure.message : 'Investigation connection failed.');
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2000);
    return () => { mounted = false; window.clearInterval(timer); };
  }, [selected]);

  async function start() {
    setBusy(true); setError(null);
    try {
      const created = await investigationApi.start(question);
      setRun(created); setSelected(created.id);
      await refresh();
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Unable to start investigation.'); }
    finally { setBusy(false); }
  }

  async function cancel() {
    if (!run) return;
    setBusy(true);
    try { setRun(await investigationApi.cancel(run.id)); await refresh(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Unable to cancel investigation.'); }
    finally { setBusy(false); }
  }

  function download() {
    if (!run) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(run, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = `failureverse-investigation-${run.id}.json`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  if (loading) return <section className="panel loading-state" role="status"><LoaderCircle className="spin" /><h2>Checking local agent services</h2><p>Reading Ollama availability and saved investigations.</p></section>;

  const running = active(run?.status);
  const stage = [...(run?.events ?? [])].reverse().find(event => event.kind === 'state');
  return <div className="investigation-center">
    {error && <div className="connection-error" role="alert"><Activity size={18} /><p>{error}</p><button className="button secondary small" onClick={() => void refresh()}>Retry agent connection</button></div>}
    <section className="panel investigation-form">
      <div className="panel-heading"><div><h2>Local investigation agent</h2><p>Ollama · LangGraph · read-only Docker diagnostics</p></div><Status value={provider?.ready ? 'healthy' : 'unavailable'} label={provider?.ready ? 'Model ready' : provider?.state.replaceAll('_', ' ') ?? 'Disconnected'} /></div>
      {!provider?.ready && <div className="provider-notice"><p>{provider?.detail ?? 'The backend did not return provider status.'}</p><code>ollama pull {provider?.model ?? 'qwen3:0.6b'}</code></div>}
      <div className="investigation-question"><label htmlFor="investigation-question">What should the agent investigate?</label><textarea id="investigation-question" value={question} onChange={event => setQuestion(event.target.value)} minLength={5} maxLength={400} rows={3} disabled={running || busy} /><div className="investigation-actions"><span><ShieldCheck size={15} />Target: allowlisted Flask demo</span><button className="button primary" onClick={() => void start()} disabled={!provider?.ready || busy || running || Boolean(provider?.active_run_id) || question.trim().length < 5}>{busy ? <LoaderCircle className="spin" size={16} /> : <FileSearch size={16} />}Start investigation</button></div></div>
      <div className="agent-limits"><span>Maximum 4 model calls</span><span>6 diagnostic calls</span><span>180 seconds</span><span>Recommendations are never executed</span></div>
    </section>

    <div className="investigation-layout">
      <aside className="panel investigation-history"><div className="panel-heading"><h2>Investigations</h2><button className="help-button" aria-label="Refresh investigations" onClick={() => void refresh()}><RefreshCw size={16} /></button></div>
        {!runs.length ? <div className="empty"><FileSearch size={24} /><p>No investigations saved yet.</p></div> : runs.map(item => <button key={item.id} className={`investigation-history-row ${selected === item.id ? 'selected' : ''}`} onClick={() => { setRun(null); setSelected(item.id); }}><span>{item.question}</span><small>{time(item.created_at, true)}</small><Status value={item.status === 'completed' ? 'healthy' : active(item.status) ? 'actual' : 'unavailable'} label={item.status.replaceAll('_', ' ')} /></button>)}
      </aside>
      <div className="investigation-detail">
        {!selected ? <section className="panel empty investigation-empty"><FileSearch size={32} /><h2>Evidence starts with an investigation</h2><p>The model will select approved tools, examine actual container data, and produce a cited report. Nothing is prefilled.</p></section> : !run ? <section className="panel empty" role="status">Loading saved investigation…</section> : <>
          <section className="panel"><div className="panel-heading"><div><h2>{running ? 'Investigation in progress' : 'Investigation result'}</h2><p className="mono">{run.id.slice(0, 8)} · {run.model}</p></div><div className="run-controls">{running && <button className="button secondary small" disabled={busy} onClick={() => void cancel()}><Square size={13} />Cancel investigation</button>}<button className="button secondary small" onClick={download}><Download size={14} />Export JSON</button></div></div>
            <div className="run-budget"><div><span>Model calls</span><strong>{run.model_calls}<small> / {run.limits.model_calls}</small></strong></div><div><span>Diagnostic calls</span><strong>{run.tool_calls}<small> / {run.limits.tool_calls}</small></strong></div><div><span>Status</span><Status value={run.status === 'completed' ? 'healthy' : running ? 'actual' : 'unavailable'} label={run.status.replaceAll('_', ' ')} /></div></div>
            {running && <div className="current-stage" role="status"><LoaderCircle className="spin" size={16} />{stage?.title ?? 'Waiting for the agent to begin'}</div>}
            {run.error && <div className="run-error" role="alert">{run.error}</div>}
          </section>

          <section className="panel"><div className="panel-heading"><div><h2>Execution trail</h2><p>Persisted transitions, tool choices, and observed outcomes</p></div><Terminal size={18} /></div><ol className="agent-events">{run.events.map(event => <li key={event.sequence}><span className={`event-marker ${event.kind}`} /><div><span>{event.title}</span>{event.tool && <code>{event.tool}</code>}{event.selected_tools && <small>Selected: {event.selected_tools.join(', ')}</small>}<time>{time(event.at)}</time></div></li>)}</ol></section>

          {run.report && <section className="panel agent-report"><div className="panel-heading"><div><h2>Investigation report</h2><p>AI-generated findings · evidence references validated</p></div><ShieldCheck size={18} /></div><p className="report-summary">{run.report.summary}</p><Findings title="Actual observations" items={run.report.observations} /><Findings title="Suspected root causes" items={run.report.suspected_root_causes} /><section className="report-section"><h3>Uncertainties and limitations</h3><ul>{run.report.uncertainties.map((item, index) => <li key={index}>{item}</li>)}</ul></section><Findings title="Recommended actions" items={run.report.recommended_actions} /><div className="report-disclaimer">Review model conclusions against the evidence. Recommendations have not been executed.</div></section>}

          {run.evidence.length > 0 && <section className="panel"><div className="panel-heading"><div><h2>Collected evidence</h2><p>Actual Docker observations · sanitized and bounded</p></div><span className="quiet-badge">{run.evidence.length} observations</span></div>{run.evidence.map(item => <details className="evidence-detail" key={item.id} id={`evidence-${item.id}`}><summary><span className="mono">{item.id}</span><span>{item.tool}</span><small>{time(item.observed_at)}</small><ArrowRight size={14} /></summary><pre>{JSON.stringify(item.data, null, 2)}</pre></details>)}</section>}
        </>}
      </div>
    </div>
  </div>;
}
