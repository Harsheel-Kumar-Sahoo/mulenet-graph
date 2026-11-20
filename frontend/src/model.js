// Pure state logic (no React / DOM) so it can be unit-tested with `node --test`.
export const WINDOW = 600;      // simulated seconds an edge stays visible (matches graph.window_seconds)
export const MAX_NODES = 300;   // keep the drawing bounded
export const LOG_CAP = 150;

export const initial = () => ({
  connected: false, nodes: new Map(), edges: new Map(), log: [], metrics: null, thresholds: null,
  scorer: '', simTime: 0, version: 0, blockedLogged: new Set(), _k: 0,
});

const ek = (s, d) => `${s}>${d}`;
const inr = (n) => '\u20B9' + Math.round(n).toLocaleString('en-IN');

function ensureNode(st, id, type, ts) {
  let n = st.nodes.get(id);
  if (!n) {
    n = { id, type: type || '?', state: 'normal', score: 0, truth: false, lastSeen: ts ?? st.simTime };
    st.nodes.set(id, n);
  } else {
    if (type && n.type === '?') n.type = type;
    if (ts != null) n.lastSeen = ts;
  }
  return n;
}

function pushLog(st, kind, text, ts) {
  st.log.unshift({ kind, text, ts, k: ++st._k });
  if (st.log.length > LOG_CAP) st.log.length = LOG_CAP;
}

function touchEdge(st, src, dst, ts) {
  const key = ek(src, dst);
  let e = st.edges.get(key);
  if (!e) { e = { id: key, src, dst, count: 0, amount: 0, is_ring: 0, lastTs: ts, blocked: false }; st.edges.set(key, e); }
  e.lastTs = ts;
  return e;
}

function applyOne(st, m) {
  const d = m.data;
  switch (m.type) {
    case 'conn': st.connected = !!d; break;
    case 'thresholds': st.thresholds = d; break;
    case 'snapshot': {
      st.nodes.clear(); st.edges.clear(); st.blockedLogged.clear();
      st.scorer = d.scorer || ''; st.thresholds = d.thresholds || st.thresholds; st.metrics = d.metrics || null;
      st.simTime = (d.metrics && d.metrics.sim_time) || st.simTime;
      for (const n of d.nodes || []) {
        const x = ensureNode(st, n.id, n.type, st.simTime);
        x.state = n.state; x.score = n.score; x.truth = !!n.truth_mule;
      }
      for (const e of d.edges || []) {
        ensureNode(st, e.src, null, st.simTime); ensureNode(st, e.dst, null, st.simTime);
        Object.assign(touchEdge(st, e.src, e.dst, st.simTime), { count: e.count, amount: e.amount, is_ring: e.is_ring });
      }
      break;
    }
    case 'txn': {
      st.simTime = Math.max(st.simTime, d.ts);
      ensureNode(st, d.src, d.src_type, d.ts); ensureNode(st, d.dst, d.dst_type, d.ts);
      const e = touchEdge(st, d.src, d.dst, d.ts);
      e.count += 1; e.amount += d.amount; e.is_ring = e.is_ring | d.is_ring;
      break;
    }
    case 'txn_blocked': {
      st.simTime = Math.max(st.simTime, d.ts);
      ensureNode(st, d.src, null, d.ts); ensureNode(st, d.dst, null, d.ts);
      touchEdge(st, d.src, d.dst, d.ts).blocked = true;
      if (!st.blockedLogged.has(d.src)) {            // log once per sender to avoid flooding
        st.blockedLogged.add(d.src);
        pushLog(st, d.is_ring ? 'blocked_ring' : 'blocked_legit',
          `Outgoing blocked (${d.reason}): ${d.src} \u2192 ${d.dst} ${inr(d.amount)}${d.is_ring ? '' : ' [legit transfer blocked]'}`, d.ts);
      }
      break;
    }
    case 'state': {
      const n = ensureNode(st, d.node, null, d.ts);
      n.state = d.to; n.score = d.score;
      if (d.to === 'normal') st.blockedLogged.delete(d.node);
      pushLog(st, 'state', `${d.node} ${d.from} \u2192 ${d.to} [${d.action}] score ${d.score}` +
        (d.reasons && d.reasons.length ? ` (${d.reasons.join(', ')})` : '') + (d.needs_review ? ' \u2014 needs human review' : ''), d.ts);
      break;
    }
    case 'attack': {
      for (const id of d.mules) ensureNode(st, id, null, d.start_ts).truth = true;
      ensureNode(st, d.cashout, 'cashout', d.start_ts).truth = true;
      pushLog(st, 'attack', `Simulated ${d.pattern} ring launched: ${d.mules.length} mule accounts (${d.ring_id})`, d.start_ts);
      break;
    }
    case 'metrics': st.metrics = d; break;
    default: break;
  }
}

function evict(st) {
  const cutoff = st.simTime - WINDOW;
  for (const [k, e] of st.edges) if (e.lastTs < cutoff) st.edges.delete(k);
  const ref = new Set();
  for (const e of st.edges.values()) { ref.add(e.src); ref.add(e.dst); }
  for (const [id, n] of st.nodes) {
    if (ref.has(id)) continue;
    if (n.state === 'normal' ? n.lastSeen < cutoff : n.lastSeen < st.simTime - 3 * WINDOW) st.nodes.delete(id);
  }
  if (st.nodes.size > MAX_NODES) {
    const rank = [...st.nodes.values()].sort((a, b) => (a.state === 'normal') === (b.state === 'normal') ? a.lastSeen - b.lastSeen : (a.state === 'normal' ? -1 : 1));
    for (const n of rank) {
      if (st.nodes.size <= MAX_NODES) break;
      st.nodes.delete(n.id);
      for (const [k, e] of st.edges) if (e.src === n.id || e.dst === n.id) st.edges.delete(k);
    }
  }
}

// Applies a batch of websocket/local messages; returns a new top-level object (maps mutated in place for speed).
export function applyBatch(state, msgs) {
  for (const m of msgs) applyOne(state, m);
  evict(state);
  return { ...state, version: state.version + 1 };
}
