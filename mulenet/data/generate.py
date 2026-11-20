"""Assemble normal traffic + rings + hard negatives into a labelled Dataset."""
import numpy as np
from .normal import generate_normal
from .rings import inject_ring
from .hard_negatives import make_hard_negative
from .schema import Dataset


def build_dataset(cfg, seed=None) -> Dataset:
    d = cfg["data"]; seed = cfg.get("seed", 0) if seed is None else seed
    rng = np.random.default_rng(seed); H = float(d["horizon_seconds"])
    accounts, txns, peers, merchants = generate_normal(cfg, rng)
    mule_set, rings, hns = set(), [], []
    pats = d["mule_ring"]["patterns"]
    for i in range(int(d["n_rings"])):            # round-robin patterns => full coverage
        rt, meta = inject_ring(cfg, rng, peers, merchants, rng.uniform(0.05 * H, 0.7 * H), i,
                               exclude=mule_set, pattern=pats[i % len(pats)])
        txns += rt; rings.append(meta); mule_set |= set(meta["mules"])
        for m in meta["mules"]:
            accounts[m].update(label=1, ring_id=meta["ring_id"])
        accounts[meta["cashout"]] = {"type": "cashout", "label": 1, "ring_id": meta["ring_id"]}
    types = d["hard_negative_types"]
    for i in range(int(d["n_hard_negatives"])):
        ht, meta, new_acc = make_hard_negative(cfg, rng, peers, merchants, rng.uniform(0.05 * H, 0.7 * H),
                                               i, types[i % len(types)], exclude=mule_set)
        txns += ht; hns.append(meta); accounts.update(new_acc)
        accounts[meta["center"]].update(hardneg_id=meta["hn_id"], hardneg_type=meta["type"])
    meta = {"seed": seed, "synthetic": True, "horizon_seconds": H,
            "note": "SYNTHETIC DATA ONLY; ring structures are author-defined."}
    return Dataset(txns, accounts, rings, hns, meta).finalize()
