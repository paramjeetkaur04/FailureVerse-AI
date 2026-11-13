import { Box, Database, Server } from 'lucide-react';
import type { Service } from '../api';
import { latency, Status } from './Status';

const icons = { api: Server, database: Database, application: Box };

export function ServiceTable({ services }: { services: Service[] }) {
  if (!services.length) return <div className="empty"><Server /><h3>No observations yet</h3><p>Run a health check to collect the first service observations.</p></div>;
  return <div className="table-scroll"><table className="service-table">
    <thead><tr><th>Service</th><th>Observed status</th><th>Latency</th><th>Evidence</th></tr></thead>
    <tbody>{services.map(service => {
      const Icon = icons[service.kind];
      return <tr key={service.id}>
        <td><div className="service-name"><span className="service-icon"><Icon size={18} /></span><div>{service.name}<small>{service.kind}</small></div></div></td>
        <td><Status value={service.status} /></td>
        <td className="mono whitespace-nowrap">{latency(service.latency_ms)}</td>
        <td className="evidence-cell">{service.detail}</td>
      </tr>;
    })}</tbody>
  </table></div>;
}
