# HANDOFF.md

## Phases done
- Phase 6 (explainability + polish): DONE. `mulenet/explain/explain.py` (rules + features + edge-removal probe), `GET /api/explain/{node}` (written, not executed: no fastapi), `NodeDetail` panel `Explain` in Panels.js (syntax-checked only), `scripts/demo.py`, `scripts/gen_report.py` -> `docs/EVALUATION.md`, `mulenet/livesmoke.py`, `tests/test_explain.py`, Makefile targets demo/report/check, README finalised. 23 Python tests pass (1 skipped: torch); `node --test test/model.test.js` 6 pass.
- Phase 0 (scaffold): DONE.
- Phase 1 (synthetic data): DONE.
- Phase 2 (graph features + baselines): DONE.
- Phase 5 (React dashboard): code DONE (Vite + React via htm + Cytoscape.js). UI state logic tested with node --test (7 pass, incl. contract test on real Python events). Vite build, React rendering, WS vs live uvicorn, Docker build **not executed**.
- Phase 4 (streaming backend): runtime/decision/simulator/bus DONE + 21 tests (1 skipped); FastAPI layer **written, not executed** (fastapi missing).
- Phase 3 (GNN): code DONE; model/training/inference **written, not executed** (no torch). Sample builder + extraction latency executed. 16 tests run, 1 skipped (torch).

## Next step
ALL 7 PHASES DONE. Remaining work is user-side verification, in this order: (1) `pip install -r requirements-deploy.txt; make serve; make ui` and click through the dashboard (render/layout bugs possible);
(2) `pip install torch; make train -- --quick`, then full `make train; make bench; make report` to get GNN metrics and real inference latency; (3) tune thresholds/weak-signal 0.35 and
consider decay for flags; (4) harder hard-negative variants (rent/friend-settle inside the window). Report any failures to the next chat with the traceback.

## File map
- `config.yaml` / `mulenet/config.py` (`load_config`, `get`)
- `mulenet/data/schema.py` `Txn`, `Dataset` (save/load/summary/finalize)
- `mulenet/data/normal.py` `generate_normal(cfg, rng)` -> accounts, txns, peers, merchants
- `mulenet/data/rings.py` `inject_ring(cfg, rng, peers, merchants, start_ts, ring_id, exclude, **overrides)` -> (txns, meta); reuse for live attacks in Phase 4
- `mulenet/data/hard_negatives.py` `make_hard_negative(...)` -> (txns, meta, new_accounts)
- `mulenet/data/generate.py` `build_dataset(cfg, seed)`
- `scripts/make_data.py` (`--sample`, `--out`, `--seed`); `data/sample/` committed sample (188 KB)
- `tests/test_scaffold.py`, `tests/test_data.py`
- `mulenet/graph/window.py` `RollingGraph(window).add(txn)`; `.g` is nx.DiGraph, edge attr tx=[(ts,amt)]
- `mulenet/graph/subgraph.py` `k_hop_nodes/k_hop_subgraph(g, seeds, k, max_nodes)` (newest edges first, bounded)
- `mulenet/features/node_features.py` `node_features`, `feature_vector`, `FEATURE_NAMES`, `subgraph_features`, `on_cycle`
- `mulenet/baseline/rules.py` `RuleBaseline`, `GraphHeuristic` (scorer(g,nodes,now)->{node:score}; `.fired()` gives rule names for explanations)
- `mulenet/evaluate.py` `replay/metrics/evaluate` (node P/R/F1, FPR all/hard-neg nodes/groups/by type, ring recall before cash-out, delay)
- `scripts/run_baseline.py` -> `docs/baseline_metrics.json`; `tests/test_graph.py`
- `mulenet/models/dataset.py` `build_sample(g, seeds, now, cfg, labels)` (train/serve parity), `build_samples(ds,cfg,...)`, `fit_scaler`, `to_pyg_data`
- `mulenet/models/gnn.py` `MuleGNN`, `build_model`, `collate`, `save/load_checkpoint`, `GNNScorer(model, mean, std, cfg)`; HAS_TORCH/HAS_PYG flags
- `scripts/train.py` (train seed1/val seed2/test=default seed42; threshold picked on val under hard-neg FPR budget; `--quick`, `--force-pure`), `scripts/bench_latency.py` (`--no-model`), `tests/test_models.py`
- `mulenet/evaluate.py` also has `replay_scores`, `first_from_scores` (threshold sweeps from one replay)
- `mulenet/stream/bus.py` `StateStore`, `InProcessBus`, `make_bus/make_store`; `stream/adapters.py` optional Kafka/Redis (unexecuted); `stream/simulator.py` `LiveSimulator` (advance, launch_attack)
- `mulenet/decision.py` `DecisionEngine` (escalate-only, release, thresholds); `mulenet/scorer.py` `select_scorer`; `baseline/rules.py` + `GradedHeuristic`
- `mulenet/runtime.py` `Runtime` (handle_txn, launch_attack, snapshot, metrics, start/stop/reset), `EventHub`; `mulenet/api/app.py` FastAPI `create_app`/`app`
- `Dockerfile`, `.dockerignore`, `requirements-deploy.txt`; `tests/test_runtime.py`
- `frontend/` package.json (react, react-dom, cytoscape, htm, vite), vite.config.js (proxy /api,/ws), `src/model.js` (pure reducer: caps 300 nodes, 600 s edge window), `api.js`, `GraphView.js`, `Controls.js`, `Panels.js`, `App.js`, `main.js`, `styles.css`; `test/model.test.js`, `test/contract.test.js` (set MULENET_EVENTS=/path/events.json recorded from Python runtime)
- `docs/MuleNet-Graph_Ideation_Document.pdf`, empty packages for later phases, `frontend/README.md` placeholder

## How to run
`make install; make test; make demo; make report` (see README "Run instructions" for full stack and GNN).

## Data model (needed by later phases)
- Txn fields: txn_id, ts(s), src, dst, amount, kind, label(1=ring flow), group_id, scenario
  (normal | ring | ring_camouflage | hardneg:<type>). Camouflage txns are label 0 but sender is a mule node.
- Node labels: accounts[id]["label"]=1 for mules and cash-out accounts (C###); victims are label 0.
  Hard-neg centers carry `hardneg_id`/`hardneg_type`; use them for FPR on hard negatives.
- Ring truth in `scenarios.json`/`ds.rings`: mules, victims, cashout, start_ts, cashout_ts (earliest
  txn into cash-out), params. Detection delay = cashout_ts - alert time.
- Account ids: A##### peers, M#### merchants, U## utilities, S### shops, L### landlords, E### employers, C### cash-out.

## Decisions
- Cytoscape.js frontend. YAML config. Stdlib unittest. In-process stream with optional Kafka/Redis adapters.
- Mules are drawn from normal peer accounts (real mules are often genuine people lending accounts).
- Rings never share mules; hard-negative participants never include ring mules (clean FPR measurement).
- `split_ratio` applies to fan_out only. fan_out tree widens, fan_in funnel narrows. Circular: depth-1 laps, then exit to cash-out.
- `hard_negative_rate` config key was replaced by `n_hard_negatives`.
- Default data: 2000 peers, 20 rings, 40 hard negatives (8 per type), 20k normal txns over 6 simulated hours.

## Environment findings (build sandbox, Python 3.12.3, 1 vCPU Xeon 2.1 GHz)
- Available: networkx, numpy, pyyaml, node 22. Network disabled.
- NOT installed: torch, torch_geometric, fastapi, pytest. Phase 3 model code likely "written, not executed";
  Phase 4 API possibly the same. Phases 2 is pure numpy/networkx and will be executed.
- `npm` raised a config-prefix error from /home/claude/.npmrc (Phase 5 build may need a workaround).

## Baseline results (seed 42, default cfg, synthetic)
rules: P .87 R .61 F1 .72, hard-neg FPR groups .33 (salary 1.0, shopkeeper .62). graph heuristic: P .98 R .83 F1 .90, hard-neg FPR groups .03 (salary .12). Both detect 100% of rings pre-cash-out (median delay 24-27 s). Rent/friend_settle hard negatives exceed the 600 s window so are easy; harder variant is a to-do.

## Phase 3 honesty status
- NOT run: model forward/backward, training, checkpoint, GNN metrics, inference latency. User must run `pip install torch; make train; make bench`.
- Executed: sample builder; extraction+features latency p50/p95/p99 = 0.13/0.63/0.74 ms (batch 1, 1 vCPU, excludes model) in docs/latency_report.json.
- Checkpoints are backend-specific (PyG vs pure). GAT requires PyG; fallback is SAGE.
- Edge features are not used by the model (edge_index only); explainability in Phase 6 will use occlusion/gradient on nodes/edges.

## Phase 4 findings (fallback scorer, simulated)
- No attacks, 1200 sim-s: 91 nodes flagged, 20 held, 2 frozen (all legit); 27 legit txns blocked. 6 rings: all held, 4/6 still reached cash-out. Noisy: the 0.35 weak-signal flag and salary/shopkeeper hard negatives drive false alarms. Candidates: tune/raise weak-signal, allow decay, or use trained GNN.
- Not executed: FastAPI app/WebSocket, Kafka/Redis adapters, Docker build.

## Phase 5 notes
- UI uses `htm` tagged templates (no JSX compiler needed). No package-lock.json (could not generate offline); Dockerfile uses `npm install`.
- First local run may reveal render/layout bugs not catchable here; fix before demo. If WS fails behind a proxy, check /ws upgrade support.

## Known issues / caveats
- Phase 6: explain probe uses the scorer on a copy of the 2-hop sub-graph with one edge removed (<=20 re-scores); it is not causal proof. No GNN feature-occlusion. `explain_node` has an ugly cycle_len conditional (config has no cycle_len key; harmless).
- Live-sim false-alarm counts vary with seed (seed 7: 23 legit flagged, 0 held, no attacks; earlier seed showed 91/20/2).
- Flags are 'ever flagged' per node (no un-flagging); k-hop truncation on hubs keeps newest edges only.
- Ring and hard-negative shapes are author-defined, so results will be optimistic. Not validated vs real or public data.
- Multi-seed check was done ad hoc (10 seeds, structure tests passed); not part of the test suite.
