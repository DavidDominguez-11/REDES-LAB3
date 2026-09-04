"""LSDB con expiración local y rutas calculadas por Dijkstra."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from router.algorithms.dijkstra import RouteEntry, build_routing_table

LSP_LIFETIME_SEC = 30.0


@dataclass
class LspEntry:
    seq: int
    neighbors: dict
    received_at: float
    age_s: float = 0


class LinkStateDatabase:
    def __init__(self, clock=time.monotonic) -> None:
        self._entries: dict[str, LspEntry] = {}
        self._clock = clock

    def update(self, origin: str, seq: int, neighbors: dict, age_s: float = 0) -> bool:
        current = self._entries.get(origin)
        if current is not None and seq <= current.seq:
            return False
        self._entries[origin] = LspEntry(seq, dict(neighbors), self._clock(), age_s)
        return True

    def expire(self) -> list[str]:
        now = self._clock()
        expired = [origin for origin, entry in self._entries.items()
                   if now - entry.received_at >= LSP_LIFETIME_SEC]
        for origin in expired:
            del self._entries[origin]
        return expired

    def get_seq(self, origin: str) -> int:
        entry = self._entries.get(origin)
        return entry.seq if entry else -1

    def known_origins(self) -> list:
        return list(self._entries)

    def snapshot(self) -> list:
        return [(origin, entry.seq, dict(entry.neighbors)) for origin, entry in self._entries.items()]

    def snapshot_with_age(self) -> list:
        now = self._clock()
        return [(origin, entry.seq, dict(entry.neighbors), entry.age_s + now - entry.received_at)
                for origin, entry in self._entries.items()]

    def to_edges(self) -> dict:
        return {origin: dict(entry.neighbors) for origin, entry in self._entries.items()}


class LsrRoutingEngine:
    def __init__(self, node_id: str, clock=time.monotonic) -> None:
        self.node_id = node_id
        self.lsdb = LinkStateDatabase(clock=clock)
        self.table: dict = {}
        self._own_seq = 0
        self._lock = threading.RLock()

    def next_own_seq(self) -> int:
        with self._lock:
            # Un snapshot puede devolver nuestro contador previo a un reinicio.
            self._own_seq = max(self._own_seq, self.lsdb.get_seq(self.node_id)) + 1
            return self._own_seq

    def apply_lsp(self, origin: str, seq: int, neighbors: dict, age_s: float = 0) -> bool:
        with self._lock:
            expired = self.lsdb.expire()
            applied = self.lsdb.update(origin, seq, neighbors, age_s)
            if applied or expired:
                self._recompute()
            return applied

    def expire(self) -> list[str]:
        with self._lock:
            expired = self.lsdb.expire()
            if expired:
                self._recompute()
            return expired

    def _recompute(self) -> None:
        edges = self.lsdb.to_edges()
        self.table = build_routing_table(self.node_id, edges) if self.node_id in edges else {}

    def next_hop(self, destination: str) -> str | None:
        entry = self.route_entry(destination)
        return entry.next_hop if entry else None

    def route_entry(self, destination: str) -> RouteEntry | None:
        with self._lock:
            self.expire()
            return self.table.get(destination)

    def routes(self) -> dict:
        with self._lock:
            self.expire()
            return dict(self.table)

    def snapshot(self) -> list:
        with self._lock:
            self.expire()
            return self.lsdb.snapshot()

    def snapshot_with_age(self) -> list:
        with self._lock:
            self.expire()
            return self.lsdb.snapshot_with_age()

    def known_origins(self) -> list:
        with self._lock:
            self.expire()
            return self.lsdb.known_origins()
