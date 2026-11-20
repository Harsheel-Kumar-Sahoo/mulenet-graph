import test from 'node:test';
import assert from 'node:assert/strict';
import { initial, applyBatch, WINDOW, MAX_NODES, LOG_CAP } from '../src/model.js';

const tx = (src, dst, ts, extra = {}) => ({ type: 'txn', data: { id: 1, src, dst, amount: 100, ts, kind: 'peer', is_ring: 0, src_type: 'peer', dst_type: 'peer', ...extra } });

test('snapshot then txn builds nodes and edges', () => {
  let s = applyBatch(initial(), [{ type: 'snapshot', data: { scorer: 'x', thresholds: { flag_at: .3, hold_at: .6, freeze_at: .85 },
    metrics: { sim_time: 50 }, nodes: [{ id: 'A', type: 'peer', state: 'held', score: .7, truth_mule: true }], edges: [] } }]);
  assert.equal(s.nodes.get('A').state, 'held'); assert.equal(s.scorer, 'x'); assert.equal(s.simTime, 50);
  s = applyBatch(s, [tx('A', 'B', 51), tx('A', 'B', 52)]);
  assert.equal(s.edges.get('A>B').count, 2); assert.equal(s.nodes.get('B').type, 'peer'); assert.equal(s.version, 2);
});

test('state events update node and log; release clears block-log throttle', () => {
  let s = applyBatch(initial(), [tx('A', 'B', 1), { type: 'state', data: { node: 'A', from: 'normal', to: 'frozen', action: 'freeze', score: .9, ts: 2, reasons: ['H1'], needs_review: true } }]);
  assert.equal(s.nodes.get('A').state, 'frozen'); assert.match(s.log[0].text, /needs human review/);
  s = applyBatch(s, [{ type: 'txn_blocked', data: { src: 'A', dst: 'B', amount: 5, ts: 3, reason: 'frozen', is_ring: 0 } }, { type: 'txn_blocked', data: { src: 'A', dst: 'C', amount: 5, ts: 4, reason: 'frozen', is_ring: 0 } }]);
  assert.equal(s.log.filter((l) => l.kind === 'blocked_legit').length, 1);        // throttled
  assert.equal(s.edges.get('A>B').blocked, true);
  s = applyBatch(s, [{ type: 'state', data: { node: 'A', from: 'frozen', to: 'normal', action: 'released_by_reviewer', score: 0, ts: 5, reasons: [], needs_review: false } }]);
  assert.equal(s.blockedLogged.has('A'), false);
});

test('attack marks ground-truth mules', () => {
  const s = applyBatch(initial(), [{ type: 'attack', data: { ring_id: 'ring0', pattern: 'fan_out', mules: ['M1', 'M2'], cashout: 'C000', start_ts: 10 } }]);
  assert.equal(s.nodes.get('M1').truth, true); assert.equal(s.nodes.get('C000').type, 'cashout'); assert.equal(s.log[0].kind, 'attack');
});

test('old edges and idle normal nodes are evicted; non-normal nodes survive a while', () => {
  let s = applyBatch(initial(), [tx('A', 'B', 0), { type: 'state', data: { node: 'B', from: 'normal', to: 'flagged', action: 'flag', score: .4, ts: 0, reasons: [], needs_review: false } }]);
  s = applyBatch(s, [tx('X', 'Y', WINDOW + 10)]);
  assert.equal(s.edges.has('A>B'), false); assert.equal(s.nodes.has('A'), false);
  assert.equal(s.nodes.has('B'), true); assert.ok(s.edges.has('X>Y'));
});

test('node cap drops normal nodes first and removes their edges', () => {
  const msgs = [{ type: 'state', data: { node: 'KEEP', from: 'normal', to: 'frozen', action: 'f', score: .9, ts: 1, reasons: [], needs_review: true } }];
  for (let i = 0; i < MAX_NODES + 50; i++) msgs.push(tx(`S${i}`, `D${i}`, 1 + i * 0.01));
  const s = applyBatch(initial(), msgs);
  assert.ok(s.nodes.size <= MAX_NODES); assert.ok(s.nodes.has('KEEP'));
  for (const e of s.edges.values()) { assert.ok(s.nodes.has(e.src) && s.nodes.has(e.dst)); }
});

test('log is capped; conn/threshold/metrics messages', () => {
  const msgs = []; for (let i = 0; i < LOG_CAP + 20; i++) msgs.push({ type: 'attack', data: { ring_id: 'r' + i, pattern: 'circular', mules: [], cashout: 'C' + i, start_ts: i } });
  let s = applyBatch(initial(), msgs); assert.equal(s.log.length, LOG_CAP);
  s = applyBatch(s, [{ type: 'conn', data: true }, { type: 'thresholds', data: { flag_at: .2 } }, { type: 'metrics', data: { txns: 5 } }]);
  assert.equal(s.connected, true); assert.equal(s.thresholds.flag_at, .2); assert.equal(s.metrics.txns, 5);
});
