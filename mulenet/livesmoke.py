"""Headless live-simulation run (no FastAPI needed): used by scripts/demo.py and scripts/gen_report.py. SYNTHETIC."""
import copy
from .runtime import Runtime


def run_live(cfg, seed=7, warmup=300, attacks=(), after=300, scorer=None, scorer_name=None, step=1.0):
    rt = Runtime(copy.deepcopy(cfg), scorer=scorer, scorer_name=scorer_name, seed=seed)
    def go(sec):
        for _ in range(int(sec / step)):
            for t in rt.sim.advance(step): rt.handle_txn(t)
    go(warmup)
    for a in attacks: rt.launch_attack(**a); go(20)
    go(after)
    return rt
