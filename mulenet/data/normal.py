"""Normal UPI-like traffic: peer transfers, merchant payments, bills."""
import numpy as np
from .schema import Txn


def generate_normal(cfg, rng):
    d = cfg["data"]; H = float(d["horizon_seconds"])
    peers = [f"A{i:05d}" for i in range(d["n_accounts"])]
    merchants = [f"M{i:04d}" for i in range(d["n_merchants"])]
    utilities = [f"U{i:02d}" for i in range(8)]
    accounts = {}
    for ids, typ in ((peers, "peer"), (merchants, "merchant"), (utilities, "utility")):
        for a in ids:
            accounts[a] = {"type": typ, "label": 0}
    n = int(d["n_normal_txns"])
    pw = rng.pareto(2.5, len(peers)) + 1.0; pw /= pw.sum()          # heavy-tailed activity
    mw = 1.0 / np.arange(1, len(merchants) + 1) ** 0.8; mw /= mw.sum()  # zipf merchant popularity
    src = rng.choice(len(peers), size=n, p=pw)
    kind = rng.choice(3, size=n, p=[0.35, 0.55, 0.10])
    ts = rng.uniform(0, H, size=n)
    m_dst = rng.choice(len(merchants), size=n, p=mw)
    p_off = rng.integers(1, len(peers), size=n)
    u_dst = rng.integers(0, len(utilities), size=n)
    amt = (rng.lognormal(6.2, 0.9, n), rng.lognormal(5.0, 0.8, n), rng.lognormal(6.5, 0.5, n))
    txns = []
    for i in range(n):
        s, k = int(src[i]), int(kind[i])
        if k == 0:
            dst, name, a = peers[(s + int(p_off[i])) % len(peers)], "peer", np.clip(amt[0][i], 10, 25000)
        elif k == 1:
            dst, name, a = merchants[int(m_dst[i])], "merchant", np.clip(amt[1][i], 5, 5000)
        else:
            dst, name, a = utilities[int(u_dst[i])], "bill", np.clip(amt[2][i], 100, 15000)
        txns.append(Txn(0, round(float(ts[i]), 3), peers[s], dst, round(float(a), 2), name))
    return accounts, txns, peers, merchants
