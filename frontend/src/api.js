// Backend base URL. Empty = same origin (dev proxy or Docker). On Vercel set VITE_BACKEND_URL=https://your-backend.example.com
const BASE = ((import.meta.env && import.meta.env.VITE_BACKEND_URL) || '').replace(/\/+$/, '');
let token = '';
export const setToken = (t) => { token = t || ''; };

async function req(method, path, body) {
  const r = await fetch(BASE + '/api' + path, {
    method, headers: { 'Content-Type': 'application/json', ...(token ? { 'X-Admin-Token': token } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail ? (typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)) : r.statusText);
  return j;
}

export const api = {
  attack: (b) => req('POST', '/attack', b),
  thresholds: (b) => req('POST', '/thresholds', b),
  control: (b) => req('POST', '/control', b),
  reset: () => req('POST', '/reset'),
  explain: (n) => req('GET', '/explain/' + encodeURIComponent(n)),
  release: (n) => req('POST', '/release/' + encodeURIComponent(n)),
};

// WebSocket with auto-reconnect. Calls onMsg(parsedMessage) and onConn(bool).
export function connectWS(onMsg, onConn) {
  let ws, stop = false, delay = 1000;
  const open = () => {
    const url = BASE ? BASE.replace(/^http/, 'ws') + '/ws' : (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
    ws = new WebSocket(url);
    ws.onopen = () => { delay = 1000; onConn(true); };
    ws.onmessage = (ev) => { try { onMsg(JSON.parse(ev.data)); } catch (e) { /* ignore malformed */ } };
    ws.onclose = () => { onConn(false); if (!stop) { setTimeout(open, delay); delay = Math.min(delay * 1.7, 5000); } };
    ws.onerror = () => ws.close();
  };
  open();
  return () => { stop = true; ws && ws.close(); };
}
