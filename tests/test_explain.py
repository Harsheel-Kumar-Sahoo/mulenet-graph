import unittest
from mulenet.config import load_config
from mulenet.livesmoke import run_live
from mulenet.explain.explain import explain_node
import copy

def cfg0():
    c = copy.deepcopy(load_config()); c["data"].update(n_accounts=600, n_merchants=30); return c

class TestExplain(unittest.TestCase):
    def test_ring_node_explained(self):
        rt = run_live(cfg0(), seed=3, warmup=120, attacks=[dict(pattern="circular", size=6, depth=3, hop_gap=[1, 3])], after=40)
        a = list(rt.attacks.values())[0]
        ex = [explain_node(rt, m) for m in a["mules"]]
        hit = [e for e in ex if e["in_window"] and e["reasons"]]
        self.assertTrue(hit, "at least one mule should have a named reason")
        e = hit[0]; self.assertTrue(e["synthetic"]); self.assertTrue(e["edges"])
        self.assertEqual(sorted(e["edges"], key=lambda r: -r["delta"]), e["edges"])
        self.assertIn("not an accusation", e["caveat"])

    def test_unknown_node(self):
        rt = run_live(cfg0(), seed=3, warmup=20)
        e = explain_node(rt, "ZZZ"); self.assertFalse(e["in_window"]); self.assertEqual(e["edges"], [])

if __name__ == "__main__": unittest.main()
