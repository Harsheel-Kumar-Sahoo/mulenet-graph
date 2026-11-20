"""Sub-graph samples for the GNN (numpy only; torch/PyG conversion lives in gnn.py)."""
import numpy as np
from ..graph.window import RollingGraph
from ..graph.subgraph import k_hop_nodes
from ..features.node_features import node_features, feature_vector, FEATURE_NAMES

_COUNT = [FEATURE_NAMES.index(n) for n in ("in_deg", "out_deg", "in_cnt", "out_cnt", "recent_out_60")]


def build_sample(g, seeds, now, cfg, labels=None) -> dict:
    """Bounded k-hop sub-graph around `seeds` (seeds first). Shared by training and live scoring."""
    seeds = [s for s in dict.fromkeys(seeds) if s in g]
    sub = k_hop_nodes(g, seeds, cfg["graph"]["k_hops"], cfg["graph"]["max_subgraph_nodes"])
    order = seeds + [n for n in sub if n not in set(seeds)]
    idx = {n: i for i, n in enumerate(order)}
    w = cfg["graph"]["window_seconds"]
    x = np.array([feature_vector(node_features(g, n, now, w)) for n in order], dtype=np.float32)
    x[:, _COUNT] = np.log1p(x[:, _COUNT])
    src, dst = [], []
    for u in order:
        for v in g.succ[u]:
            if v in idx:
                src.append(idx[u]); dst.append(idx[v])
    s = {"x": x, "edge_index": np.array([src, dst], dtype=np.int64).reshape(2, -1), "nodes": order,
         "n_seed": len(seeds), "ts": float(now)}
    if labels is not None:
        s["y"] = np.array([labels.get(n, 0) for n in order], dtype=np.float32)
    return s


def build_samples(ds, cfg, max_normal=4000, seed=0) -> list:
    """Replay the stream; keep every ring/hard-negative/camouflage event + a random subset of normal events."""
    rng = np.random.default_rng(seed)
    labels = {a: v["label"] for a, v in ds.accounts.items()}
    normal = [i for i, t in enumerate(ds.txns) if not t.group_id]
    keep = set(rng.choice(normal, size=min(max_normal, len(normal)), replace=False).tolist())
    rg, out = RollingGraph(cfg["graph"]["window_seconds"]), []
    for i, t in enumerate(ds.txns):
        rg.add(t)
        if t.group_id or i in keep:
            out.append(build_sample(rg.g, (t.src, t.dst), t.ts, cfg, labels))
    return out


def fit_scaler(samples):
    x = np.concatenate([s["x"] for s in samples])
    return x.mean(0), np.maximum(x.std(0), 1e-6)


def to_pyg_data(sample, mean=None, std=None):
    """Optional: torch_geometric Data object (requires torch + PyG)."""
    import torch
    from torch_geometric.data import Data
    x = sample["x"] if mean is None else (sample["x"] - mean) / std
    return Data(x=torch.from_numpy(x), edge_index=torch.from_numpy(sample["edge_index"]),
                y=torch.from_numpy(sample["y"]) if "y" in sample else None)
