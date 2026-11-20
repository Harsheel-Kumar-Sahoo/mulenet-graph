"""Replay a Dataset through a scorer; node/ring-level metrics, FPR on hard negatives, detection delay."""
from collections import defaultdict
from statistics import mean, median
from .graph.window import RollingGraph


def replay(ds, scorer, cfg, threshold=0.5) -> dict:
    """Returns {node: first_flag_ts}. scorer(g, nodes, now) -> {node: score}; nodes = endpoints of each txn."""
    rg, first = RollingGraph(cfg["graph"]["window_seconds"]), {}
    for t in ds.txns:
        rg.add(t)
        for n, s in scorer(rg.g, (t.src, t.dst), t.ts).items():
            if s >= threshold and n not in first:
                first[n] = t.ts
    return first


def metrics(ds, first: dict) -> dict:
    nodes = {n for t in ds.txns for n in (t.src, t.dst)}
    lab = {n: ds.accounts[n]["label"] for n in nodes}
    flagged = set(first)
    tp = sum(1 for n in nodes if lab[n] and n in flagged); fp = sum(1 for n in nodes if not lab[n] and n in flagged)
    fn = sum(1 for n in nodes if lab[n] and n not in flagged); tn = len(nodes) - tp - fp - fn
    pr = tp / (tp + fp) if tp + fp else 0.0; rc = tp / (tp + fn) if tp + fn else 0.0
    out = {"node": {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": pr, "recall": rc,
                    "f1": 2 * pr * rc / (pr + rc) if pr + rc else 0.0, "fpr_all_nonmule": fp / (fp + tn) if fp + tn else 0.0}}
    # hard negatives
    hn_nodes, by_type, grp = set(), defaultdict(lambda: [0, 0]), [0, 0]
    for h in ds.hard_negatives:
        mem = set(h["members"]) | {h["center"]}; hn_nodes |= mem
        hit = bool(mem & flagged); grp[0] += hit; grp[1] += 1
        by_type[h["type"]][0] += hit; by_type[h["type"]][1] += 1
    out["hard_negative"] = {
        "fpr_nodes": len(hn_nodes & flagged) / len(hn_nodes) if hn_nodes else 0.0,
        "fpr_groups": grp[0] / grp[1] if grp[1] else 0.0,
        "fpr_groups_by_type": {k: v[0] / v[1] for k, v in by_type.items()}}
    # rings
    det, delays, late, by_pat = 0, [], 0, defaultdict(lambda: [0, 0])
    for r in ds.rings:
        ts = [first[m] for m in r["mules"] if m in first]
        by_pat[r["pattern"]][1] += 1
        if ts and min(ts) <= r["cashout_ts"]:
            det += 1; by_pat[r["pattern"]][0] += 1; delays.append(r["cashout_ts"] - min(ts))
        elif ts:
            late += 1
    n = len(ds.rings)
    out["ring"] = {"n_rings": n, "recall_before_cashout": det / n if n else 0.0, "detected_only_after_cashout": late,
                   "delay_s_before_cashout_mean": mean(delays) if delays else None,
                   "delay_s_before_cashout_median": median(delays) if delays else None,
                   "recall_by_pattern": {k: v[0] / v[1] for k, v in by_pat.items()}}
    return out


def evaluate(ds, scorer, cfg, threshold=0.5) -> dict:
    return metrics(ds, replay(ds, scorer, cfg, threshold))


def replay_scores(ds, scorer, cfg) -> dict:
    """One replay recording every score: {node: [(ts, score), ...]}. Lets us sweep thresholds cheaply."""
    rg, out = RollingGraph(cfg["graph"]["window_seconds"]), defaultdict(list)
    for t in ds.txns:
        rg.add(t)
        for n, s in scorer(rg.g, (t.src, t.dst), t.ts).items():
            out[n].append((t.ts, s))
    return out


def first_from_scores(scores: dict, thr: float) -> dict:
    first = {}
    for n, lst in scores.items():
        for ts, s in lst:
            if s >= thr:
                first[n] = ts; break
    return first
