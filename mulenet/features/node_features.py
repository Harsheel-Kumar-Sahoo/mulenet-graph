"""Velocity / structure features from the rolling window graph."""
import math
from statistics import median

FEATURE_NAMES = ["in_deg", "out_deg", "in_cnt", "out_cnt", "log_in_amt", "log_out_amt", "fwd_ratio",
                 "min_gap_norm", "med_gap_norm", "in_cycle", "log_max_in", "recent_out_60", "passthrough"]
SUBGRAPH_FEATURE_NAMES = ["n_nodes", "n_edges", "density", "max_in_deg", "max_out_deg"]


def on_cycle(g, n, max_len=5, budget=200) -> bool:
    """True if n lies on a directed cycle of length 3..max_len (bounded BFS)."""
    seen, frontier = {n}, [n]
    for d in range(max_len):
        nxt = []
        for u in frontier:
            for v in g.succ[u]:
                if v == n and d >= 2:
                    return True
                if v not in seen:
                    seen.add(v); nxt.append(v)
        if len(seen) > budget:
            return False
        frontier = nxt
    return False


def node_features(g, n, now, window, cycle_len=5) -> dict:
    ins = sorted(x for u in g.pred[n] for x in g[u][n]["tx"])
    outs = sorted(x for v in g.succ[n] for x in g[n][v]["tx"])
    in_amt, out_amt = sum(a for _, a in ins), sum(a for _, a in outs)
    fwd = min(out_amt / in_amt, 1.5) if in_amt > 0 else 0.0
    gaps = []
    for ts, _ in outs:                      # delay since most recent earlier receipt
        prev = [t for t, _ in ins if t <= ts]
        if prev:
            gaps.append(ts - prev[-1])
    mn = min(gaps) if gaps else window
    md = median(gaps) if gaps else window
    cyc = float(bool(ins and outs) and on_cycle(g, n, cycle_len))
    return {"in_deg": len(g.pred[n]), "out_deg": len(g.succ[n]), "in_cnt": len(ins), "out_cnt": len(outs),
            "log_in_amt": math.log1p(in_amt), "log_out_amt": math.log1p(out_amt), "fwd_ratio": fwd,
            "min_gap_norm": mn / window, "med_gap_norm": md / window, "in_cycle": cyc,
            "log_max_in": math.log1p(max((a for _, a in ins), default=0.0)),
            "recent_out_60": sum(1 for ts, _ in outs if ts >= now - 60),
            "passthrough": float(in_amt > 0 and out_amt > 0 and fwd >= 0.8),
            # raw values for rules
            "_in_amt": in_amt, "_min_gap": mn, "_max_in": max((a for _, a in ins), default=0.0)}


def feature_vector(f: dict) -> list:
    return [float(f[k]) for k in FEATURE_NAMES]


def subgraph_features(sub) -> dict:
    n, e = sub.number_of_nodes(), sub.number_of_edges()
    return {"n_nodes": n, "n_edges": e, "density": e / (n * (n - 1)) if n > 1 else 0.0,
            "max_in_deg": max((d for _, d in sub.in_degree()), default=0),
            "max_out_deg": max((d for _, d in sub.out_degree()), default=0)}
