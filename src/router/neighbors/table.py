"""Tabla de vecinos de un nodo.

Guarda, por cada vecino configurado, su identidad, dirección, costo
configurado del enlace y estado (activo/inactivo). El health check
(Fase 6, ver neighbors/health_check.py) es quien decide cuándo cambiar
el estado; esta clase solo lo almacena y expone consultas simples.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class NeighborState:
    node_id: str
    host: str
    port: int
    cost: int
    is_up: bool = True
    consecutive_failures: int = 0
    last_rtt_sec: float | None = None


class NeighborTable:
    def __init__(self, neighbors: list) -> None:
        self._neighbors: dict[str, NeighborState] = {
            n.node_id: NeighborState(node_id=n.node_id, host=n.host, port=n.port, cost=n.cost)
            for n in neighbors
        }
        self._lock = threading.Lock()

    def all_ids(self) -> list:
        with self._lock:
            return list(self._neighbors.keys())

    def get(self, node_id: str) -> NeighborState | None:
        with self._lock:
            return self._neighbors.get(node_id)

    def active_neighbors(self) -> dict:
        """dict[node_id] -> costo configurado, solo de vecinos activos."""
        with self._lock:
            return {nid: n.cost for nid, n in self._neighbors.items() if n.is_up}

    def mark_up(self, node_id: str) -> bool:
        """Devuelve True si hubo un cambio de estado (estaba caído)."""
        with self._lock:
            n = self._neighbors.get(node_id)
            if n is None:
                return False
            changed = not n.is_up
            n.is_up = True
            n.consecutive_failures = 0
            return changed

    def mark_down(self, node_id: str) -> bool:
        """Devuelve True si hubo un cambio de estado (estaba activo)."""
        with self._lock:
            n = self._neighbors.get(node_id)
            if n is None:
                return False
            changed = n.is_up
            n.is_up = False
            return changed

    def record_failure(self, node_id: str) -> int:
        """Incrementa el contador de fallos consecutivos y lo devuelve."""
        with self._lock:
            n = self._neighbors.get(node_id)
            if n is None:
                return 0
            n.consecutive_failures += 1
            return n.consecutive_failures

    def record_success(self, node_id: str, rtt_sec: float | None = None) -> None:
        with self._lock:
            n = self._neighbors.get(node_id)
            if n is None:
                return
            n.consecutive_failures = 0
            if rtt_sec is not None:
                n.last_rtt_sec = rtt_sec
