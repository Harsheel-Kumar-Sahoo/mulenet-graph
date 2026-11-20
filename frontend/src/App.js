import React, { useEffect, useRef, useState } from 'react';
import htm from 'htm';
import { initial, applyBatch } from './model.js';
import { connectWS } from './api.js';
import { GraphView } from './GraphView.js';
import { Controls } from './Controls.js';
import { MetricsPanel, AttackTable, EventLog, NodeDetail } from './Panels.js';
const html = htm.bind(React.createElement);

export function App() {
  const [state, setState] = useState(initial);
  const [showTruth, setShowTruth] = useState(true);
  const [sel, setSel] = useState(null);
  const [msg, setMsg] = useState('');
  const buf = useRef([]);

  useEffect(() => {
    const stop = connectWS((m) => buf.current.push(m), (c) => buf.current.push({ type: 'conn', data: c }));
    const t = setInterval(() => {           // batch events: one render per 250 ms instead of one per transaction
      if (buf.current.length) setState((s) => applyBatch(s, buf.current.splice(0)));
    }, 250);
    return () => { stop(); clearInterval(t); };
  }, []);

  return html`<div class="app">
    <header><h1>MuleNet-Graph</h1><span class="sub">real-time mule-ring detector \u00B7 prototype</span>
      <span class=${'conn ' + (state.connected ? 'on' : 'off')}>${state.connected ? 'live' : 'disconnected \u2013 retrying'}</span></header>
    ${msg && html`<div class="err" onClick=${() => setMsg('')}>${msg} (click to dismiss)</div>`}
    <main>
      <aside class="left"><${Controls} state=${state} showTruth=${showTruth} setShowTruth=${setShowTruth} setMsg=${setMsg} /></aside>
      <section class="center"><${GraphView} state=${state} showTruth=${showTruth} onSelect=${setSel} /></section>
      <aside class="right">
        <${NodeDetail} state=${state} id=${sel} setMsg=${setMsg} /><${MetricsPanel} state=${state} />
        <${AttackTable} state=${state} /><${EventLog} state=${state} />
      </aside>
    </main>
    <footer>SIMULATED DATA \u2014 every transaction shown is synthetic; no real UPI, bank or customer data. Research prototype: not production-ready,
      no claim of real-world accuracy. Scorer: ${state.scorer || '\u2026'}.</footer>
  </div>`;
}
