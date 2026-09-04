"""Link State Routing: LSDB con expiración y Dijkstra sobre los LSP."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from router.algorithms.dijkstra import RouteEntry, build_routing_table


def normalize_neighbors(value: Any) -> dict[str, int | float]:
    """Acepta las variantes de ``neighbors`` definidas para recepción."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}

    if isinstance(value, dict):
        if "neighbors" in value:
            return normalize_neighbors(value["neighbors"])
        if "links" in value:
            return normalize_neighbors(value["links"])
        result = {}
        for node_id, weight in value.items():
            if isinstance(weight, (int, float)) and not isinstance(weight, bool):
                result[str(node_id)] = weight
        return result

    if isinstance(value, list):
        result = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            node_id = item.get("id", item.get("node"))
            weight = item.get("weight", item.get("cost"))
            if isinstance(node_id, str) and isinstance(weight, (int, float)) and not isinstance(weight, bool):
                result[node_id] = weight
        return result
    return {}


def parse_lsp_payload(payload: Any) -> tuple[str, int, float, dict[str, int | float]] | None:
    """Valida y normaliza el payload de un anuncio LSP."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    origin = payload.get("origin")
    seq = payload.get("seq")
    if not isinstance(origin, str) or not origin:
        return None
    if not isinstance(seq, int) or isinstance(seq, bool):
        return None
    age_s = payload.get("age_s", 0)
    if not isinstance(age_s, (int, float)) or isinstance(age_s, bool):
        age_s = 0.0
    neighbors = normalize_neighbors(payload.get("neighbors", payload.get("links", {})))
    return origin, seq, float(age_s), neighbors


@dataclass
class LspEntry:
    seq: int
    neighbors: dict
    received_at: float = field(default_factory=time.monotonic)


class LinkStateDatabase:
    """Último LSP por origen, con expiración local configurable."""

    def __init__(self, expiry_sec: float = 30.0, clock=time.monotonic) -> None:
        self._entries: dict[str, LspEntry] = {}
        self._expiry_sec = expiry_sec
        self._clock = clock
        self._lock = threading.RLock()

    def update(self, origin: str, seq: int, neighbors: Any, received_at: float | None = None) -> bool:
        normalized = normalize_neighbors(neighbors)
        with self._lock:
            current = self._entries.get(origin)
            if current is not None and not (seq > current.seq or current.seq - seq > 16):
                return False
            self._entries[origin] = LspEntry(
                seq=seq,
                neighbors=dict(normalized),
                received_at=self._clock() if received_at is None else received_at,
            )
            return True

    def expire(self, now: float | None = None) -> list[str]:
        now = self._clock() if now is None else now
        with self._lock:
            expired = [
                origin
                for origin, entry in self._entries.items()
                if now - entry.received_at >= self._expiry_sec
            ]
            for origin in expired:
                del self._entries[origin]
            return expired

    def get_seq(self, origin: str) -> int:
        with self._lock:
            entry = self._entries.get(origin)
            return entry.seq if entry else -1

    def known_origins(self) -> list:
        with self._lock:
            return list(self._entries.keys())

    def to_edges(self) -> dict:
        with self._lock:
            return {origin: dict(entry.neighbors) for origin, entry in self._entries.items()}


class LsrRoutingEngine:
    """Orquesta LSDB + Dijkstra en modo ``lsr``."""

    def __init__(self, node_id: str, expiry_sec: float = 30.0, clock=time.monotonic) -> None:
        self.node_id = node_id
        self.lsdb = LinkStateDatabase(expiry_sec=expiry_sec, clock=clock)
        self.table: dict = {}
        self._own_seq = 0

    def next_own_seq(self) -> int:
        self._own_seq += 1
        return self._own_seq

    def apply_lsp(
        self,
        origin: str,
        seq: int,
        neighbors: Any,
        received_at: float | None = None,
    ) -> bool:
        applied = self.lsdb.update(origin, seq, neighbors, received_at=received_at)
        if applied:
            self._recompute()
        return applied

    def expire_lsp(self, now: float | None = None) -> list[str]:
        expired = self.lsdb.expire(now)
        if expired:
            self._recompute()
        return expired

    def _recompute(self) -> None:
        edges = self.lsdb.to_edges()
        if self.node_id not in edges:
            self.table = {}
            return
        self.table = build_routing_table(self.node_id, edges)

    def next_hop(self, destination: str) -> str | None:
        entry = self.table.get(destination)
        return entry.next_hop if entry else None

    def route_entry(self, destination: str) -> RouteEntry | None:
        return self.table.get(destination)
