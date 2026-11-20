"""Per-event latency: sub-graph extraction+features, and (if torch + checkpoint) GNN inference. Report p50/p95/p99.
Batch size 1, single process, in-memory 600 s window, replay of the default synthetic test stream."""
import argparse, json, platform, os, sys, time, subprocess
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mulenet.config import load_config, ROOT
from mulenet.data.generate import build_dataset
from mulenet.graph.window import RollingGraph
from mulenet.models.dataset import build_sample

p = argparse.ArgumentParser(); p.add_argument("--events", type=int, default=3000); p.add_argument("--no-model", action="store_true")
a = p.parse_args(); cfg = load_config(); ds = build_dataset(cfg)
model = None
if not a.no_model:
    try:
        from mulenet.models import gnn
        import torch
        torch.set_num_threads(1)
        model, ck = gnn.load_checkpoint(ROOT / cfg["model"]["checkpoint"], cfg)
        mean, std = ck["mean"], ck["std"]
    except Exception as e:
        print("model inference skipped:", repr(e))
rg, feat, inf, nodes, edges = RollingGraph(cfg["graph"]["window_seconds"]), [], [], [], []
warm = len(ds.txns) // 2
for i, t in enumerate(ds.txns):
    rg.add(t)
    if i < warm or len(feat) >= a.events:
        if len(feat) >= a.events: break
        continue
    t0 = time.perf_counter(); s = build_sample(rg.g, (t.src, t.dst), t.ts, cfg); t1 = time.perf_counter()
    feat.append((t1 - t0) * 1e3); nodes.append(len(s["x"])); edges.append(rg.g.number_of_edges())
    if model is not None:
        with torch.no_grad():
            x, ei, _ = gnn.collate([s], mean, std); t2 = time.perf_counter(); torch.sigmoid(model(x, ei)); inf.append((time.perf_counter() - t2) * 1e3)
pc = lambda v: {f"p{q}": round(float(np.percentile(v, q)), 2) for q in (50, 95, 99)}
try: cpu = [l for l in subprocess.check_output(["lscpu"], text=True).splitlines() if "Model name" in l][0].split(":")[1].strip()
except Exception: cpu = platform.processor()
out = {"synthetic": True, "events_timed": len(feat), "cpu": cpu, "cpu_count": os.cpu_count(), "platform": platform.platform(),
       "python": platform.python_version(), "window_s": cfg["graph"]["window_seconds"], "avg_edges_in_window": int(np.mean(edges)),
       "avg_subgraph_nodes": round(float(np.mean(nodes)), 1), "extract_features_ms": pc(feat),
       "gnn_inference_ms": pc(inf) if inf else "NOT MEASURED (torch/checkpoint unavailable)",
       "total_ms": pc(np.array(feat) + np.array(inf)) if inf else "NOT MEASURED",
       "caveat": "Simulated load, batch size 1, one process; not a production throughput claim."}
(ROOT / "docs/latency_report.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
