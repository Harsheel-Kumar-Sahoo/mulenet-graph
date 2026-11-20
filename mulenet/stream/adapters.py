"""OPTIONAL real Kafka / Redis adapters (config: stream.backend = kafka | redis). Written, NOT executed."""
import asyncio, json
from dataclasses import asdict
from ..data.schema import Txn


class KafkaBus:
    def __init__(self, c):
        from kafka import KafkaProducer, KafkaConsumer          # pip install kafka-python
        self.c = c
        self.p = KafkaProducer(bootstrap_servers=c["bootstrap_servers"], value_serializer=lambda v: json.dumps(v).encode())
        self.cons = KafkaConsumer(c["topic"], bootstrap_servers=c["bootstrap_servers"], group_id="mulenet",
                                  value_deserializer=lambda b: json.loads(b.decode()))
        self._it = iter(self.cons)

    async def send(self, topic, msg):
        await asyncio.to_thread(lambda: self.p.send(self.c["topic"], asdict(msg)).get(timeout=5))

    async def poll(self, topic):
        return Txn(**(await asyncio.to_thread(lambda: next(self._it))).value)

    def qsize(self, topic): return 0


class RedisStateStore:
    def __init__(self, url):
        import redis                                            # pip install redis
        self.r = redis.Redis.from_url(url, decode_responses=True)
    def get(self, k, default=None):
        v = self.r.get(k); return json.loads(v) if v is not None else default
    def set(self, k, v): self.r.set(k, json.dumps(v))
    def delete(self, k): self.r.delete(k)
    def keys(self, prefix=""): return list(self.r.scan_iter(prefix + "*"))
    def flush(self):
        for k in self.keys("node:"): self.r.delete(k)
