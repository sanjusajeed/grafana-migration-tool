import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export const api = axios.create({ baseURL, timeout: 120000 });

export async function verify(cfg) {
  const { data } = await api.post('/verify', cfg);
  return data;
}

export async function fetchDashboards(source) {
  const { data } = await api.post('/fetch/dashboards', { source });
  return data;
}

export async function fetchDatasources(source) {
  const { data } = await api.post('/fetch/datasources', { source });
  return data;
}

export async function fetchAlerts(source) {
  const { data } = await api.post('/fetch/alerts', { source });
  return data;
}

export async function fetchUsers(source) {
  const { data } = await api.post('/fetch/users', { source });
  return data;
}

export async function fetchContactPoints(source) {
  const { data } = await api.post('/fetch/contact-points', { source });
  return data;
}

export async function migrate(payload) {
  const { data } = await api.post('/migrate', payload);
  return data;
}

/**
 * Stream migration progress via NDJSON.
 * Calls onEvent for each parsed event: {type:'plan'|'item'|'done'|'error', ...}.
 * Resolves when the stream ends.
 */
export async function migrateStream(payload, onEvent, signal) {
  const resp = await fetch(`${baseURL}/migrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch (_) { /* ignore */ }
    throw new Error(detail);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 1);
      if (!line) continue;
      try {
        onEvent(JSON.parse(line));
      } catch (e) {
        console.warn('malformed ndjson line', line);
      }
    }
  }
  const tail = buffer.trim();
  if (tail) {
    try { onEvent(JSON.parse(tail)); } catch (_) { /* ignore */ }
  }
}
