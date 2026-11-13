import { describe, expect, it, vi } from 'vitest';
import { api, request } from '../api';

describe('backend request contract', () => {
  it('sends a bounded manual check with no arbitrary target', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'real-check' })));
    vi.stubGlobal('fetch', fetch);
    expect(await api.runCheck()).toEqual({ id: 'real-check' });
    expect(fetch).toHaveBeenCalledWith('/api/checks', expect.objectContaining({ method: 'POST', body: '{"source":"manual"}', signal: expect.any(AbortSignal) }));
  });

  it('surfaces a structured backend failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Database is unavailable.' }), { status: 503 })));
    await expect(request('/overview')).rejects.toThrow('Database is unavailable.');
  });

  it('handles an HTML proxy error without inventing a response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>Bad gateway</html>', { status: 502 })));
    await expect(api.overview()).rejects.toThrow('HTTP 502');
  });
});
