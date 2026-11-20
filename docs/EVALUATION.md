# Evaluation report

> **SYNTHETIC DATA ONLY.** Ring and hard-negative shapes were written by the authors, so every number below is likely optimistic.
> Not validated on real or public UPI data. Not production-ready. No claim of real-world accuracy.

## 1. Detection vs baselines (offline replay, default config, seed 42)

| model | node P | node R | node F1 | **FPR hard-neg groups** | FPR hard-neg nodes | ring recall pre-cash-out | median delay s |
|---|---|---|---|---|---|---|---|
| single_account_rules | 0.87 | 0.61 | 0.72 | **0.33** | 0.020 | 1.00 | 27.0 |
| graph_heuristic | 0.98 | 0.83 | 0.90 | **0.03** | 0.001 | 1.00 | 24.0 |
| GNN graphsage/pure (thr 0.95) | 0.97 | 0.99 | 0.98 | **0.05** | 0.003 | 1.00 | 32.5 |

### False-positive rate by hard-negative type (share of legitimate scenarios with >=1 account alerted)

| type | single-account rules | graph heuristic |
|---|---|---|
| shopkeeper | 0.62 | 0.00 |
| group_split | 0.00 | 0.00 |
| rent | 0.00 | 0.00 |
| salary | 1.00 | 0.12 |
| friend_settle | 0.00 | 0.00 |

Rent and friend-settle scenarios span more than the 600 s window, so they are easy here; a harder variant is a to-do.

## 2. Live simulation (graded response, escalate-only policy)

**No attacks, 1200 simulated s** (scorer: gnn-graphsage-pure)

- legit accounts ever flagged/held/frozen: 1356 / 18 / 1; legit transfers blocked: 12; legit scenarios harmed: 1

**6 injected rings (2 per pattern), seed 7** (scorer: gnn-graphsage-pure)

- legit accounts ever flagged/held/frozen: 962 / 8 / 0; legit transfers blocked: 52; legit scenarios harmed: 4
- rings held (any mule): 6/6; interrupted before finishing: 6/6; cash-out still reached: 2/6; ring transfers blocked: 49

## 3. Latency (simulated load, NOT a production figure)

- Sub-graph extraction + features, batch 1: p50/p95/p99 = 0.35/1.46/1.76 ms (AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD, 16 vCPU, ~605 edges in window, ~15.9-node sub-graphs, 3000 events).
- GNN inference / total: {'p50': 0.92, 'p95': 1.21, 'p99': 1.48} / {'p50': 1.32, 'p95': 2.51, 'p99': 2.91}. The 50 ms target is **unverified** until `make bench` is run with torch.

## 4. Honest weaknesses

- The fallback scorer plus escalate-only policy flags legitimate accounts even with no attack (see section 2; counts vary by seed and earlier runs showed held/frozen legit nodes), and offline hard-negative FPR is not zero (salary).
- In the live sim hops are seconds apart, so some rings reach cash-out even when held. Holding is not the same as stopping.
- Thresholds were not tuned against adversarial or slower rings.
