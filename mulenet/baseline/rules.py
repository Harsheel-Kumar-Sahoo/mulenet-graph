"""Baselines. RuleBaseline = single-account rules; GraphHeuristic = simple graph rules.
Both return score 1.0 if any rule fires else 0.0 (same scorer interface the GNN will use)."""
from ..features.node_features import node_features


class _Base:
    def __init__(self, cfg):
        self.c, self.window = cfg["baseline"], cfg["graph"]["window_seconds"]
        self.k = cfg["graph"]["k_hops"]; self.max_nodes = cfg["graph"]["max_subgraph_nodes"]

    def f(self, g, n, now):
        return node_features(g, n, now, self.window)

    def fired(self, g, n, now) -> list:
        raise NotImplementedError

    def __call__(self, g, nodes, now) -> dict:
        return {n: (1.0 if self.fired(g, n, now) else 0.0) for n in nodes if n in g}


class RuleBaseline(_Base):
    name = "single_account_rules"

    def fired(self, g, n, now):
        c, f, out = self.c, self.f(g, n, now), []
        if f["_in_amt"] >= c["rule_amount"] and f["fwd_ratio"] >= c["rule_fwd_ratio"] and f["_min_gap"] <= c["rule_gap_s"]:
            out.append("R1_fast_pass_through_large")
        if f["out_deg"] >= c["rule_fanout"]:
            out.append("R2_high_fan_out")
        if f["in_deg"] >= c["rule_fanin"] and f["fwd_ratio"] >= c["rule_fwd_ratio"] and f["out_cnt"] >= 1:
            out.append("R3_collector_forwarding")
        return out


class GraphHeuristic(_Base):
    name = "graph_heuristic"

    def _pt(self, g, n, now, gap):
        f = self.f(g, n, now)
        return f, f["passthrough"] and f["_min_gap"] <= gap

    def fired(self, g, n, now):
        f, pt60 = self._pt(g, n, now, 60)
        out = []
        if f["in_cycle"] and f["passthrough"] and f["_min_gap"] <= 120:
            out.append("H1_fast_cycle")
        if pt60:
            nb = (list(g.succ[n]) + list(g.pred[n]))[:10]
            if any(self._pt(g, m, now, 60)[1] for m in nb):
                out.append("H2_pass_through_chain")
        if f["out_deg"] >= 5 and f["_max_in"] >= self.c["rule_amount"] and f["_min_gap"] <= 60:
            out.append("H3_fast_fan_out_entry")
        return out


class GradedHeuristic(GraphHeuristic):
    """GraphHeuristic with a graded score so the policy has levels (0.35 weak signal, 0.65 one rule, 0.9 two+ rules).
    Fallback scorer for demos when no trained GNN is available. NOT a GNN."""
    name = "graded_heuristic"

    def reasons(self, g, n, now):
        return self.fired(g, n, now)

    def __call__(self, g, nodes, now):
        out = {}
        for n in nodes:
            if n not in g:
                continue
            r = self.fired(g, n, now)
            if len(r) >= 2: out[n] = 0.9
            elif r: out[n] = 0.65
            else:
                f = self.f(g, n, now); out[n] = 0.35 if (f["passthrough"] and f["_min_gap"] <= 120) else 0.0
        return out
