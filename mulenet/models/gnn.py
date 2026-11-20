"""Direction-aware GraphSAGE / GAT node classifier. PyG backend if installed, else pure PyTorch (SAGE only).
Checkpoints are backend-specific (state-dict keys differ)."""
import numpy as np
from ..features.node_features import FEATURE_NAMES
from .dataset import build_sample
from ..graph.subgraph import k_hop_nodes  # noqa: F401

try:
    import torch, torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
try:
    from torch_geometric.nn import SAGEConv, GATConv
    HAS_PYG = HAS_TORCH
except Exception:
    HAS_PYG = False

if HAS_TORCH:
    class DirLayerPure(nn.Module):
        """h = W_s x + W_in mean(in-neighbours) + W_out mean(out-neighbours)."""
        def __init__(s, i, o):
            super().__init__(); s.ws = nn.Linear(i, o); s.win = nn.Linear(i, o, bias=False); s.wout = nn.Linear(i, o, bias=False)

        @staticmethod
        def _mean(x, frm, to):
            agg = torch.zeros_like(x).index_add_(0, to, x[frm])
            deg = torch.zeros(x.size(0), device=x.device).index_add_(0, to, torch.ones(to.size(0), device=x.device))
            return agg / deg.clamp(min=1).unsqueeze(1)

        def forward(s, x, ei):
            return s.ws(x) + s.win(s._mean(x, ei[0], ei[1])) + s.wout(s._mean(x, ei[1], ei[0]))

    class DirLayerPyG(nn.Module):
        def __init__(s, i, o, kind="graphsage", heads=2):
            super().__init__(); s.lin = nn.Linear(i, o)
            mk = (lambda: GATConv(i, o // heads, heads=heads)) if kind == "gat" else (lambda: SAGEConv(i, o))
            s.cin, s.cout = mk(), mk()

        def forward(s, x, ei):
            return s.lin(x) + s.cin(x, ei) + s.cout(x, ei.flip(0))

    class MuleGNN(nn.Module):
        def __init__(s, in_dim, hidden=32, kind="graphsage", backend="pure", dropout=0.1):
            super().__init__()
            L = (lambda i, o: DirLayerPyG(i, o, kind)) if backend == "pyg" else DirLayerPure
            s.l1, s.l2, s.drop = L(in_dim, hidden), L(hidden, hidden), nn.Dropout(dropout)
            s.head = nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, 1))

        def forward(s, x, ei):
            h = s.drop(torch.relu(s.l1(x, ei))); h = torch.relu(s.l2(h, ei))
            return s.head(h).squeeze(-1)          # per-node logit

    def build_model(cfg, in_dim=len(FEATURE_NAMES), force_pure=False):
        m = cfg["model"]; use_pyg = HAS_PYG and m.get("prefer_pyg", True) and not force_pure
        kind = m["arch"] if use_pyg else "graphsage"      # GAT needs PyG; fallback is SAGE
        backend = "pyg" if use_pyg else "pure"
        return MuleGNN(in_dim, m["hidden_dim"], kind, backend), backend, kind

    def collate(samples, mean=None, std=None):
        xs, eis, ys, off = [], [], [], 0
        for s in samples:
            x = s["x"] if mean is None else (s["x"] - mean) / std
            xs.append(x); eis.append(s["edge_index"] + off); off += len(x)
            ys.append(s.get("y", np.zeros(len(x), np.float32)))
        return (torch.from_numpy(np.concatenate(xs).astype(np.float32)),
                torch.from_numpy(np.concatenate(eis, axis=1)).long(),
                torch.from_numpy(np.concatenate(ys).astype(np.float32)))

    def save_checkpoint(path, model, backend, kind, mean, std, cfg, extra=None):
        torch.save({"state": model.state_dict(), "backend": backend, "kind": kind, "mean": mean, "std": std,
                    "hidden": cfg["model"]["hidden_dim"], "features": FEATURE_NAMES, "extra": extra or {}}, path)

    def load_checkpoint(path, cfg):
        ck = torch.load(path, map_location="cpu", weights_only=False)
        if ck["backend"] == "pyg" and not HAS_PYG:
            raise RuntimeError("checkpoint was trained with PyG; install torch_geometric or retrain with the fallback")
        c = {**cfg, "model": {**cfg["model"], "hidden_dim": ck["hidden"], "arch": ck["kind"], "prefer_pyg": ck["backend"] == "pyg"}}
        model, backend, _ = build_model(c); model.load_state_dict(ck["state"]); model.eval()
        return model, ck

    class GNNScorer:
        """scorer(g, nodes, now) -> {node: probability}; same interface as the baselines."""
        def __init__(self, model, mean, std, cfg):
            self.model, self.mean, self.std, self.cfg = model.eval(), mean, std, cfg

        @torch.no_grad()
        def __call__(self, g, nodes, now):
            s = build_sample(g, nodes, now, self.cfg)
            if s["n_seed"] == 0:
                return {}
            x, ei, _ = collate([s], self.mean, self.std)
            p = torch.sigmoid(self.model(x, ei))[: s["n_seed"]].tolist()
            return dict(zip(s["nodes"][: s["n_seed"]], p))
