import copy, unittest
import networkx as nx
from mulenet.config import load_config
from mulenet.data.generate import build_dataset
from mulenet.data.schema import Txn
from mulenet.graph.window import RollingGraph
from mulenet.graph.subgraph import k_hop_nodes
from mulenet.features.node_features import node_features, on_cycle, feature_vector, FEATURE_NAMES
from mulenet.baseline.rules import RuleBaseline, GraphHeuristic
from mulenet.evaluate import evaluate, metrics

T = lambda ts, s, d, a=1000.0: Txn(0, ts, s, d, a, "x")

class TestGraph(unittest.TestCase):
    def test_eviction(self):
        rg = RollingGraph(100); rg.add(T(0, "A", "B")); rg.add(T(50, "B", "C")); rg.add(T(150, "C", "D"))
        self.assertFalse(rg.g.has_edge("A", "B")); self.assertNotIn("A", rg.g)
        self.assertTrue(rg.g.has_edge("B", "C")); self.assertEqual(len(rg), 2)
        with self.assertRaises(ValueError): rg.add(T(10, "X", "Y"))

    def test_repeat_edge_partial_evict(self):
        rg = RollingGraph(100); rg.add(T(0, "A", "B")); rg.add(T(60, "A", "B")); rg.add(T(120, "C", "D"))
        self.assertEqual(len(rg.g["A"]["B"]["tx"]), 1)

    def test_khop_bounds(self):
        g = nx.path_graph(10, create_using=nx.DiGraph)
        self.assertEqual(k_hop_nodes(g, [0], 2, 99), {0, 1, 2})
        self.assertLessEqual(len(k_hop_nodes(g, [5], 4, 4)), 4)

    def test_features_and_cycle(self):
        rg = RollingGraph(600); rg.add(T(0, "A", "B")); rg.add(T(5, "B", "C", 950)); rg.add(T(9, "C", "A", 900))
        f = node_features(rg.g, "B", 9, 600)
        self.assertAlmostEqual(f["fwd_ratio"], 0.95); self.assertEqual(f["_min_gap"], 5); self.assertEqual(f["passthrough"], 1.0)
        self.assertEqual(f["in_cycle"], 1.0); self.assertEqual(len(feature_vector(f)), len(FEATURE_NAMES))
        g2 = nx.DiGraph([("A", "B"), ("B", "A")]); self.assertFalse(on_cycle(g2, "A"))

class TestEval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config(); c = copy.deepcopy(cls.cfg)
        c["data"].update(n_accounts=400, n_merchants=20, n_normal_txns=3000, n_rings=9, n_hard_negatives=15)
        cls.ds = build_dataset(c, seed=3)

    def test_metric_extremes(self):
        allf = {n: 0.0 for t in self.ds.txns for n in (t.src, t.dst)}
        m = metrics(self.ds, allf)
        self.assertEqual(m["node"]["recall"], 1.0); self.assertEqual(m["node"]["fpr_all_nonmule"], 1.0)
        self.assertEqual(m["hard_negative"]["fpr_groups"], 1.0)
        m0 = metrics(self.ds, {}); self.assertEqual(m0["node"]["recall"], 0.0); self.assertEqual(m0["ring"]["recall_before_cashout"], 0.0)

    def test_baselines_run_and_detect_something(self):
        for B in (RuleBaseline, GraphHeuristic):
            m = evaluate(self.ds, B(self.cfg), self.cfg)
            self.assertGreater(m["ring"]["recall_before_cashout"], 0.0, B.name)
            self.assertTrue(0 <= m["hard_negative"]["fpr_groups"] <= 1)

if __name__ == "__main__":
    unittest.main()
