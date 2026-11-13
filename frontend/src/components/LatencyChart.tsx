import { useState } from 'react';
import { Activity } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Check } from '../api';
import { time } from './Status';

export function LatencyChart({ history }: { history: Check[] }) {
  const [service, setService] = useState('database');
  const [limit, setLimit] = useState(30);
  const data = history.slice(0, limit).reverse().map(check => ({
    timestamp: time(check.checked_at),
    latency: check.services.find(item => item.id === service)?.latency_ms ?? null,
  }));
  const measured = data.filter(item => item.latency !== null);

  return <section className="panel chart-panel" aria-label="Measured health-check latency">
    <div className="panel-heading"><div><h2>Health-check latency</h2><p>Actual measurements · milliseconds</p></div>
      <select aria-label="Chart service" value={service} onChange={event => setService(event.target.value)}>
        <option value="database">SQLite query</option><option value="demo">Flask HTTP request</option>
      </select>
    </div>
    <div className="chart-toolbar"><span className="chart-legend"><i />{service === 'database' ? 'SELECT 1 response time' : 'Demo /health response time'}</span><div className="segmented" aria-label="Chart history length">{[10, 30].map(value => <button key={value} className={limit === value ? 'selected' : ''} onClick={() => setLimit(value)}>Last {value}</button>)}</div></div>
    <div className="chart-body">
      {measured.length < 2 ? <div className="empty chart-empty"><Activity size={28} /><h3>{measured.length ? 'One observation collected' : 'Waiting for measurements'}</h3><p>{measured.length ? 'Run another health check to see the response-time trend.' : 'Successful health checks will appear here. Missing data is never plotted as zero.'}</p></div> : <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <AreaChart data={data} margin={{ top: 16, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid vertical={false} stroke="#2a2e33" strokeDasharray="3 5" />
          <XAxis dataKey="timestamp" axisLine={false} tickLine={false} tick={{ fill: '#9ca4ad', fontSize: 11 }} minTickGap={48} dy={12} />
          <YAxis axisLine={false} tickLine={false} tick={{ fill: '#9ca4ad', fontSize: 11 }} width={48} tickFormatter={value => Number(value).toFixed(1)} />
          <Tooltip contentStyle={{ background: '#1a1e23', border: '1px solid #343b44', borderRadius: 8, color: '#edf0f3', fontSize: 13 }} formatter={value => [`${Number(value).toFixed(2)} ms`, 'Measured latency']} />
          <Area type="linear" dataKey="latency" stroke="#64d2e3" strokeWidth={2} fill="#64d2e3" fillOpacity={0.06} connectNulls={false} isAnimationActive={false} dot={{ r: 3, fill: '#64d2e3', strokeWidth: 0 }} activeDot={{ r: 5 }} />
        </AreaChart>
      </ResponsiveContainer>}
    </div>
    <div className="panel-footnote">{measured.length} measured samples <span>Manual checks · no estimated values</span></div>
  </section>;
}
