"""Run both baselines on synthetic data; print + save metrics (docs/baseline_metrics.json)."""
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mulenet.config import load_config, ROOT
from mulenet.data.generate import build_dataset
from mulenet.data.schema import Dataset
from mulenet.evaluate import evaluate
from mulenet.baseline.rules import RuleBaseline, GraphHeuristic

p = argparse.ArgumentParser(); p.add_argument("--data"); p.add_argument("--seed", type=int)
a = p.parse_args(); cfg = load_config()
ds = Dataset.load(a.data) if a.data else build_dataset(cfg, a.seed)
res = {"synthetic": True, "summary": ds.summary(), "seed": ds.meta.get("seed")}
for B in (RuleBaseline, GraphHeuristic):
    t0 = time.time(); m = evaluate(ds, B(cfg), cfg, cfg["baseline"]["flag_threshold"])
    m["replay_seconds"] = round(time.time() - t0, 1); res[B.name] = m
out = ROOT / "docs" / "baseline_metrics.json"; out.write_text(json.dumps(res, indent=1))
print("SYNTHETIC DATA. Baselines are simple and untuned.\n")
print("| baseline | node P | node R | node F1 | FPR hard-neg (nodes) | FPR hard-neg (groups) | ring recall pre-cashout | median delay s |")
print("|---|---|---|---|---|---|---|---|")
for k in ("single_account_rules", "graph_heuristic"):
    m = res[k]; n, h, r = m["node"], m["hard_negative"], m["ring"]
    d = r["delay_s_before_cashout_median"]
    print(f"| {k} | {n['precision']:.2f} | {n['recall']:.2f} | {n['f1']:.2f} | {h['fpr_nodes']:.2f} | {h['fpr_groups']:.2f} | {r['recall_before_cashout']:.2f} | {'-' if d is None else round(d,1)} |")
print("\nFPR on hard negatives by type (groups):")
for k in ("single_account_rules", "graph_heuristic"):
    print(" ", k, {t: round(v, 2) for t, v in res[k]["hard_negative"]["fpr_groups_by_type"].items()})
print("recall by pattern:", {k: {t: round(v, 2) for t, v in res[k]["ring"]["recall_by_pattern"].items()} for k in ("single_account_rules", "graph_heuristic")})
print("wrote", out)
