"""Per-alert explanation. Model-agnostic: (1) rules that fired (heuristic scorer), (2) the node's window features,
(3) edge-removal deltas: drop one incident edge from the sub-graph, re-score, report the score change.
Edge-removal is a perturbation probe on THIS scorer, not a causal proof. SYNTHETIC DATA."""
from ..features.node_features import node_features, FEATURE_NAMES
from ..graph.subgraph import k_hop_subgraph

REASON_TEXT = {
    "H1_fast_cycle": "Funds leave soon after arriving and the account sits on a short directed cycle.",
    "H2_pass_through_chain": "Pass-through account (forwards most of what it receives, fast) next to another pass-through account.",
    "H3_fast_fan_out_entry": "Large inbound amount followed by quick fan-out to 5+ accounts.",
    "model_score": "Score came from the trained model; no named rule (see edge probe below).",
}
FEATURE_NOTE = {
    "fwd_ratio": "share of received money sent onward (1.0 = pass-through)", "min_gap_norm": "fastest receive-to-send gap / window",
    "in_cycle": "on a short directed cycle", "passthrough": "forwards >= 80% of inflow", "out_deg": "distinct recipients",
    "in_deg": "distinct senders", "recent_out_60": "outgoing txns in last 60 s",
}


def _edge_rows(h, node, now, scorer, base, limit):
    inc = [(u, v) for u, v in h.edges if u == node or v == node]
    inc.sort(key=lambda e: -max(t for t, _ in h[e[0]][e[1]]["tx"]))
    rows = []
    for u, v in inc[:limit]:
        data = h[u][v]; h2 = h.copy(); h2.remove_edge(u, v)
        new = scorer(h2, [node], now).get(node, 0.0)
        rows.append({"src": u, "dst": v, "count": len(data["tx"]), "amount": round(sum(a for _, a in data["tx"]), 2),
                     "last_ts": round(max(t for t, _ in data["tx"]), 1), "score_without": round(new, 3), "delta": round(base - new, 3)})
    rows.sort(key=lambda r: -r["delta"])
    return rows


def explain_node(rt, node, top_edges=6, max_probe_edges=20):
    g, now, cfg = rt.rg.g, rt.sim.now, rt.cfg
    rec = rt.decision.record(node)
    out = {"synthetic": True, "node": node, "state": rec["state"], "stored_score": round(rec["score"], 3), "peak_score": round(rec.get("peak", 0.0), 3),
           "scorer": rt.scorer_name, "method": "rules fired + window features + edge-removal probe",
           "caveat": "Risk node for human review, not an accusation. Synthetic data; explanation = what drives THIS scorer's score."}
    if node not in g:
        return {**out, "in_window": False, "reasons": [], "features": [], "edges": [],
                "note": "Node has no edges in the rolling window now (activity expired); score shown is the stored one."}
    sub = k_hop_subgraph(g, [node], cfg["graph"]["k_hops"], cfg["graph"]["max_subgraph_nodes"])
    h = sub.copy()
    base = rt.scorer(h, [node], now).get(node, 0.0)
    rs = getattr(rt.scorer, "reasons", None)
    names = list(rs(h, node, now)) if rs else []
    if not names and rs is None: names = ["model_score"]
    f = node_features(g, node, now, cfg["graph"]["window_seconds"], cfg["graph"].get("cycle_len", 5)) if "cycle_len" in cfg["graph"] else node_features(g, node, now, cfg["graph"]["window_seconds"])
    feats = [{"name": k, "value": round(float(f[k]), 3), "note": FEATURE_NOTE.get(k, "")} for k in FEATURE_NAMES]
    feats.sort(key=lambda r: (r["name"] not in FEATURE_NOTE, -abs(r["value"])))
    return {**out, "in_window": True, "current_score": round(base, 3), "subgraph_nodes": h.number_of_nodes(), "subgraph_edges": h.number_of_edges(),
            "reasons": [{"name": n, "text": REASON_TEXT.get(n, n)} for n in names], "features": feats[:8],
            "edges": _edge_rows(h, node, now, rt.scorer, base, max_probe_edges)[:top_edges]}
