"""Bounded k-hop (undirected) neighbourhood extraction, newest edges first."""
from itertools import chain


def k_hop_nodes(g, seeds, k: int, max_nodes: int) -> set:
    seen = {s for s in seeds if s in g}
    frontier = list(seen)
    for _ in range(k):
        nxt = []
        for u in frontier:
            for v in chain(reversed(list(g.succ[u])), reversed(list(g.pred[u]))):
                if v not in seen:
                    if len(seen) >= max_nodes:
                        return seen
                    seen.add(v); nxt.append(v)
        frontier = nxt
    return seen


def k_hop_subgraph(g, seeds, k: int, max_nodes: int):
    """Read-only subgraph view around `seeds`."""
    return g.subgraph(k_hop_nodes(g, seeds, k, max_nodes))
