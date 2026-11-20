import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import htm from 'htm';
const html = htm.bind(React.createElement);

const STYLE = [
  { selector: 'node', style: { 'background-color': '#64748b', width: 10, height: 10, 'border-width': 1, 'border-color': '#334155',
      label: 'data(label)', 'font-size': 9, color: '#e5e7eb', 'text-valign': 'top', 'text-margin-y': -3,
      'text-background-color': '#0f172a', 'text-background-opacity': 0.75, 'text-background-padding': 1 } },
  { selector: 'node[type = "merchant"], node[type = "shop"], node[type = "utility"]', style: { shape: 'round-rectangle', 'background-color': '#475569' } },
  { selector: 'node[type = "employer"], node[type = "landlord"]', style: { shape: 'hexagon', 'background-color': '#475569' } },
  { selector: 'node[type = "cashout"]', style: { shape: 'diamond', width: 16, height: 16 } },
  { selector: 'node[state = "flagged"]', style: { 'background-color': '#f59e0b', width: 14, height: 14 } },
  { selector: 'node[state = "held"]', style: { 'background-color': '#f97316', width: 18, height: 18, 'border-color': '#7c2d12', 'border-width': 2 } },
  { selector: 'node[state = "frozen"]', style: { 'background-color': '#dc2626', width: 22, height: 22, 'border-color': '#450a0a', 'border-width': 3 } },
  { selector: 'node.truth', style: { 'border-style': 'dashed', 'border-width': 3, 'border-color': '#a855f7' } },
  { selector: 'node:selected', style: { 'overlay-color': '#38bdf8', 'overlay-opacity': 0.35, 'overlay-padding': 6 } },
  { selector: 'edge', style: { width: 1, 'line-color': '#475569', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#475569',
      'curve-style': 'bezier', 'arrow-scale': 0.6, opacity: 0.55 } },
  { selector: 'edge.ring', style: { 'line-color': '#a855f7', 'target-arrow-color': '#a855f7', width: 2, opacity: 0.9 } },
  { selector: 'edge.blocked', style: { 'line-color': '#ef4444', 'target-arrow-color': '#ef4444', 'line-style': 'dashed', width: 2, opacity: 0.95 } },
];

// Incrementally sync the cytoscape instance with the model; returns true if elements were added.
function sync(cy, state, showTruth) {
  let added = false;
  cy.batch(() => {
    cy.nodes().forEach((n) => { if (!state.nodes.has(n.id())) n.remove(); });
    for (const [id, n] of state.nodes) {
      const data = { id, type: n.type, state: n.state, score: n.score, label: n.state !== 'normal' ? id : '' };
      let el = cy.getElementById(id);
      if (el.empty()) { el = cy.add({ group: 'nodes', data, position: { x: Math.random() * 500, y: Math.random() * 350 } }); added = true; }
      else el.data(data);
      el.toggleClass('truth', !!(showTruth && n.truth));
    }
    cy.edges().forEach((e) => { if (!state.edges.has(e.id())) e.remove(); });
    for (const [id, e] of state.edges) {
      let el = cy.getElementById(id);
      if (el.empty()) {
        if (!state.nodes.has(e.src) || !state.nodes.has(e.dst)) continue;
        el = cy.add({ group: 'edges', data: { id, source: e.src, target: e.dst } }); added = true;
      }
      el.toggleClass('ring', !!(showTruth && e.is_ring));
      el.toggleClass('blocked', !!e.blocked);
    }
  });
  return added;
}

export function GraphView({ state, showTruth, onSelect }) {
  const box = useRef(null), cy = useRef(null), dirty = useRef(false), cb = useRef(onSelect), first = useRef(true);
  cb.current = onSelect;

  const layout = (fit) => {
    if (!cy.current || cy.current.nodes().length === 0) return;
    cy.current.layout({ name: 'cose', animate: false, randomize: false, fit, padding: 30, nodeRepulsion: 9000,
      idealEdgeLength: 55, numIter: 250, gravity: 0.6 }).run();
  };

  useEffect(() => {
    cy.current = cytoscape({ container: box.current, style: STYLE, wheelSensitivity: 0.25, minZoom: 0.1, maxZoom: 3 });
    cy.current.on('tap', 'node', (e) => cb.current(e.target.id()));
    cy.current.on('tap', (e) => { if (e.target === cy.current) cb.current(null); });
    const t = setInterval(() => {
      if (dirty.current) { dirty.current = false; layout(first.current); if (cy.current.nodes().length > 5) first.current = false; }
    }, 2000);
    return () => { clearInterval(t); cy.current && cy.current.destroy(); cy.current = null; };
  }, []);

  useEffect(() => {
    if (cy.current && sync(cy.current, state, showTruth)) dirty.current = true;
  }, [state.version, showTruth]);

  return html`<div class="graphwrap">
    <div class="graph" ref=${box}></div>
    <div class="legend">
      <span><i class="dot n"></i>normal</span><span><i class="dot f"></i>flagged</span>
      <span><i class="dot h"></i>held</span><span><i class="dot z"></i>frozen</span>
      <button onClick=${() => layout(true)}>Re-layout / fit</button>
    </div>
  </div>`;
}
