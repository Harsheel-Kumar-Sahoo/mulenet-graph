"""Streaming runtime: simulator -> bus -> graph update -> score -> decision -> events. Framework-free (testable)."""
import asyncio, time
from collections import Counter, deque
from .graph.window import RollingGraph
from .decision import DecisionEngine, LEVELS
from .stream.bus import make_bus, make_store
from .stream.simulator import LiveSimulator
from .scorer import select_scorer


class EventHub:
    def __init__(self): self.clients = set()
    def subscribe(self, maxsize=1000):
        q = asyncio.Queue(maxsize); self.clients.add(q); return q
    def unsubscribe(self, q): self.clients.discard(q)
    def broadcast(self, msg):
        for q in list(self.clients):
            try: q.put_nowait(msg)
            except asyncio.QueueFull:
                try: q.get_nowait(); q.put_nowait(msg)       # drop oldest for slow clients
                except Exception: pass


class Runtime:
    def __init__(self, cfg, scorer=None, scorer_name=None, seed=None):
        self.cfg, self.seed, self.hub, self._tasks = cfg, seed, EventHub(), []
        self.scorer, self.scorer_name = (scorer, scorer_name or "custom") if scorer else select_scorer(cfg)
        self.speed, self.paused = float(cfg["sim"]["speed"]), False
        self._init_state()

    def _init_state(self):
        c = self.cfg
        self.sim, self.rg = LiveSimulator(c, self.seed), RollingGraph(c["graph"]["window_seconds"])
        self.bus, self.store = make_bus(c), make_store(c)
        self.decision = DecisionEngine(c, self.store)
        self.lat, self.stats, self.attacks, self.recent = deque(maxlen=2000), Counter(), {}, deque(maxlen=200)
        self.false_nodes = {l: set() for l in LEVELS}; self.harmed_groups = set()

    # ---- core step (sync, deterministic) ----
    def handle_txn(self, t) -> list:
        self.stats["txns"] += 1; ev = []
        st = self.decision.state_of(t.src)
        base = {"id": t.txn_id, "src": t.src, "dst": t.dst, "amount": t.amount, "ts": t.ts}
        if st in ("held", "frozen"):                              # outgoing transfer interrupted
            self.stats["blocked"] += 1
            if t.label:
                self.stats["blocked_ring"] += 1; self.stats["blocked_ring_amount"] += t.amount
                a = self.attacks.get(t.group_id)
                if a: a["blocked_txns"] += 1; a["amount_blocked"] += t.amount; a["interrupted"] = True
            else:
                self.stats["blocked_legit"] += 1; self.stats["blocked_legit_amount"] += t.amount
                if t.group_id: self.harmed_groups.add(t.group_id)
            return [{"type": "txn_blocked", "data": {**base, "reason": st, "is_ring": t.label}}]
        self.rg.add(t)
        a = self.attacks.get(t.group_id)
        if a and t.label and t.dst == a["cashout"] and not a["cashout_reached"]:
            a["cashout_reached"], a["cashout_ts"] = True, t.ts; self.stats["cashout_reached"] += 1
        t0 = time.perf_counter(); scores = self.scorer(self.rg.g, (t.src, t.dst), t.ts)
        self.lat.append((time.perf_counter() - t0) * 1e3)
        d = {**base, "kind": t.kind, "is_ring": t.label, "src_type": self.sim.accounts.get(t.src, {}).get("type", "?"),
             "dst_type": self.sim.accounts.get(t.dst, {}).get("type", "?")}
        self.recent.append(d); ev.append({"type": "txn", "data": d})
        rs = getattr(self.scorer, "reasons", None)
        for n, s in scores.items():
            e = self.decision.update(n, s, t.ts, (lambda n=n: rs(self.rg.g, n, t.ts)) if rs else (lambda: ["model_score"]))
            if e: self._track(e); ev.append(e)
        return ev

    def _track(self, e):
        n, to, ts = e["data"]["node"], e["data"]["to"], e["data"]["ts"]
        rid = self.sim.node_ring.get(n)
        if rid and rid in self.attacks:
            a = self.attacks[rid]
            for lvl, key in (("flagged", "first_flag_ts"), ("held", "first_hold_ts"), ("frozen", "first_freeze_ts")):
                if LEVELS.index(to) >= LEVELS.index(lvl) and a[key] is None: a[key] = ts
        elif to in self.false_nodes:
            self.false_nodes[to].add(n)

    # ---- controls ----
    def launch_attack(self, **kw):
        meta = self.sim.launch_attack(**kw)
        self.attacks[meta["ring_id"]] = {"ring_id": meta["ring_id"], "pattern": meta["pattern"], "start_ts": meta["start_ts"],
            "cashout": meta["cashout"], "mules": meta["mules"], "first_flag_ts": None, "first_hold_ts": None, "first_freeze_ts": None,
            "blocked_txns": 0, "amount_blocked": 0.0, "interrupted": False, "cashout_reached": False, "cashout_ts": None,
            "params": meta["params"]}
        self.hub.broadcast({"type": "attack", "data": {"ring_id": meta["ring_id"], "pattern": meta["pattern"], "mules": meta["mules"],
                                                       "cashout": meta["cashout"], "start_ts": meta["start_ts"]}})
        return meta

    def release(self, node):
        e = self.decision.release(node, self.sim.now); self.hub.broadcast(e); return e

    # ---- views ----
    def node_view(self, n):
        r = self.decision.record(n)
        return {"id": n, "type": self.sim.accounts.get(n, {}).get("type", "?"), "state": r["state"], "score": round(r["score"], 3),
                "truth_mule": bool(self.sim.accounts.get(n, {}).get("label", 0))}

    def snapshot(self):
        edges, nodes = {}, set(self.decision.nonnormal())
        for e in self.recent:
            k = (e["src"], e["dst"]); x = edges.setdefault(k, {"src": e["src"], "dst": e["dst"], "count": 0, "amount": 0.0, "is_ring": 0})
            x["count"] += 1; x["amount"] += e["amount"]; x["is_ring"] |= e["is_ring"]; nodes |= set(k)
        return {"synthetic": True, "scorer": self.scorer_name, "thresholds": self.decision.th, "metrics": self.metrics(),
                "nodes": [self.node_view(n) for n in nodes], "edges": list(edges.values())}

    def metrics(self):
        lat = sorted(self.lat); pc = lambda q: round(lat[min(len(lat) - 1, int(q / 100 * len(lat)))], 3) if lat else None
        s, atk = self.stats, []
        for a in self.attacks.values():
            st = Counter(self.decision.state_of(m) for m in a["mules"])
            atk.append({**{k: a[k] for k in ("ring_id", "pattern", "start_ts", "blocked_txns", "interrupted", "cashout_reached")},
                        "amount_blocked": round(a["amount_blocked"], 2),
                        "secs_to_flag": None if a["first_flag_ts"] is None else round(a["first_flag_ts"] - a["start_ts"], 1),
                        "secs_to_hold": None if a["first_hold_ts"] is None else round(a["first_hold_ts"] - a["start_ts"], 1),
                        "mules": len(a["mules"]), "mules_by_state": dict(st)})
        return {"synthetic": True, "scorer": self.scorer_name, "sim_time": round(self.sim.now, 1), "speed": self.speed, "paused": self.paused,
                "txns": s["txns"], "blocked": s["blocked"], "blocked_ring": s["blocked_ring"], "blocked_ring_amount": round(s["blocked_ring_amount"], 2),
                "blocked_legit": s["blocked_legit"], "blocked_legit_amount": round(s["blocked_legit_amount"], 2),
                "legit_groups_harmed": len(self.harmed_groups), "cashouts_reached": s["cashout_reached"],
                "false_alarm_nodes": {k: len(v) for k, v in self.false_nodes.items() if k != "normal"},
                "node_states": self.decision.counts(), "queue_depth": self.bus.qsize("txns"),
                "scoring_ms": {"n": len(lat), "p50": pc(50), "p95": pc(95), "p99": pc(99),
                               "note": "per-event sub-graph extraction + scoring, simulated load, one process, NOT a production claim"},
                "attacks": atk}

    # ---- async loops ----
    async def _producer(self):
        tick = self.cfg["sim"]["tick_s"]
        while True:
            if not self.paused:
                for t in self.sim.advance(tick * self.speed): await self.bus.send("txns", t)
            await asyncio.sleep(tick)

    async def _consumer(self):
        while True:
            t = await self.bus.poll("txns")
            for e in self.handle_txn(t): self.hub.broadcast(e)
            await asyncio.sleep(0)

    async def _metrics_loop(self):
        while True:
            await asyncio.sleep(1.0); self.hub.broadcast({"type": "metrics", "data": self.metrics()})

    def start(self):
        self._tasks = [asyncio.create_task(c()) for c in (self._producer, self._consumer, self._metrics_loop)]

    async def stop(self):
        for t in self._tasks: t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True); self._tasks = []

    async def reset(self):
        await self.stop(); self._init_state(); self.start(); self.hub.broadcast({"type": "snapshot", "data": self.snapshot()})
