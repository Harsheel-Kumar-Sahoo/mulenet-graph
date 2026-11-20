"""Hard negatives: legitimate patterns that resemble mule structures. All label 0."""
import numpy as np
from .schema import Txn
from .rings import pick

HN_TYPES = ["shopkeeper", "group_split", "rent", "salary", "friend_settle"]


def make_hard_negative(cfg, rng, peers, merchants, start_ts, hn_id, kind, exclude=()):
    """Return (txns, meta, new_accounts)."""
    ri = lambda a, b: int(rng.integers(a, b + 1))
    ru = lambda a, b: float(rng.uniform(a, b))
    gid, scn, k = f"hn{hn_id}", f"hardneg:{kind}", f"hn_{kind}"
    txns, new_acc = [], {}

    def emit(s, d, a, t):
        txns.append(Txn(0, round(float(t), 3), s, d, round(float(a), 2), k, 0, gid, scn))

    if kind == "shopkeeper":      # fan-in burst, optional sweep to owner (looks like cash-out)
        center = f"S{hn_id:03d}"; new_acc[center] = {"type": "shop", "label": 0}
        cust = pick(rng, peers, ri(25, 70), exclude); dur = ru(300, 900)
        total = 0.0
        for c in cust:
            a = float(np.clip(rng.lognormal(5.0, 0.7), 20, 3000)); total += a
            emit(c, center, a, start_ts + ru(0, dur))
        if rng.random() < 0.5:
            owner = pick(rng, peers, 1, set(cust) | set(exclude))[0]
            emit(center, owner, 0.9 * total, start_ts + dur + ru(60, 300)); cust.append(owner)
        members = cust
    elif kind == "group_split":   # one payer fronts the bill, friends pay back (fan-in, short gaps)
        center = pick(rng, peers, 1, exclude)[0]
        friends = pick(rng, peers, ri(3, 8), {center} | set(exclude)); total = ru(1500, 12000)
        emit(center, merchants[int(rng.integers(len(merchants)))], total, start_ts)
        for f in friends:
            emit(f, center, total / (len(friends) + 1) * ru(0.95, 1.05), start_ts + ru(30, 900))
        members = [center] + friends
    elif kind == "rent":          # many tenants -> landlord, maybe forwarded onward
        center = f"L{hn_id:03d}"; new_acc[center] = {"type": "landlord", "label": 0}
        ten = pick(rng, peers, ri(6, 20), exclude); base = ru(8000, 25000); total = 0.0
        for tn in ten:
            a = base * ru(0.8, 1.2); total += a; emit(tn, center, a, start_ts + ru(0, 5400))
        members = list(ten)
        if rng.random() < 0.4:
            fam = pick(rng, peers, 1, set(ten) | set(exclude))[0]
            emit(center, fam, 0.7 * total, start_ts + 5400 + ru(600, 3600)); members.append(fam)
    elif kind == "salary":        # employer fan-out burst; some employees send part to family
        center = f"E{hn_id:03d}"; new_acc[center] = {"type": "employer", "label": 0}
        emp = pick(rng, peers, ri(10, 40), exclude); t = start_ts; members = list(emp)
        for e in emp:
            t += ru(0.2, 3.0); a = ru(15000, 80000); emit(center, e, a, t)
            if rng.random() < 0.3:
                fam = pick(rng, peers, 1, {e} | set(exclude))[0]
                emit(e, fam, a * ru(0.2, 0.4), t + ru(300, 3600)); members.append(fam)
    elif kind == "friend_settle": # small legit cycle among friends (looks circular)
        friends = pick(rng, peers, ri(3, 5), exclude); center = friends[0]; t = start_ts
        for i, f in enumerate(friends):
            t += ru(60, 900); emit(f, friends[(i + 1) % len(friends)], ru(200, 3000), t)
        members = friends
    else:
        raise ValueError(f"unknown hard-negative type {kind}")
    meta = {"hn_id": gid, "type": kind, "center": center, "members": sorted(set(members)),
            "start_ts": float(start_ts), "end_ts": max(x.ts for x in txns)}
    return txns, meta, new_acc
