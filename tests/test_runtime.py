import asyncio, copy, unittest
from mulenet.config import load_config
from mulenet.baseline.rules import GradedHeuristic
from mulenet.decision import DecisionEngine
from mulenet.runtime import Runtime
from mulenet.stream.bus import StateStore, InProcessBus
from mulenet.stream.simulator import LiveSimulator

def cfg0():
    c = copy.deepcopy(load_config()); c["data"].update(n_accounts=600, n_merchants=30); return c

def drive(rt, seconds, step=1.0):
    ev = []
    for _ in range(int(seconds / step)):
        for t in rt.sim.advance(step): ev += rt.handle_txn(t)
    return ev

class TestStreamPieces(unittest.IsolatedAsyncioTestCase):
    async def test_bus_and_store(self):
        b = InProcessBus(10); await b.send("t", 1); await b.send("t", 2)
        self.assertEqual((await b.poll("t"), await b.poll("t")), (1, 2)); self.assertEqual(b.qsize("t"), 0)
        s = StateStore(); s.set("node:a", {"x": 1}); self.assertEqual(s.keys("node:"), ["node:a"]); s.delete("node:a"); self.assertIsNone(s.get("node:a"))

    def test_decision_escalate_only_and_release(self):
        d = DecisionEngine(load_config(), StateStore())
        self.assertEqual(d.update("n", 0.1, 1.0), None)
        self.assertEqual(d.update("n", 0.4, 2.0)["data"]["to"], "flagged")
        self.assertEqual(d.update("n", 0.7, 3.0)["data"]["to"], "held")
        self.assertIsNone(d.update("n", 0.1, 4.0)); self.assertEqual(d.state_of("n"), "held")   # no auto-downgrade
        e = d.update("n", 0.9, 5.0); self.assertTrue(e["data"]["needs_review"])
        d.release("n"); self.assertEqual(d.state_of("n"), "normal")
        with self.assertRaises(ValueError): d.set_thresholds(flag_at=0.9)
        d.set_thresholds(freeze_at=0.95); self.assertEqual(d.th["freeze_at"], 0.95)

    def test_simulator_order_and_validation(self):
        sim = LiveSimulator(cfg0(), seed=1); last = -1
        for _ in range(60):
            for t in sim.advance(5.0):
                self.assertGreaterEqual(t.ts, last); last = t.ts
        m = sim.launch_attack(pattern="circular", size=6, depth=3, hop_gap=[1, 3]); self.assertEqual(len(m["mules"]), 6)
        for bad in (dict(pattern="x"), dict(size=1), dict(depth=9), dict(hop_gap=[5, 2]), dict(split_ratio=1.5)):
            with self.assertRaises(ValueError): sim.launch_attack(**bad)
        for t in sim.advance(400.0):
            self.assertGreaterEqual(t.ts, last); last = t.ts

    def test_end_to_end_attack_is_interrupted(self):
        rt = Runtime(cfg0(), GradedHeuristic(cfg0()), "test", seed=3)
        drive(rt, 300)                                                  # warm-up traffic
        metas = [rt.launch_attack(pattern=p, size=8, depth=3, hop_gap=[2, 10]) for p in ("fan_out", "fan_in", "circular")]
        ev = drive(rt, 400)
        m = rt.metrics()
        self.assertGreater(m["txns"], 500); self.assertGreater(m["scoring_ms"]["n"], 0)
        self.assertTrue(any(e["type"] == "state" for e in ev))
        self.assertEqual(len(m["attacks"]), 3)
        self.assertTrue(any(a["secs_to_hold"] is not None for a in m["attacks"]), m["attacks"])
        self.assertGreater(m["blocked_ring"], 0)                       # chain interrupted
        self.assertIn("legit_groups_harmed", m); self.assertIn("false_alarm_nodes", m)
        snap = rt.snapshot(); self.assertTrue(snap["synthetic"]); self.assertTrue(snap["nodes"])

class TestAsyncPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_loops_run(self):
        c = cfg0(); c["sim"]["tick_s"] = 0.05; rt = Runtime(c, GradedHeuristic(c), "test", seed=4); rt.speed = 60
        q = rt.hub.subscribe(); rt.start(); rt.launch_attack(pattern="fan_out", size=6)
        await asyncio.sleep(1.5); await rt.stop()
        self.assertGreater(rt.stats["txns"], 20); self.assertFalse(q.empty())
        await rt.reset(); await asyncio.sleep(0.2); self.assertLess(rt.stats["txns"], 20); await rt.stop()

if __name__ == "__main__":
    unittest.main()
