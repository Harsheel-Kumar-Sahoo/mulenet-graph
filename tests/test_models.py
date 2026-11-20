import copy, unittest
import numpy as np
from mulenet.config import load_config
from mulenet.data.generate import build_dataset
from mulenet.models.dataset import build_samples, fit_scaler
from mulenet.features.node_features import FEATURE_NAMES
from mulenet.models import gnn

class TestSamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config(); c = copy.deepcopy(cls.cfg)
        c["data"].update(n_accounts=400, n_merchants=20, n_normal_txns=2000, n_rings=6, n_hard_negatives=10)
        cls.ds = build_dataset(c, seed=5); cls.S = build_samples(cls.ds, cls.cfg, max_normal=300, seed=0)

    def test_sample_shapes(self):
        mx = self.cfg["graph"]["max_subgraph_nodes"]
        for s in self.S:
            n = len(s["x"]); self.assertLessEqual(n, mx); self.assertEqual(s["x"].shape[1], len(FEATURE_NAMES))
            self.assertEqual(len(s["y"]), n); self.assertTrue(np.isfinite(s["x"]).all())
            if s["edge_index"].size: self.assertLess(s["edge_index"].max(), n)
            self.assertIn(s["n_seed"], (1, 2))

    def test_has_positives_and_negatives(self):
        y = np.concatenate([s["y"] for s in self.S]); self.assertGreater(y.sum(), 0); self.assertLess(y.mean(), 0.5)
        m, sd = fit_scaler(self.S); self.assertEqual(m.shape[0], len(FEATURE_NAMES)); self.assertTrue((sd > 0).all())

@unittest.skipUnless(gnn.HAS_TORCH, "torch not installed (written, not executed)")
class TestModel(unittest.TestCase):
    def test_forward_and_roundtrip(self):
        import tempfile, os, torch
        cfg = load_config(); model, backend, kind = gnn.build_model(cfg)
        x = torch.randn(5, len(FEATURE_NAMES)); ei = torch.tensor([[0, 1, 2], [1, 2, 0]])
        self.assertEqual(model(x, ei).shape, (5,))
        self.assertEqual(model(x, torch.zeros(2, 0, dtype=torch.long)).shape, (5,))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "m.pt"); gnn.save_checkpoint(p, model, backend, kind, np.zeros(len(FEATURE_NAMES)), np.ones(len(FEATURE_NAMES)), cfg)
            m2, ck = gnn.load_checkpoint(p, cfg); m2.eval(); model.eval()
            self.assertTrue(torch.allclose(model(x, ei), m2(x, ei), atol=1e-6))

if __name__ == "__main__":
    unittest.main()
