"""Rolling-window transaction graph (NetworkX DiGraph; edge attr tx=[(ts, amount), ...])."""
from collections import deque
import networkx as nx


class RollingGraph:
    def __init__(self, window_seconds: float):
        self.window, self.g, self.now = float(window_seconds), nx.DiGraph(), -1e18
        self._q = deque()

    def add(self, t) -> None:
        if t.ts < self.now:
            raise ValueError("transactions must arrive in time order")
        self.now = t.ts
        if self.g.has_edge(t.src, t.dst):
            self.g[t.src][t.dst]["tx"].append((t.ts, t.amount))
        else:
            self.g.add_edge(t.src, t.dst, tx=[(t.ts, t.amount)])
        self._q.append(t)
        cutoff = self.now - self.window
        while self._q and self._q[0].ts < cutoff:
            o = self._q.popleft()
            lst = self.g[o.src][o.dst]["tx"]; lst.pop(0)       # oldest first (time-ordered)
            if not lst:
                self.g.remove_edge(o.src, o.dst)
                for n in (o.src, o.dst):
                    if n in self.g and self.g.degree(n) == 0:
                        self.g.remove_node(n)

    def __len__(self):
        return len(self._q)
