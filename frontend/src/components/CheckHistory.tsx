import { useState } from 'react';
import { ChevronDown, Download, FileClock } from 'lucide-react';
import type { Check } from '../api';
import { ServiceTable } from './ServiceTable';
import { Status, time } from './Status';

export function CheckHistory({ history, compact = false }: { history: Check[]; compact?: boolean }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const visible = history.filter(check => filter === 'all' ||
    (filter === 'healthy') === check.services.every(service => service.status === 'healthy'));

  function exportChecks() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(visible, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'failureverse-health-checks.json';
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <section className="panel">
    <div className="panel-heading"><div><h2>{compact ? 'Recent observations' : 'Health-check history'}</h2><p>Persisted in SQLite · newest first</p></div>{!compact && <button className="button secondary small" disabled={!visible.length} onClick={exportChecks}><Download size={15} />Export JSON</button>}</div>
    {!compact && <div className="history-filter"><label htmlFor="history-filter">Show</label><select id="history-filter" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All observations</option><option value="healthy">All services healthy</option><option value="attention">Needs attention</option></select><span>{visible.length} records loaded</span></div>}
    {!visible.length ? <div className="empty"><FileClock size={28} /><h3>No matching observations</h3><p>Run a health check or choose another filter.</p></div> : <div className="check-list">{visible.slice(0, compact ? 4 : 30).map(check => {
      const healthy = check.services.filter(service => service.status === 'healthy').length;
      const allHealthy = healthy === check.services.length;
      return <div className="check-item" key={check.id}>
        <button className="check-row" aria-expanded={expanded === check.id} onClick={() => setExpanded(expanded === check.id ? null : check.id)}>
          <span className={`timeline-marker ${allHealthy ? 'good' : 'attention'}`} />
          <span className="check-title">{check.source === 'startup' ? 'Startup service check' : 'Manual service check'}<small>{healthy}/{check.services.length} services healthy · <span className="mono">{check.id.slice(0, 8)}</span></small></span>
          <span className="check-time mono">{time(check.checked_at, true)}</span>
          <Status value={allHealthy ? 'healthy' : 'degraded'} label={allHealthy ? 'Passed' : 'Attention'} />
          <ChevronDown size={15} className={expanded === check.id ? 'rotate' : ''} />
        </button>
        {expanded === check.id && <div className="check-details"><ServiceTable services={check.services} /></div>}
      </div>;
    })}</div>}
  </section>;
}
