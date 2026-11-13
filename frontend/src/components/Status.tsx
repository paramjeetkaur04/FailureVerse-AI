export function Status({ value, label }: { value: string; label?: string }) {
  return <span className={`status status-${value}`}><i aria-hidden="true" />{label ?? value}</span>;
}

export function time(value: string, includeDate = false): string {
  return new Date(value).toLocaleString(undefined, includeDate
    ? { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }
    : { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function latency(value: number | null | undefined): string {
  return value == null ? '—' : `${value.toFixed(2)} ms`;
}
