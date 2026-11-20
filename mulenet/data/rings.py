"""Mule-ring injector: fan_out, fan_in, circular. Reusable for live attacks (Phase 4)."""
import numpy as np
from .schema import Txn


def pick(rng, pool, k, exclude=()):
    ex = set(exclude)
    cand = [p for p in pool if p not in ex]
    if len(cand) < k:
        raise ValueError(f"account pool too small: need {k}, have {len(cand)}")
    return [cand[i] for i in rng.choice(len(cand), size=k, replace=False)]


def _layers(size, depth):
    """Split `size` mules into `depth` layers, first layer = 1 account."""
    size = max(size, 3); depth = min(max(depth, 2), size)
    layers, rem = [1], size - 1
    for i in range(1, depth):
        left = depth - i
        take = rem if left == 1 else min(max(1, rem // 2), rem - (left - 1))
        layers.append(take); rem -= take
    return layers


def _chunk(items, sizes):
    out, i = [], 0
    for n in sizes:
        out.append(items[i:i + n]); i += n
    return out


def inject_ring(cfg, rng, peers, merchants, start_ts, ring_id, exclude=(), **ov):
    """Return (txns, ring_meta). Overrides: pattern,size,depth,hop_gap,split_ratio.
    split_ratio is used by fan_out only (documented limitation)."""
    rc = cfg["data"]["mule_ring"]
    ri = lambda r: int(rng.integers(r[0], r[1] + 1))
    ru = lambda r: float(rng.uniform(r[0], r[1]))
    pattern = ov.get("pattern") or str(rng.choice(rc["patterns"]))
    size = ov.get("size") or ri(rc["size"])
    depth = ov.get("depth") or ri(rc["depth"])
    gap_lo, gap_hi = ov.get("hop_gap") or rc["hop_gap_seconds"]
    split = ov.get("split_ratio") or ru(rc["split_ratio"])
    skim, total, n_camo = ru(rc["skim"]), ru(rc["amount"]), ri(rc["camouflage_txns"])
    size = max(size, 3); depth = min(max(depth, 2), size)
    gid, kind = f"ring{ring_id}", f"mule_{pattern}"
    cash = f"C{ring_id:03d}"
    mules = pick(rng, peers, size, exclude)
    txns = []

    def emit(s, d, a, t, k=kind, label=1, scn="ring"):
        txns.append(Txn(0, round(float(t), 3), s, d, round(float(a), 2), k, label, gid, scn))

    jit = lambda: float(rng.uniform(0, 0.8 * gap_lo))     # < gap_lo keeps hops causal
    hop = lambda t: t + float(rng.uniform(gap_lo, gap_hi))
    t, amt, cash_ts = start_ts, {}, []

    if pattern == "fan_out":
        layers = _chunk(mules, sorted(_layers(size, depth)))  # tree widens
        victims = pick(rng, peers, ri((1, 3)), set(mules) | set(exclude))
        for v in victims:
            emit(v, layers[0][0], total / len(victims), t + jit(), "mule_inflow")
        amt[layers[0][0]] = total
        for li in range(1, len(layers)):
            t = hop(t)
            kids = {p: [] for p in layers[li - 1]}
            for j, c in enumerate(layers[li]):
                kids[layers[li - 1][j % len(layers[li - 1])]].append(c)
            for p, cs in kids.items():
                if not cs:
                    continue
                out = amt[p] * (1 - skim)
                shares = [out] if len(cs) == 1 else [split * out] + [(1 - split) * out / (len(cs) - 1)] * (len(cs) - 1)
                for c, a in zip(cs, shares):
                    amt[c] = a; emit(p, c, a, t + jit())
        t = hop(t)
        for c in layers[-1]:
            tt = t + jit(); cash_ts.append(tt); emit(c, cash, amt[c] * (1 - skim), tt)
    elif pattern == "fan_in":
        layers = _chunk(mules, sorted(_layers(size, depth), reverse=True))  # funnel narrows
        victims = pick(rng, peers, len(layers[0]), set(mules) | set(exclude))
        for v, m in zip(victims, layers[0]):
            amt[m] = total / len(victims); emit(v, m, amt[m], t + jit(), "mule_inflow")
        for li in range(1, len(layers)):
            t = hop(t); nxt = layers[li]
            for j, m in enumerate(layers[li - 1]):
                if amt.get(m, 0) <= 0:
                    continue
                p = nxt[j % len(nxt)]; a = amt[m] * (1 - skim)
                amt[p] = amt.get(p, 0) + a; emit(m, p, a, t + jit())
        t = hop(t); collector = layers[-1][0]; tt = t + jit(); cash_ts.append(tt)
        emit(collector, cash, amt[collector] * (1 - skim), tt)
    elif pattern == "circular":
        victims = pick(rng, peers, 1, set(mules) | set(exclude))
        a = total; emit(victims[0], mules[0], a, t + jit(), "mule_inflow")
        path = mules * max(1, depth - 1) + [mules[0]]        # closes the cycle
        for s, d in zip(path[:-1], path[1:]):
            t = hop(t); a *= (1 - skim); emit(s, d, a, t + jit())
        t = hop(t); tt = t + jit(); cash_ts.append(tt); emit(mules[0], cash, a * (1 - skim), tt)
    else:
        raise ValueError(f"unknown pattern {pattern}")

    end = max(x.ts for x in txns)
    for m in mules:                                          # benign-looking noise
        for _ in range(n_camo):
            emit(m, merchants[int(rng.integers(len(merchants)))], float(rng.uniform(20, 800)),
                 rng.uniform(start_ts, end + 60), "camouflage", 0, "ring_camouflage")
    meta = {"ring_id": gid, "pattern": pattern, "mules": mules, "victims": victims, "cashout": cash,
            "start_ts": float(start_ts), "cashout_ts": round(min(cash_ts), 3), "end_ts": end,
            "params": {"size": size, "depth": depth, "hop_gap": [gap_lo, gap_hi], "split_ratio": round(split, 3),
                       "skim": round(skim, 3), "total": round(total, 2), "camouflage": n_camo}}
    return txns, meta
