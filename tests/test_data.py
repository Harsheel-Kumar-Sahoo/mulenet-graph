import copy, tempfile, unittest
import networkx as nx
import numpy as np
from mulenet.config import load_config
from mulenet.data.generate import build_dataset
from mulenet.data.rings import inject_ring
from mulenet.data.schema import Dataset
from mulenet.data.hard_negatives import HN_TYPES

def small_cfg():
    cfg = copy.deepcopy(load_config())
    cfg["data"].update(n_accounts=400, n_merchants=20, n_normal_txns=3000, n_rings=9, n_hard_negatives=15)
    return cfg

class TestData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = small_cfg(); cls.ds = build_dataset(cls.cfg, seed=7)

    def test_deterministic(self):
        b = build_dataset(self.cfg, seed=7)
        self.assertEqual([(t.ts, t.src, t.dst, t.amount) for t in self.ds.txns],
                         [(t.ts, t.src, t.dst, t.amount) for t in b.txns])

    def test_basic_integrity(self):
        ts = [t.ts for t in self.ds.txns]
        self.assertEqual(ts, sorted(ts))
        self.assertEqual([t.txn_id for t in self.ds.txns], list(range(len(ts))))
        for t in self.ds.txns:
            self.assertNotEqual(t.src, t.dst); self.assertGreater(t.amount, 0)
            self.assertIn(t.src, self.ds.accounts); self.assertIn(t.dst, self.ds.accounts)
        self.assertTrue(self.ds.meta["synthetic"])

    def test_ring_structure_and_labels(self):
        pats = {r["pattern"] for r in self.ds.rings}
        self.assertEqual(pats, {"fan_out", "fan_in", "circular"})
        seen = set()
        for r in self.ds.rings:
            self.assertFalse(seen & set(r["mules"])); seen |= set(r["mules"])   # no mule in 2 rings
            rt = [t for t in self.ds.txns if t.group_id == r["ring_id"] and t.label == 1]
            g = nx.MultiDiGraph(); g.add_edges_from((t.src, t.dst) for t in rt)
            if r["pattern"] == "fan_out":
                self.assertGreaterEqual(max(d for _, d in g.out_degree()), 2)
            elif r["pattern"] == "fan_in":
                self.assertGreaterEqual(max(d for _, d in g.in_degree()), 2)
            else:
                self.assertTrue(any(True for _ in nx.simple_cycles(nx.DiGraph(g))))
            first_in, inflow, outflow = {}, {}, {}
            for t in rt:                       # causality + conservation
                first_in[t.dst] = min(first_in.get(t.dst, 1e18), t.ts)
                inflow[t.dst] = inflow.get(t.dst, 0) + t.amount
            for t in rt:
                if t.src in r["mules"]:
                    self.assertGreater(t.ts, first_in[t.src])
                    outflow[t.src] = outflow.get(t.src, 0) + t.amount
            for m, o in outflow.items():
                self.assertLessEqual(o, inflow[m] + 1.0)
            self.assertLessEqual(r["start_ts"], r["cashout_ts"])
            for m in r["mules"]:
                self.assertEqual(self.ds.accounts[m]["label"], 1)

    def test_hard_negatives(self):
        self.assertEqual({h["type"] for h in self.ds.hard_negatives}, set(HN_TYPES))
        mules = {m for r in self.ds.rings for m in r["mules"]}
        for t in self.ds.txns:
            if t.scenario.startswith("hardneg"):
                self.assertEqual(t.label, 0)
        for h in self.ds.hard_negatives:
            self.assertFalse(set(h["members"]) & mules)
            self.assertEqual(self.ds.accounts[h["center"]]["label"], 0)

    def test_overrides(self):
        rng = np.random.default_rng(1)
        peers = [f"A{i:05d}" for i in range(100)]
        txns, meta = inject_ring(self.cfg, rng, peers, ["M0001"], 100.0, 99,
                                 pattern="circular", size=6, depth=3, hop_gap=[1, 2])
        self.assertEqual(len(meta["mules"]), 6); self.assertEqual(meta["pattern"], "circular")
        self.assertEqual(meta["params"]["hop_gap"], [1, 2])

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            self.ds.save(d); b = Dataset.load(d)
        self.assertEqual(len(b.txns), len(self.ds.txns))
        self.assertEqual(b.summary(), self.ds.summary())

if __name__ == "__main__":
    unittest.main()
