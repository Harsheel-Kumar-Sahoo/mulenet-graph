"""Live synthetic traffic: rolling normal traffic + hard negatives + on-demand mule-ring attacks (SYNTHETIC)."""
import heapq
import numpy as np
from ..data.normal import generate_normal
from ..data.rings import inject_ring
from ..data.hard_negatives import make_hard_negative

PATTERNS = ("fan_out", "fan_in", "circular")


class LiveSimulator:
    def __init__(self, cfg, seed=None):
        self.cfg, sc = cfg, cfg["sim"]
        self.rng = np.random.default_rng(cfg["seed"] if seed is None else seed)
        self.now, self.heap, self._n, self.gen_until = 0.0, [], 0, 0.0
        self.accounts, _, self.peers, self.merchants = generate_normal(self._ncfg(1.0, 1), self.rng)
        self.mule_set, self.node_ring, self.ring_n, self.hn_n = set(), {}, 0, 0
        self.ring_meta = {}

    def _ncfg(self, chunk, n):
        return {"data": {**self.cfg["data"], "horizon_seconds": chunk, "n_normal_txns": int(n)}}

    def _push(self, txns):
        for t in txns:
            t.txn_id = self._n; heapq.heappush(self.heap, (t.ts, self._n, t)); self._n += 1

    def _gen_chunk(self):
        sc, d = self.cfg["sim"], self.cfg["data"]; ch = float(sc["chunk_s"])
        _, txns, _, _ = generate_normal(self._ncfg(ch, sc["normal_rate"] * ch), self.rng)
        for t in txns:
            t.ts = round(t.ts + self.gen_until, 3)
        self._push(txns)
        types = d["hard_negative_types"]
        for _ in range(int(self.rng.poisson(ch / sc["hardneg_every_s"]))):
            ht, meta, acc = make_hard_negative(self.cfg, self.rng, self.peers, self.merchants,
                                               self.gen_until + float(self.rng.uniform(0, ch * 0.5)), self.hn_n,
                                               str(self.rng.choice(types)), exclude=self.mule_set)
            self.hn_n += 1; self.accounts.update(acc); self._push(ht)
        self.gen_until += ch

    def advance(self, dt_sim):
        """Advance simulated time; return due transactions in time order."""
        self.now += dt_sim
        while self.gen_until < self.now + self.cfg["sim"]["chunk_s"]:
            self._gen_chunk()
        out = []
        while self.heap and self.heap[0][0] <= self.now:
            out.append(heapq.heappop(self.heap)[2])
        return out

    def launch_attack(self, pattern=None, size=None, depth=None, hop_gap=None, split_ratio=None):
        if pattern is not None and pattern not in PATTERNS: raise ValueError(f"pattern must be one of {PATTERNS}")
        if size is not None and not 3 <= size <= 30: raise ValueError("size must be 3..30")
        if depth is not None and not 2 <= depth <= 6: raise ValueError("depth must be 2..6")
        if hop_gap is not None and not 0 < hop_gap[0] < hop_gap[1]: raise ValueError("hop_gap needs 0 < min < max")
        if split_ratio is not None and not 0 < split_ratio < 1: raise ValueError("split_ratio must be in (0,1)")
        txns, meta = inject_ring(self.cfg, self.rng, self.peers, self.merchants, self.now + 1.0, self.ring_n,
                                 exclude=self.mule_set, pattern=pattern, size=size, depth=depth,
                                 hop_gap=hop_gap, split_ratio=split_ratio)
        self.ring_n += 1; self.mule_set |= set(meta["mules"]); self._push(txns)
        for m in meta["mules"]:
            self.accounts[m]["label"] = 1; self.node_ring[m] = meta["ring_id"]
        self.accounts[meta["cashout"]] = {"type": "cashout", "label": 1}; self.node_ring[meta["cashout"]] = meta["ring_id"]
        self.ring_meta[meta["ring_id"]] = meta
        return meta
