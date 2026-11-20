"""Graded response: score -> monitor / flag / hold / freeze. Escalate-only until a human releases the node."""
from collections import deque

LEVELS = ["normal", "flagged", "held", "frozen"]
ACTION = {"normal": "monitor", "flagged": "flag_step_up_or_delay", "held": "hold_outgoing_pending_review",
          "frozen": "freeze_and_escalate_to_fraud_team"}


class DecisionEngine:
    def __init__(self, cfg, store):
        p = cfg["policy"]; self.store = store
        self.th = {"flag_at": p["flag_at"], "hold_at": p["hold_at"], "freeze_at": p["freeze_at"]}
        self.log = deque(maxlen=1000)

    def set_thresholds(self, **kw):
        new = {**self.th, **{k: float(v) for k, v in kw.items() if v is not None and k in self.th}}
        if not (0 < new["flag_at"] < new["hold_at"] < new["freeze_at"] <= 1):
            raise ValueError("need 0 < flag_at < hold_at < freeze_at <= 1")
        self.th = new

    def level_for(self, score):
        t = self.th
        return "frozen" if score >= t["freeze_at"] else "held" if score >= t["hold_at"] else "flagged" if score >= t["flag_at"] else "normal"

    def record(self, n):
        return self.store.get(f"node:{n}") or {"state": "normal", "score": 0.0, "peak": 0.0}

    def state_of(self, n): return self.record(n)["state"]

    def update(self, node, score, ts, reasons_fn=None):
        rec = self.record(node); rec["score"] = float(score); rec["peak"] = max(rec["peak"], float(score))
        new, cur, ev = self.level_for(score), rec["state"], None
        if LEVELS.index(new) > LEVELS.index(cur):
            rec["state"] = new
            ev = {"type": "state", "data": {"node": node, "from": cur, "to": new, "action": ACTION[new], "score": round(float(score), 3),
                                            "ts": ts, "reasons": reasons_fn() if reasons_fn else [], "needs_review": new == "frozen",
                                            "note": "Risk node for human review, not an accusation."}}
            self.log.append(ev)
        self.store.set(f"node:{node}", rec)
        return ev

    def release(self, node, ts=0.0):
        """Human review outcome: clear the node (demo of the appeal/review path)."""
        prev = self.state_of(node); self.store.set(f"node:{node}", {"state": "normal", "score": 0.0, "peak": 0.0, "released": True})
        return {"type": "state", "data": {"node": node, "from": prev, "to": "normal", "action": "released_by_reviewer", "score": 0.0,
                                          "ts": ts, "reasons": ["manual_release"], "needs_review": False}}

    def nonnormal(self): return [k[5:] for k in self.store.keys("node:") if self.store.get(k)["state"] != "normal"]

    def counts(self):
        c = {l: 0 for l in LEVELS}
        for k in self.store.keys("node:"): c[self.store.get(k)["state"]] += 1
        return c
