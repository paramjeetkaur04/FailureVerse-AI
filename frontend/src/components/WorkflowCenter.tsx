import { useCallback, useEffect, useState } from 'react';
import { Download, LoaderCircle, RefreshCw, ShieldCheck, Square, Workflow } from 'lucide-react';
import { investigationApi, workflowApi, type AgentStatus, type AgentWorkflow, type Finding, type WorkflowRole, type WorkflowSummary } from '../api';
import { Status, time } from './Status';

const roles: { id: WorkflowRole; title: string; method: string }[] = [
  { id: 'monitoring', title: 'Monitoring', method: 'Python rules · fixed diagnostics' },
  { id: 'investigation', title: 'Investigation', method: 'Ollama · native diagnostics' },
  { id: 'simulation', title: 'Simulation planning', method: 'Ollama · proposal selection' },
  { id: 'risk', title: 'Risk analysis', method: 'Python policy · observed signals' },
  { id: 'recovery', title: 'Recovery planning', method: 'Ollama · proposal selection' },
];
const active = (status?: string) => status === 'queued' || status === 'running';

function Citations({ ids }: { ids: string[] }) {
  return <span className="evidence-links">{ids.map(id => <a key={id} title={id} href={`#workflow-evidence-${id}`}>{id.split('.').at(-1)}</a>)}</span>;
}

function Findings({ items }: { items: Finding[] }) {
  return <ul className="workflow-findings">{items.map((item, index) => <li key={index}>{item.statement}<Citations ids={item.evidence_ids} />
    {Boolean(item.source_fields?.length) && <small className="source-fields">Source fields: {item.source_fields!.join(', ')}</small>}</li>)}</ul>;
}

export default function WorkflowCenter() {
  const [provider, setProvider] = useState<AgentStatus | null>(null);
  const [history, setHistory] = useState<WorkflowSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [run, setRun] = useState<AgentWorkflow | null>(null);
  const [question, setQuestion] = useState('Investigate current demo container health.');
  const [force, setForce] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const refresh = useCallback(async (followActive = false) => {
    try {
      const [status, saved] = await Promise.all([investigationApi.status(), workflowApi.list()]);
      setProvider(status); setHistory(saved); setError(null);
      setSelected(previous => (followActive ? status.active_workflow_id : null) ?? previous ?? status.active_workflow_id ?? saved[0]?.id ?? null);
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Workflow services are unavailable.'); }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (!selected) return;
    let mounted = true;
    const poll = async () => {
      try {
        const value = await workflowApi.get(selected);
        if (mounted) { setRun(value); setDetailError(null); }
      } catch (failure) { if (mounted) setDetailError(failure instanceof Error ? failure.message : 'Workflow could not be loaded.'); }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2000);
    return () => { mounted = false; window.clearInterval(timer); };
  }, [selected]);

  async function act(operation: 'start' | 'cancel' | 'resume') {
    setBusy(true); setActionError(null);
    try {
      const value = operation === 'start' ? await workflowApi.start(question, force)
        : operation === 'cancel' ? await workflowApi.cancel(run!.id) : await workflowApi.resume(run!.id);
      setRun(value); setSelected(value.id); await refresh();
    } catch (failure) {
      setActionError(failure instanceof Error ? failure.message : 'Workflow action failed.');
      await refresh(true);
    } finally { setBusy(false); }
  }

  function download() {
    if (!run) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(run, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = `failureverse-workflow-${run.id}.json`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const running = active(run?.status);
  const slotBusy = Boolean(provider?.active_run_id || provider?.active_workflow_id);
  const cp = run?.checkpoint;
  return <div className="investigation-center">
    {(error || detailError || actionError) && <div className="connection-error" role="alert"><div>{actionError && <p>{actionError}</p>}{error && <p>{error}</p>}{detailError && <p>{detailError}</p>}</div><button className="button secondary small" onClick={() => { setActionError(null); void refresh(true); }}>Retry workflow connection</button></div>}
    <section className="panel investigation-form">
      <div className="panel-heading"><div><h2>Coordinated agent workflow</h2><p>Monitoring → investigation → simulation planning → risk analysis → recovery planning</p></div><Workflow size={20} /></div>
      <div className="investigation-question"><label htmlFor="workflow-question">What should the workflow investigate?</label><textarea id="workflow-question" rows={3} minLength={5} maxLength={400} value={question} onChange={event => setQuestion(event.target.value)} disabled={busy || running} />
        <label className="workflow-mode"><input type="checkbox" checked={force} onChange={event => setForce(event.target.checked)} disabled={busy || running} />Investigate even when monitoring checks are healthy</label>
        <p className="workflow-help">Monitoring collects real snapshots. Healthy checks finish without AI inference unless you select the option above. Simulation and recovery steps produce proposals for review.</p>
        {provider && !provider.ready && <p className="workflow-help">AI provider: {provider.detail} Monitoring-only runs remain available when workflows are enabled.</p>}
        {slotBusy && <p className="workflow-help">Another run owns the execution slot. Existing investigations and workflows share one slot.</p>}
        <div className="investigation-actions"><span><ShieldCheck size={16} />Designated demo only · execution disabled</span><button className="button primary" onClick={() => void act('start')} disabled={busy || running || slotBusy || !provider?.enabled || (force && !provider?.ready) || question.trim().length < 5}>{busy && <LoaderCircle size={15} className="spin" />}Start workflow</button></div>
      </div>
      <div className="agent-limits"><span>7 model calls</span><span>9 diagnostic calls</span><span>300 seconds total</span><span>Investigator retains 4 calls / 6 tools / 180 seconds</span></div>
    </section>
    <div className="investigation-layout">
      <aside className="panel investigation-history"><div className="panel-heading"><h2>Saved workflows</h2><button className="help-button" aria-label="Refresh workflows" onClick={() => void refresh()}><RefreshCw size={16} /></button></div>
        {history.length ? history.map(item => <button key={item.id} className={`investigation-history-row ${item.id === selected ? 'selected' : ''}`} onClick={() => { setRun(null); setSelected(item.id); }}><span>{item.question}</span><small>{time(item.created_at, true)}</small><span>{item.status.replaceAll('_', ' ')}</span></button>) : <p className="panel-copy">No workflow records yet. Start a monitoring check to collect evidence.</p>}
      </aside>
      <div className="investigation-detail">
        {!selected ? <section className="panel empty"><Workflow size={30} /><h2>Evidence moves between specialist stages</h2><p>Monitoring applies rules, the investigator chooses diagnostics, and planners select supported proposals. Infrastructure changes remain disabled.</p></section> : !run || !cp ? <section className="panel empty" role="status">Loading saved workflow…</section> : <>
          <section className="panel"><div className="panel-heading"><div><h2>{running ? 'Workflow in progress' : 'Workflow result'}</h2><p className="mono">{run.id.slice(0, 8)} · {run.model}</p></div><div className="run-controls">
            {running && <button className="button secondary small" disabled={busy} onClick={() => void act('cancel')}><Square size={13} />Cancel workflow</button>}
            {run.resumable && <button className="button secondary small" disabled={busy || slotBusy} onClick={() => void act('resume')}>Resume saved checkpoint</button>}
            <button className="button secondary small" onClick={download}><Download size={14} />Export workflow JSON</button></div></div>
            <div className="run-budget"><div><span>Model calls</span><strong>{cp.model_calls}<small> / {run.limits.model_calls}</small></strong></div><div><span>Diagnostic calls</span><strong>{cp.tool_calls}<small> / {run.limits.tool_calls}</small></strong></div><div><span>Status</span><Status value={running ? 'actual' : ['awaiting_review', 'observed_healthy'].includes(run.status) ? 'healthy' : 'unavailable'} label={run.status.replaceAll('_', ' ')} /></div></div>
            <p className="workflow-meta">Original deadline: {time(run.expires_at, true)}. Resume preserves this deadline and consumed budgets.</p>
            {run.error && <div className="run-error" role="alert">{run.error}</div>}
            {run.status === 'insufficient_evidence' && <div className="run-error" role="alert">Insufficient evidence for a complete validated workflow. Unsupported proposals were withheld.</div>}
            <ol className="workflow-stages">{roles.map(role => {
              const completed = run.events.some(event => event.role === role.id && event.kind === 'checkpoint');
              const started = run.events.some(event => event.role === role.id && event.kind === 'stage_started');
              const label = completed ? 'completed' : running && cp.next_stage === role.id ? 'active' : started ? 'stopped' : cp.outcome === 'observed_healthy' ? 'skipped' : 'not run';
              return <li key={role.id}><div><strong>{role.title}</strong><small>{role.method}</small></div><Status value={completed ? 'healthy' : label === 'active' ? 'actual' : 'unavailable'} label={label} /></li>;
            })}</ol>
          </section>
          {cp.monitoring && <section className="panel"><div className="panel-heading"><div><h2>Monitoring observations</h2><p>Snapshot rules · memory review threshold uses raw counters</p></div><Status value={cp.monitoring.state === 'healthy' ? 'healthy' : 'unavailable'} label={cp.monitoring.state.replaceAll('_', ' ')} /></div>
            {cp.monitoring.signals.length ? <Findings items={cp.monitoring.signals} /> : cp.monitoring.state === 'healthy' ? <p className="report-summary">Configured health and memory checks detected no failure signal at collection time.<Citations ids={cp.monitoring.evidence_ids} /></p> : null}
            {cp.monitoring.missing.length > 0 && <div className="workflow-notes"><h3>Missing evidence</h3><ul>{cp.monitoring.missing.map(item => <li key={item}>{item}</li>)}</ul></div>}
          </section>}
          {cp.investigation && <section className="panel"><div className="panel-heading"><div><h2>Investigator findings</h2><p>Source-field validated · hypotheses remain unconfirmed</p></div></div><p className="report-summary">{cp.investigation.summary}<Citations ids={cp.investigation.summary_evidence_ids ?? []} /></p><Findings items={cp.investigation.observations} />
            {cp.investigation.suspected_root_causes.length > 0 && <div className="workflow-notes"><h3>Unconfirmed hypotheses</h3><Findings items={cp.investigation.suspected_root_causes} /></div>}
            {Boolean(cp.investigation.limitations?.length) && <div className="workflow-notes"><h3>Uncertainties and limitations</h3><Findings items={cp.investigation.limitations!} /></div>}
          </section>}
          {roles.filter(role => ['simulation', 'risk', 'recovery'].includes(role.id)).map(role => {
            const output = cp.specialists[role.id];
            return output ? <section className="panel workflow-proposal" key={role.id}><div className="panel-heading"><div><h2>{role.title}</h2><p>{output.method === 'deterministic_policy' ? 'Policy assessment · no predicted probabilities' : 'Proposals selected through Ollama · not executed'}</p></div><ShieldCheck size={18} /></div><Findings items={output.items} />
              {output.plan_hash && <details className="workflow-fingerprint"><summary>Plan fingerprint for review</summary><code>{output.plan_hash}</code><p>This identifies the proposed plan version. It is not an approval token.</p></details>}
              <p className="report-disclaimer">Execution is disabled. Experiments and recovery actions require a later phase and separate execution controls.</p></section> : null;
          })}
          <section className="panel"><div className="panel-heading"><div><h2>Agent execution timeline</h2><p>Persisted role transitions, choices, counters and checkpoints</p></div></div><ol className="agent-events">{run.events.map(event => <li key={event.sequence}><span className={`event-marker ${event.kind}`} /><div><span>{event.title}</span><small>{event.role}{event.tool ? ` · ${event.tool}` : ''}</small><time>{time(event.at)}</time></div></li>)}</ol></section>
          {cp.evidence.length > 0 && <section className="panel"><div className="panel-heading"><h2>Shared evidence</h2><span className="quiet-badge">{cp.evidence.length} observations</span></div>{cp.evidence.map(item => <details className="evidence-detail" id={`workflow-evidence-${item.id}`} key={item.id}><summary><span className="mono" title={item.id}>{item.id.split('.').at(-1)}</span><span>{item.tool}</span><small>{item.measurement} · {time(item.observed_at)}</small></summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}</section>}
        </>}
      </div>
    </div>
  </div>;
}
