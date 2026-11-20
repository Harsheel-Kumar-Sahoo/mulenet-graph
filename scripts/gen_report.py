"""Build docs/EVALUATION.md from the JSON reports + a fresh live-sim run. Only numbers present in the JSON/run are written;
a missing GNN report is stated as missing, never filled in. SYNTHETIC DATA."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from mulenet.config import load_config
from mulenet.livesmoke import run_live

D = ROOT / "docs"; rd = lambda n: json.loads((D / n).read_text()) if (D / n).exists() else None
base, gnn, lat = rd("baseline_metrics.json"), rd("gnn_metrics.json"), rd("latency_report.json")
row = lambda name, r: (f"| {name} | {r['node']['precision']:.2f} | {r['node']['recall']:.2f} | {r['node']['f1']:.2f} | **{r['hard_negative']['fpr_groups']:.2f}** | "
                       f"{r['hard_negative']['fpr_nodes']:.3f} | {r['ring']['recall_before_cashout']:.2f} | {round(r['ring']['delay_s_before_cashout_median'], 1)} |")
L = ["# Evaluation report", "", "> **SYNTHETIC DATA ONLY.** Ring and hard-negative shapes were written by the authors, so every number below is likely optimistic.",
     "> Not validated on real or public UPI data. Not production-ready. No claim of real-world accuracy.", "",
     "## 1. Detection vs baselines (offline replay, default config, seed 42)", "",
     "| model | node P | node R | node F1 | **FPR hard-neg groups** | FPR hard-neg nodes | ring recall pre-cash-out | median delay s |", "|---|---|---|---|---|---|---|---|"]
for k, v in (base or {}).items():
    if isinstance(v, dict) and "node" in v: L.append(row(k, v))
if gnn: L.append(row(f"GNN {gnn['arch']}/{gnn['backend']} (thr {gnn['threshold']}{', QUICK MODE' if gnn.get('quick_mode') else ''})", gnn["gnn"]))
else: L += ["", "**GNN row: MISSING.** `docs/gnn_metrics.json` does not exist: the GNN was not trained in the build sandbox (no torch). Run `make train`, then `make report`."]
if base:
    hb = base.get("graph_heuristic", {}).get("hard_negative", {}).get("fpr_groups_by_type")
    rb = base.get("single_account_rules", {}).get("hard_negative", {}).get("fpr_groups_by_type")
    if hb and rb:
        L += ["", "### False-positive rate by hard-negative type (share of legitimate scenarios with >=1 account alerted)", "", "| type | single-account rules | graph heuristic |", "|---|---|---|"]
        L += [f"| {t} | {rb[t]:.2f} | {hb[t]:.2f} |" for t in rb]
L += ["", "Rent and friend-settle scenarios span more than the 600 s window, so they are easy here; a harder variant is a to-do.", "",
      "## 2. Live simulation (graded response, escalate-only policy)", ""]
cfg = load_config()
for title, atk, kw in (("No attacks, 1200 simulated s", [], dict(warmup=1200, after=0)),
                       ("6 injected rings (2 per pattern), seed 7", [dict(pattern=p) for p in ("fan_out", "fan_in", "circular") * 2], dict(warmup=300, after=300))):
    rt = run_live(cfg, seed=7, attacks=atk, **kw); m = rt.metrics(); fa, s = m["false_alarm_nodes"], m["node_states"]
    L += [f"**{title}** (scorer: {m['scorer']})", "",
          f"- legit accounts ever flagged/held/frozen: {fa.get('flagged',0)} / {fa.get('held',0)} / {fa.get('frozen',0)}; legit transfers blocked: {m['blocked_legit']}; legit scenarios harmed: {m['legit_groups_harmed']}"]
    if atk:
        a = m["attacks"]; L += [f"- rings held (any mule): {sum(1 for r in a if r['secs_to_hold'] is not None)}/{len(a)}; interrupted before finishing: {sum(r['interrupted'] for r in a)}/{len(a)}; cash-out still reached: {sum(r['cashout_reached'] for r in a)}/{len(a)}; ring transfers blocked: {m['blocked_ring']}"]
    L.append("")
L += ["## 3. Latency (simulated load, NOT a production figure)", ""]
if lat:
    e = lat["extract_features_ms"]
    L += [f"- Sub-graph extraction + features, batch 1: p50/p95/p99 = {e['p50']}/{e['p95']}/{e['p99']} ms ({lat['cpu']}, {lat['cpu_count']} vCPU, ~{lat['avg_edges_in_window']} edges in window, ~{lat['avg_subgraph_nodes']}-node sub-graphs, {lat['events_timed']} events).",
          f"- GNN inference / total: {lat['gnn_inference_ms']} / {lat['total_ms']}. The 50 ms target is **unverified** until `make bench` is run with torch."]
L += ["", "## 4. Honest weaknesses", "",
      "- The fallback scorer plus escalate-only policy flags legitimate accounts even with no attack (see section 2; counts vary by seed and earlier runs showed held/frozen legit nodes), and offline hard-negative FPR is not zero (salary).",
      "- In the live sim hops are seconds apart, so some rings reach cash-out even when held. Holding is not the same as stopping.",
      "- Thresholds were not tuned against adversarial or slower rings.", ""]
(D / "EVALUATION.md").write_text("\n".join(L)); print("wrote docs/EVALUATION.md")
