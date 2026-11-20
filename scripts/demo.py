"""End-to-end headless demo (no FastAPI/npm needed): normal traffic -> 3 injected rings -> detection timeline -> explanation.
SYNTHETIC DATA. Usage: python3 scripts/demo.py [--seed 7]"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mulenet.config import load_config
from mulenet.livesmoke import run_live
from mulenet.explain.explain import explain_node

ap = argparse.ArgumentParser(); ap.add_argument("--seed", type=int, default=7); a = ap.parse_args()
cfg = load_config()
print("MuleNet-Graph demo | SIMULATED DATA ONLY | not production-ready\n")
rt = run_live(cfg, seed=a.seed, warmup=300, after=200, attacks=[dict(pattern=p) for p in ("fan_out", "fan_in", "circular")])
print("scorer:", rt.scorer_name)
for r in rt.metrics()["attacks"]:
    print(f"- {r['pattern']:9s} flag {r['secs_to_flag']}s hold {r['secs_to_hold']}s | mules by state {r['mules_by_state']} | "
          f"stopped mid-chain: {r['interrupted']} | cash-out reached: {r['cashout_reached']} | blocked INR {r['amount_blocked']}")
m = rt.metrics()
print(f"\nFALSE ALARMS on legitimate accounts: flagged {m['false_alarm_nodes'].get('flagged',0)}, held {m['false_alarm_nodes'].get('held',0)}, "
      f"frozen {m['false_alarm_nodes'].get('frozen',0)}; legit transfers blocked {m['blocked_legit']}; legit scenarios harmed {m['legit_groups_harmed']}")
print(f"scoring ms p50/p95/p99 = {m['scoring_ms']['p50']}/{m['scoring_ms']['p95']}/{m['scoring_ms']['p99']} (simulated load, 1 process)")
atk = list(rt.attacks.values())[0]; node = next((n for n in atk["mules"] if rt.decision.state_of(n) != "normal"), atk["mules"][0])
e = explain_node(rt, node); print(f"\nExplanation for {node} (state {e['state']}, score {e['stored_score']}):")
for r in e["reasons"]: print("  reason:", r["name"], "-", r["text"])
for x in e["edges"][:3]: print(f"  edge {x['src']}->{x['dst']} x{x['count']} drops score by {x['delta']} if removed")
print("\nFor the live UI: make serve  (and  make ui  in a second terminal).")
