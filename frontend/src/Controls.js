import React, { useEffect, useRef, useState } from 'react';
import htm from 'htm';
import { api, setToken } from './api.js';
const html = htm.bind(React.createElement);

export function Controls({ state, showTruth, setShowTruth, setMsg }) {
  const [atk, setAtk] = useState({ pattern: '', size: 8, depth: 3, gapMin: 2, gapMax: 10, split: 0.4 });
  const [th, setTh] = useState({ flag_at: 0.3, hold_at: 0.6, freeze_at: 0.85 });
  const [tok, setTok] = useState(() => { try { return sessionStorage.getItem('mn_tok') || ''; } catch (e) { return ''; } });
  const timer = useRef(null);
  const m = state.metrics || {};

  useEffect(() => { setToken(tok); try { sessionStorage.setItem('mn_tok', tok); } catch (e) { /* ignore */ } }, [tok]);
  useEffect(() => { if (state.thresholds) setTh(state.thresholds); }, [state.thresholds]);

  const run = async (fn) => { try { setMsg(''); await fn(); } catch (e) { setMsg(String(e.message || e)); } };

  const launch = () => run(() => api.attack({
    pattern: atk.pattern || undefined, size: +atk.size, depth: +atk.depth,
    hop_gap_min: +atk.gapMin, hop_gap_max: +atk.gapMax, split_ratio: atk.pattern === 'fan_out' ? +atk.split : undefined,
  }));

  const setThreshold = (key, v) => {
    const g = 0.01, n = { ...th, [key]: v };
    if (key === 'flag_at') n.flag_at = Math.min(v, n.hold_at - g);
    if (key === 'hold_at') n.hold_at = Math.min(Math.max(v, n.flag_at + g), n.freeze_at - g);
    if (key === 'freeze_at') n.freeze_at = Math.max(v, n.hold_at + g);
    setTh(n); clearTimeout(timer.current);
    timer.current = setTimeout(() => run(async () => { await api.thresholds(n); }), 300);
  };

  const slider = (label, key) => html`<label class="row">${label}: <b>${(+th[key]).toFixed(2)}</b>
    <input type="range" min="0.05" max="0.99" step="0.01" value=${th[key]} onChange=${(e) => setThreshold(key, +e.target.value)} /></label>`;
  const num = (label, key, min, max, step = 1) => html`<label class="row inline">${label}
    <input type="number" min=${min} max=${max} step=${step} value=${atk[key]} onChange=${(e) => setAtk({ ...atk, [key]: e.target.value })} /></label>`;

  return html`<div class="panel">
    <h3>Launch simulated attack</h3>
    <label class="row inline">Pattern
      <select value=${atk.pattern} onChange=${(e) => setAtk({ ...atk, pattern: e.target.value })}>
        <option value="">random</option><option value="fan_out">fan-out</option><option value="fan_in">fan-in</option><option value="circular">circular</option>
      </select></label>
    ${num('Mule accounts', 'size', 3, 30)} ${num('Depth', 'depth', 2, 6)}
    ${num('Hop gap min (s)', 'gapMin', 0.5, 60, 0.5)} ${num('Hop gap max (s)', 'gapMax', 1, 120, 0.5)}
    ${atk.pattern === 'fan_out' && html`<label class="row">Split ratio: <b>${(+atk.split).toFixed(2)}</b>
      <input type="range" min="0.1" max="0.9" step="0.05" value=${atk.split} onChange=${(e) => setAtk({ ...atk, split: e.target.value })} /></label>`}
    <button class="primary" onClick=${launch}>Launch ring</button>

    <h3>Response thresholds</h3>
    ${slider('Flag at', 'flag_at')} ${slider('Hold at', 'hold_at')} ${slider('Freeze at', 'freeze_at')}
    <p class="hint">Flag: step-up/delay. Hold: block outgoing, pending review. Freeze: escalate to a human fraud team.</p>

    <h3>Simulation</h3>
    <div class="btnrow">
      <button onClick=${() => run(() => api.control({ paused: !m.paused }))}>${m.paused ? 'Resume' : 'Pause'}</button>
      <select value=${m.speed || 20} onChange=${(e) => run(() => api.control({ speed: +e.target.value }))}>
        ${[5, 10, 20, 40, 80].map((s) => html`<option key=${s} value=${s}>${s}x</option>`)}</select>
      <button onClick=${() => run(() => api.reset())}>Reset</button>
    </div>
    <label class="row inline"><input type="checkbox" checked=${showTruth} onChange=${(e) => setShowTruth(e.target.checked)} />
      Show simulator ground truth (purple = actual mule)</label>
    <label class="row">Admin token (if the server requires one)
      <input type="password" value=${tok} onChange=${(e) => setTok(e.target.value)} placeholder="X-Admin-Token" /></label>
  </div>`;
}
