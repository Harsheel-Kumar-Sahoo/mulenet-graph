"""In-process stream primitives with Kafka/Redis-shaped interfaces. Real adapters: stream/adapters.py (optional)."""
import asyncio


class StateStore:
    """Key-value state (Redis subset): get/set/delete/keys(prefix)."""
    def __init__(self): self._d = {}
    def get(self, k, default=None): return self._d.get(k, default)
    def set(self, k, v): self._d[k] = v
    def delete(self, k): self._d.pop(k, None)
    def keys(self, prefix=""): return [k for k in self._d if k.startswith(prefix)]
    def flush(self): self._d.clear()


class InProcessBus:
    """Producer/consumer over asyncio queues (Kafka subset): send(topic, msg), poll(topic)."""
    def __init__(self, maxsize=10000): self.maxsize, self._q = maxsize, {}
    def _topic(self, t): return self._q.setdefault(t, asyncio.Queue(self.maxsize))
    async def send(self, topic, msg): await self._topic(topic).put(msg)
    async def poll(self, topic): return await self._topic(topic).get()
    def qsize(self, topic): return self._topic(topic).qsize()


def make_bus(cfg):
    b = cfg["stream"]["backend"]
    if b == "kafka":
        from .adapters import KafkaBus
        return KafkaBus(cfg["stream"]["kafka"])
    return InProcessBus(cfg["stream"]["queue_maxsize"])


def make_store(cfg):
    if cfg["stream"]["backend"] == "redis":
        from .adapters import RedisStateStore
        return RedisStateStore(cfg["stream"]["redis"]["url"])
    return StateStore()
