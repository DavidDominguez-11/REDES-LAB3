"""Link State Routing (LSR).

LSR = Flooding (para distribuir los LSP a toda la red) + Dijkstra (para
calcular rutas óptimas sobre la topología reconstruida a partir de los LSP
recibidos). Este módulo NO reimplementa flooding ni dijkstra: los importa
y reutiliza (ver requisito de modularidad de la guía).

Un LSP (Link State Packet) es el payload de un paquete `type: info`:
    {"origin": "A", "seq": 7, "neighbors": {"B": 4, "C": 1}}

Regla de frescura: un LSP con `seq` menor o igual al último visto de ese
`origin` se descarta (ni se aplica, ni se reenvía, ni dispara recálculo).
Esto evita procesar/propagar LSPs viejos o repetidos indefinidamente.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from router.algorithms.dijkstra import RouteEntry, build_routing_table


@dataclass
class LspEntry:
    seq: int
    neighbors: dict


class LinkStateDatabase:
    """Almacena el último LSP conocido de cada origen."""

    def __init__(self) -> None:
        self._entries: dict[str, LspEntry] = {}

    def update(self, origin: str, seq: int, neighbors: dict) -> bool:
        """Aplica el LSP si es más nuevo que el almacenado. Devuelve True si se aplicó."""
        current = self._entries.get(origin)
        if current is not None and seq <= current.seq:
            return False  # LSP viejo o repetido: se ignora
        self._entries[origin] = LspEntry(seq=seq, neighbors=dict(neighbors))
        return True

    def get_seq(self, origin: str) -> int:
        entry = self._entries.get(origin)
        return entry.seq if entry else -1

    def known_origins(self) -> list:
        return list(self._entries.keys())

    def to_edges(self) -> dict:
        """Adyacencia lista para pasar a `dijkstra.build_routing_table`."""
        return {origin: dict(entry.neighbors) for origin, entry in self._entries.items()}


class LsrRoutingEngine:
    """Orquesta LSDB + Dijkstra para un nodo operando en modo `lsr`."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self.lsdb = LinkStateDatabase()
        self.table: dict = {}
        self._own_seq = 0

    def next_own_seq(self) -> int:
        self._own_seq += 1
        return self._own_seq

    def apply_lsp(self, origin: str, seq: int, neighbors: dict) -> bool:
        """Aplica un LSP recibido (o propio). Si es nuevo, recalcula la tabla.

        Devuelve True si el LSP era nuevo (y por lo tanto debe re-flood-earse).
        """
        applied = self.lsdb.update(origin, seq, neighbors)
        if applied:
            self._recompute()
        return applied

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
