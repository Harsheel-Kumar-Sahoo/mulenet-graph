"""Train + evaluate the GNN. Needs torch (PyG optional). Datasets: train seed 1, val seed 2, test = default cfg seed 42."""
import argparse, copy, json, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mulenet.config import load_config, ROOT
from mulenet.data.generate import build_dataset
from mulenet.models.dataset import build_samples, fit_scaler
from mulenet.models import gnn
from mulenet.evaluate import replay_scores, first_from_scores, metrics

p = argparse.ArgumentParser(); p.add_argument("--quick", action="store_true"); p.add_argument("--epochs", type=int)
p.add_argument("--force-pure", action="store_true"); a = p.parse_args()
if not gnn.HAS_TORCH:
    sys.exit("torch is not installed: `pip install torch` (PyG optional). Nothing trained.")
import torch, torch.nn as nn
cfg = load_config(); tc = cfg["train"]; torch.manual_seed(cfg["seed"]); np.random.seed(cfg["seed"])

def mk(seed, rings, hns):
    c = copy.deepcopy(cfg); c["data"].update(n_rings=rings, n_hard_negatives=hns)
    if a.quick: c["data"].update(n_accounts=600, n_normal_txns=4000)
    return build_dataset(c, seed)
t0 = time.time()
tr, va = mk(1, 12 if a.quick else tc["n_train_rings"], 20 if a.quick else tc["n_train_hard_negatives"]), mk(2, 6 if a.quick else 20, 10 if a.quick else 40)
te = build_dataset(cfg) if not a.quick else mk(42, 6, 10)
mx = 800 if a.quick else tc["max_normal_events"]
S_tr, S_va = build_samples(tr, cfg, mx, 1), build_samples(va, cfg, mx, 2)
mean, std = fit_scaler(S_tr); print(f"samples train={len(S_tr)} val={len(S_va)} ({time.time()-t0:.0f}s)")
model, backend, kind = gnn.build_model(cfg, force_pure=a.force_pure); print("backend:", backend, kind)
y_all = np.concatenate([s["y"] for s in S_tr]); pw = torch.tensor(min((1 - y_all.mean()) / max(y_all.mean(), 1e-6), 20.0))
lossf, opt = nn.BCEWithLogitsLoss(pos_weight=pw), torch.optim.Adam(model.parameters(), lr=tc["lr"], weight_decay=1e-4)

def vloss():
    model.eval(); tot = 0.0
    with torch.no_grad():
        for i in range(0, len(S_va), 256):
            x, ei, y = gnn.collate(S_va[i:i + 256], mean, std); tot += lossf(model(x, ei), y).item() * len(y)
    return tot / sum(len(s["y"]) for s in S_va)

best, best_state, bs = 1e9, None, tc["batch_size"]
for ep in range(a.epochs or (5 if a.quick else tc["epochs"])):
    model.train(); order = np.random.permutation(len(S_tr))
    for i in range(0, len(order), bs):
        x, ei, y = gnn.collate([S_tr[j] for j in order[i:i + bs]], mean, std)
        opt.zero_grad(); l = lossf(model(x, ei), y); l.backward(); opt.step()
    v = vloss(); print(f"epoch {ep+1} val_loss {v:.4f}")
    if v < best: best, best_state = v, copy.deepcopy(model.state_dict())
model.load_state_dict(best_state)
scorer = gnn.GNNScorer(model, mean, std, cfg)
sv = replay_scores(va, scorer, cfg); thrs = [round(x, 2) for x in np.arange(0.3, 0.96, 0.05)]
cand = []
for th in thrs:
    m = metrics(va, first_from_scores(sv, th)); cand.append((th, m))
ok = [c for c in cand if c[1]["hard_negative"]["fpr_groups"] <= tc["min_hn_fpr_budget"]] or cand
thr = max(ok, key=lambda c: c[1]["node"]["f1"])[0]
print("threshold (chosen on VAL):", thr)
t0 = time.time(); st = replay_scores(te, scorer, cfg); m = metrics(te, first_from_scores(st, thr)); m["replay_seconds"] = round(time.time() - t0, 1)
base = json.loads((ROOT / "docs/baseline_metrics.json").read_text()) if (ROOT / "docs/baseline_metrics.json").exists() else {}
res = {"synthetic": True, "backend": backend, "arch": kind, "threshold": thr, "quick_mode": a.quick, "gnn": m, "baselines": {k: base[k] for k in base if isinstance(base[k], dict) and "node" in base[k]}}
(ROOT / "docs/gnn_metrics.json").write_text(json.dumps(res, indent=1, default=float))
ck = ROOT / cfg["model"]["checkpoint"]; ck.parent.mkdir(exist_ok=True)
gnn.save_checkpoint(ck, model, backend, kind, mean, std, cfg, {"threshold": thr, "synthetic": True})
print("| model | node P | node R | node F1 | FPR hard-neg (groups) | ring recall pre-cashout | median delay s |\n|---|---|---|---|---|---|---|")
for name, r in [("GNN " + kind + "/" + backend, m)] + [(k, v) for k, v in res["baselines"].items()]:
    d = r["ring"]["delay_s_before_cashout_median"]
    print(f"| {name} | {r['node']['precision']:.2f} | {r['node']['recall']:.2f} | {r['node']['f1']:.2f} | {r['hard_negative']['fpr_groups']:.2f} | {r['ring']['recall_before_cashout']:.2f} | {'-' if d is None else round(d,1)} |")
print("SYNTHETIC DATA; checkpoint:", ck)
