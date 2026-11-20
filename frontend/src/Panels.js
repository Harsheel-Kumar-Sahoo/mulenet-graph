import React from 'react';
import htm from 'htm';
import { api } from './api.js';
const html = htm.bind(React.createElement);
const inr = (n) => '\u20B9' + Math.round(n || 0).toLocaleString('en-IN');
const f = (v) => (v == null ? '\u2013' : v);

export function MetricsPanel({ state }) {
  const m = state.metrics;
  if (!m) return html`<div class="panel"><h3>Metrics</h3><p class="hint">Waiting for data\u2026</p></div>`;
  const fallback = /fallback/i.test(m.scorer);
  const s = m.node_states || {}, fa = m.false_alarm_nodes || {}, l = m.scoring_ms || {};
  return html`<div class="panel">
    <h3>Live metrics <small>(simulated)</small></h3>
    <p class=${fallback ? 'warn' : 'ok'}>Scorer: <b>${m.scorer}</b>${fallback ? ' \u2014 heuristic stand-in, not a trained GNN' : ''}</p>
    <table class="kv">
      <tr><td>Sim time</td><td>${m.sim_time}s \u00B7 ${m.speed}x ${m.paused ? '(paused)' : ''}</td></tr>
      <tr><td>Transactions</td><td>${m.txns}</td></tr>
      <tr><td>Nodes normal/flag/hold/freeze</td><td>${f(s.normal)} / ${f(s.flagged)} / ${f(s.held)} / ${f(s.frozen)}</td></tr>
      <tr><td>Ring transfers blocked</td><td>${m.blocked_ring} (${inr(m.blocked_ring_amount)})</td></tr>
      <tr class="bad"><td>Legit transfers blocked</td><td>${m.blocked_legit} (${inr(m.blocked_legit_amount)})</td></tr>
      <tr class="bad"><td>Legit scenarios harmed</td><td>${m.legit_groups_harmed}</td></tr>
      <tr class="bad"><td>Legit accounts flag/hold/freeze</td><td>${f(fa.flagged)} / ${f(fa.held)} / ${f(fa.frozen)}</td></tr>
      <tr><td>Cash-outs reached</td><td>${m.cashouts_reached}</td></tr>
      <tr><td>Scoring ms p50/p95/p99</td><td>${f(l.p50)} / ${f(l.p95)} / ${f(l.p99)}</td></tr>
    </table>
    <p class="hint">Latency = per-event sub-graph extraction + scoring in this simulator (one process, simulated load). Not a production figure.</p>
  </div>`;
}

export function AttackTable({ state }) {
  const a = (state.metrics && state.metrics.attacks) || [];
  if (!a.length) return null;
  return html`<div class="panel"><h3>Injected rings</h3>
    <table class="grid"><thead><tr><th>ring</th><th>flag s</th><th>hold s</th><th>stopped?</th><th>cash-out</th></tr></thead>
    <tbody>${a.slice(-8).reverse().map((r) => html`<tr key=${r.ring_id}>
      <td>${r.pattern}</td><td>${f(r.secs_to_flag)}</td><td>${f(r.secs_to_hold)}</td>
      <td>${r.interrupted ? 'yes' : 'no'}</td><td>${r.cashout_reached ? 'reached' : 'not reached'}</td></tr>`)}</tbody></table>
    <p class="hint">Seconds measured from ring start (simulated clock).</p></div>`;
}

export function EventLog({ state }) {
  return html`<div class="panel"><h3>Event log</h3>
    <ul class="log">${state.log.slice(0, 60).map((e) => html`<li key=${e.k} class=${e.kind}>
      <span class="t">${Math.round(e.ts)}s</span> ${e.text}</li>`)}</ul></div>`;
}

function Explain({ id, score, state }) {
  const [ex, setEx] = React.useState(null), [err, setErr] = React.useState('');
  React.useEffect(() => {                      // refetch when the node is selected or its state/score changes
    let dead = false; setErr('');
    api.explain(id).then((x) => { if (!dead) setEx(x); }).catch((e) => { if (!dead) setErr(String(e.message || e)); });
    return () => { dead = true; };
  }, [id, state, score]);
  if (err) return html`<p class="warn">Explanation unavailable: ${err}</p>`;
  if (!ex || ex.node !== id) return html`<p class="hint">Loading explanation\u2026</p>`;
  if (!ex.in_window) return html`<p class="hint">${ex.note}</p>`;
  const maxd = Math.max(0.001, ...ex.edges.map((e) => Math.abs(e.delta)));
  return html`<div class="explain">
    <h4>Why this score?</h4>
    ${ex.reasons.length ? html`<ul>${ex.reasons.map((r) => html`<li key=${r.name}><b>${r.name}</b>: ${r.text}</li>`)}</ul>` : html`<p class="hint">No named rule fired for this node right now.</p>`}
    <h4>Top contributing edges <small>(score drop if removed)</small></h4>
    <table class="grid"><tbody>${ex.edges.map((e) => html`<tr key=${e.src + e.dst}>
      <td>${e.src} \u2192 ${e.dst}</td><td>${e.count}\u00D7 ${inr(e.amount)}</td>
      <td><span class="bar" style=${'width:' + Math.round(40 * Math.max(0, e.delta) / maxd) + 'px'}></span> ${e.delta}</td></tr>`)}</tbody></table>
    <h4>Window features</h4>
    <table class="kv"><tbody>${ex.features.map((x) => html`<tr key=${x.name} title=${x.note}><td>${x.name}</td><td>${x.value}</td></tr>`)}</tbody></table>
    <p class="hint">${ex.method}. ${ex.caveat}</p></div>`;
}

export function NodeDetail({ state, id, setMsg }) {
  const n = id && state.nodes.get(id);
  if (!n) return null;
  const release = async () => { try { setMsg(''); await api.release(id); } catch (e) { setMsg(String(e.message || e)); } };
  return html`<div class="panel"><h3>Account ${n.id}</h3>
    <p>Type: ${n.type} \u00B7 state: <b>${n.state}</b> \u00B7 score: ${n.score}</p>
    <p class="hint">Risk node for human review, not an accusation.</p>
    ${n.state !== 'normal' && html`<button onClick=${release}>Release (reviewer clears node)</button>`}
    <${Explain} id=${id} score=${n.score} state=${n.state} /></div>`;
}
