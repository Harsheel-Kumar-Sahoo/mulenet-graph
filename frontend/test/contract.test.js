// Feeds a real recording from the Python runtime (if present at $MULENET_EVENTS) through the UI model.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { initial, applyBatch, MAX_NODES } from '../src/model.js';

const p = process.env.MULENET_EVENTS;
test('python event stream is consumable by the UI model', { skip: !p || !fs.existsSync(p) }, () => {
  const msgs = JSON.parse(fs.readFileSync(p, 'utf8'));
  let s = initial();
  for (let i = 0; i < msgs.length; i += 25) s = applyBatch(s, msgs.slice(i, i + 25));
  assert.ok(s.nodes.size > 0 && s.nodes.size <= MAX_NODES);
  assert.ok(s.edges.size > 0);
  assert.ok([...s.nodes.values()].some((n) => n.state !== 'normal'), 'some node should be flagged/held/frozen');
  assert.ok([...s.nodes.values()].some((n) => n.truth), 'ring mules marked as ground truth');
  assert.ok(s.metrics && s.metrics.scorer);
  for (const e of s.edges.values()) assert.ok(s.nodes.has(e.src) && s.nodes.has(e.dst));
  console.log('nodes', s.nodes.size, 'edges', s.edges.size, 'log', s.log.length, 'states', [...new Set([...s.nodes.values()].map((n) => n.state))]);
});
