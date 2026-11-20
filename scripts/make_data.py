"""Generate synthetic dataset. `--sample` writes a small one to data/sample/."""
import argparse, copy, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mulenet.config import load_config, ROOT
from mulenet.data.generate import build_dataset

p = argparse.ArgumentParser()
p.add_argument("--sample", action="store_true"); p.add_argument("--out"); p.add_argument("--seed", type=int)
a = p.parse_args()
cfg = copy.deepcopy(load_config())
if a.sample:
    cfg["data"].update(n_accounts=300, n_merchants=20, n_normal_txns=2500, n_rings=6, n_hard_negatives=10)
out = Path(a.out) if a.out else ROOT / "data" / ("sample" if a.sample else "generated")
ds = build_dataset(cfg, a.seed); ds.save(out)
print(f"wrote {out}  (SYNTHETIC)"); print(json.dumps(ds.summary(), indent=1))
