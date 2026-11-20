"""Pick the scorer: trained GNN if torch + checkpoint exist, else the graded heuristic (clearly labelled)."""
from pathlib import Path
from .config import ROOT
from .baseline.rules import GradedHeuristic


def select_scorer(cfg):
    ck = ROOT / cfg["model"]["checkpoint"]
    try:
        from .models import gnn
        if gnn.HAS_TORCH and ck.exists():
            model, c = gnn.load_checkpoint(ck, cfg)
            return gnn.GNNScorer(model, c["mean"], c["std"], cfg), f"gnn-{c['kind']}-{c['backend']}"
    except Exception as e:                                   # fall back, never crash the demo
        print("GNN scorer unavailable, using fallback:", repr(e))
    return GradedHeuristic(cfg), "graded-heuristic (fallback, NOT a GNN)"
