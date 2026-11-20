# MuleNet-Graph

Real-time UPI mule-account ring detector: a streaming Graph Neural Network
scores small transaction sub-graphs and a graded response (monitor, flag, hold,
freeze) acts on the score. Hackathon prototype.

> **ALL DATA IS SYNTHETIC.** No real UPI, bank or customer data is used.
> This is **not production-ready** and makes **no claim of real-world accuracy**.
> Any latency figure (50 ms target) is a **benchmark under stated simulated load only**.

## Problem
UPI payments settle instantly and cannot be reversed, so stolen funds can pass
through chains of mule accounts within minutes (officially described
qualitatively; see `MuleNet-Graph_Ideation_Document.pdf` for cited sources and
scope notes). Single-account rules often miss mules, whose signal lives in the
surrounding network structure and speed of transfers.

## Approach
1. Rolling in-memory transaction graph (NetworkX) over a recent time window.
2. Per transaction, extract a bounded k-hop sub-graph around the accounts involved.
3. Score with a GNN (GraphSAGE or GAT; PyG, with a pure-PyTorch fallback).
   Signals: fan-out, fan-in, circular flow, short hop gaps / velocity.
4. Graded response: monitor, flag (step-up/delay), hold outgoing, freeze + escalate
   (final action assumes human review).
5. Live simulator dashboard (React + Cytoscape.js) injects synthetic rings into
   normal traffic and colours nodes by state in real time.

## Honesty notes
- Ring patterns are defined by the authors, so results are likely optimistic.
- **Hard negatives** (shopkeepers, group splits, rent, salary) are included and the
  **false-positive rate is reported prominently**.
- The GNN is compared against a rule-based baseline.
- Kafka/Redis are **not required**: an in-process asyncio queue and key-value store
  share the same interface; real adapters are optional behind `stream.backend`.
- Real mule accounts are often genuine people lending accounts: nodes are *risk
  nodes for review*, not accusations.
- Not a replacement for MuleHunter.AI, FRI, or the I4C Suspect Registry; a complement
  concept only.

## Layout
```
mulenet/  config, data, graph, features, baseline, models, stream, api, explain
scripts/  CLI entry points (make_data, run_baseline, train, bench_latency, demo, gen_report)
tests/    unit tests
frontend/ React (Vite) + Cytoscape.js dashboard
docs/     EVALUATION.md (generated), metrics JSON, ideation PDF
config.yaml  all tunables
```

## Run instructions
Core (no torch, no FastAPI): `make install && make test && make demo && make report`. `make demo` is a headless end-to-end run
(normal traffic, 3 injected rings, detection timeline, one explanation); `make report` regenerates `docs/EVALUATION.md`.
Full stack: `pip install -r requirements-deploy.txt`, `make serve` (API :8000), `make ui` (Vite dev server; proxies /api and /ws).
GNN: `pip install torch` (PyG optional), `make train` (try `--quick` first), `make bench`, `make report`.
Without a checkpoint the backend uses the graded heuristic fallback and says so in the UI and `/api/health`.

## Explainability (Phase 6)
`GET /api/explain/{node}` and the node panel in the dashboard show: rules fired (heuristic scorer), the node's window features, and an
**edge-removal probe** (drop one incident edge, re-score, show the score drop). The probe is model-agnostic, so it works for the GNN too, but
it explains *this scorer's behaviour*, not causal truth. For the GNN there are no named rules, only the probe and features. Nodes are risk
nodes for human review, not accusations.

## Known limitations
- All data synthetic; ring and hard-negative shapes are author-defined, so metrics are optimistic. Not validated on real or public data.
- GNN never trained or run in the build sandbox (no torch): no GNN metrics, and the 50 ms target is unverified. Only extraction+features latency was measured.
- FastAPI layer, Vite build, React rendering against live WebSocket, Docker and Kafka/Redis adapters were not executed in the build sandbox. Explain endpoint and panel: logic tested via Python, UI code syntax-checked only.
- Escalate-only policy flags legitimate accounts (see `docs/EVALUATION.md` sec. 2); some injected rings still reach cash-out because hops are seconds apart.
- Rolling window is 600 s; slower rings or longer legitimate cycles are outside it. No auth beyond an optional admin token; no rate limiting.
- Not a replacement for MuleHunter.AI, FRI or the I4C Suspect Registry.

## Data (Phase 1)
`make data` writes the full synthetic set to `data/generated/`; `python3 scripts/make_data.py --sample`
writes a small one to `data/sample/` (txns.csv, accounts.csv, scenarios.json = ground truth).
Rings: fan_out, fan_in, circular, with configurable size/depth/hop gap/split ratio/skim and
camouflage payments. Hard negatives: shopkeeper burst (+sweep), group split, rent, salary, friend settle (small legit cycle).

## Baselines (Phase 2) - SYNTHETIC data, seed 42, default config
`python3 scripts/run_baseline.py` replays the stream through a 600 s rolling graph and writes `docs/baseline_metrics.json`.
| baseline | node P | node R | node F1 | FPR hard-neg nodes | FPR hard-neg groups | ring recall pre-cash-out |
|---|---|---|---|---|---|---|
| single-account rules | 0.87 | 0.61 | 0.72 | 0.02 | **0.33** | 1.00 |
| graph heuristic | 0.98 | 0.83 | 0.90 | 0.00 | **0.03** | 1.00 |

Single-account rules false-alarm on salary bursts (100%) and shopkeepers (62%). These numbers are optimistic: rings are
author-defined and the baselines were not tuned against adversarial variants. Rent/friend-settle hard negatives span more
than the 600 s window, so they are easy here; a harder variant is a to-do.

## GNN (Phase 3) - STATUS: written, NOT executed
Direction-aware GraphSAGE/GAT (PyG if installed, pure-PyTorch SAGE fallback). **No torch in the build sandbox, so the model was
never trained or run here; there is no checkpoint and no GNN metrics yet.** On your machine: `pip install torch` (PyG optional),
then `make train` (add `--quick` first as a smoke test) and `make bench`. This writes `docs/gnn_metrics.json`, `docs/latency_report.json`
and `checkpoints/mulenet.pt`, and prints the GNN-vs-baseline table (FPR on hard negatives included). Executed here: the sample builder
(7.9k sub-graph samples in 2.5 s) and sub-graph extraction + feature latency (p50 0.13 ms, p95 0.63 ms, p99 0.74 ms, batch 1,
1 vCPU Xeon 2.1 GHz, ~600 edges in window, ~16-node sub-graphs). That excludes model inference, so it is NOT the 50 ms figure.

## Streaming backend (Phase 4) - SYNTHETIC
`mulenet/runtime.py` runs: live simulator -> in-process asyncio bus -> rolling graph -> scorer -> graded decision -> events.
Scorer = trained GNN if torch + `checkpoints/mulenet.pt` exist, else a **graded heuristic fallback (not a GNN)**; the API/UI always
report which. Policy: score >= flag/hold/freeze thresholds (config `policy`, adjustable live). States only escalate until a human
releases the node; "held"/"frozen" nodes have outgoing transfers blocked in the simulation. Live metrics include **legit
transactions blocked and legit groups harmed** (ground truth from the simulator), not just ring catches.
Kafka/Redis adapters exist (`stream.backend: kafka|redis`) but are optional and unexecuted.

API (FastAPI, **written, not executed here**): `GET /api/health|state|metrics|thresholds`, `POST /api/thresholds|attack|control|reset|release/{node}`,
`WS /ws` (snapshot, txn, txn_blocked, state, attack, metrics). Set `MULENET_ADMIN_TOKEN` to require `X-Admin-Token` on POSTs
(recommended for any public demo; there is no other auth or rate limiting).

Smoke run of the runtime with the fallback scorer (seed-specific, simulated, 1 vCPU): scoring p50/p95/p99 = 0.05/0.13/0.19 ms per event.
With NO attacks in 1,200 simulated seconds, ~91 normal accounts were flagged, 20 held and 2 frozen (27 legit transfers blocked): the
fallback + escalate-only policy is noisy. With 6 injected rings, all were held, but 4 of 6 still reached cash-out (hops are seconds apart).
Treat these as honest weaknesses to tune against, not results.

## Run / deploy
```
pip install -r requirements-deploy.txt && uvicorn mulenet.api.app:app --port 8000   # API at /api, WS at /ws
docker build -t mulenet-graph . && docker run -p 8000:8000 -e MULENET_ADMIN_TOKEN=change-me mulenet-graph
```
The Dockerfile builds the React dashboard (Phase 5) when `frontend/package.json` exists and serves it from the same origin.
Any container host with WebSocket support works (Render, Railway, Fly.io, Cloud Run). Honour `$PORT`. Footer must keep "SIMULATED DATA".

## Dashboard (Phase 5) - React + Vite + Cytoscape.js
`frontend/`: live graph coloured by state (normal / flagged / held / frozen), attack launcher (pattern, size, depth, hop gap, split),
threshold sliders, pause/speed/reset, event log, metrics panel (names the active scorer, shows **legit transfers blocked / legit
accounts flagged**, scoring latency with its caveat), click a node to release it (simulated human review), "SIMULATED DATA" footer.
Dev: `make serve` (port 8000) + `make ui` (Vite, proxies /api and /ws). Production: `docker build` builds the UI and FastAPI serves it.
**Verified here:** UI state logic (`node --test`, 7 tests incl. a recording of real Python runtime events fed through the model),
and JS syntax check of every module. **NOT verified here:** `npm install`/`vite build`, the React components rendering, Cytoscape
layout, the live WebSocket against uvicorn, and the Docker build (no registry/network or fastapi in the build sandbox). Do a first
run locally before demoing: `pip install -r requirements-deploy.txt`, `uvicorn mulenet.api.app:app`, then `cd frontend && npm install && npm run dev`.
