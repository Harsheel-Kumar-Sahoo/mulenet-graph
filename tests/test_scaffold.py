import unittest
from mulenet.config import load_config, get

class TestScaffold(unittest.TestCase):
    def test_config_loads(self):
        cfg = load_config()
        self.assertEqual(get(cfg, "stream.backend"), "inprocess")
        self.assertLess(get(cfg, "policy.flag_at"), get(cfg, "policy.hold_at"))
        self.assertLess(get(cfg, "policy.hold_at"), get(cfg, "policy.freeze_at"))
        self.assertEqual(get(cfg, "nope.missing", 7), 7)

if __name__ == "__main__":
    unittest.main()
