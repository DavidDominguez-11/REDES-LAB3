"""Motor de ruteo del nodo: expone una interfaz uniforme (`next_hop`,
`routes`) sin importar si el modo es `dijkstra` (tabla estática, calculada
una sola vez al iniciar, tal como pide la guía), `lsr` (tabla dinámica
basada en LSPs) o `flooding` (no hay tabla de ruteo; el reenvío se decide
paquete por paquete con las reglas de `algorithms/flooding.py`).
"""
from __future__ import annotations

from router.algorithms.dijkstra import RouteEntry, build_routing_table
from router.algorithms.lsr import LsrRoutingEngine
from router.config.models import Topology


class RoutingEngine:
    def __init__(self, node_id: str, mode: str, static_topology: Topology | None = None) -> None:
        self.node_id = node_id
        self.mode = mode
        self._static_table: dict = {}
        self._lsr: LsrRoutingEngine | None = None

        if mode == "dijkstra":
            if static_topology is None:
                raise ValueError("mode='dijkstra' requiere una topología estática")
            # Se calcula UNA sola vez al iniciar: la guía indica que este modo
            # es estático, aunque en la práctica se use dentro de LSR.
            self._static_table = build_routing_table(node_id, static_topology.edges)
        elif mode == "lsr":
            self._lsr = LsrRoutingEngine(node_id)
        elif mode == "flooding":
            pass  # sin tabla: el forwarding usa algorithms.flooding directamente
        else:
            raise ValueError(f"modo desconocido: {mode}")

    def next_hop(self, destination: str) -> str | None:
        if self.mode == "dijkstra":
            entry = self._static_table.get(destination)
        elif self.mode == "lsr":
            entry = self._lsr.route_entry(destination) if self._lsr else None
        else:
            return None
        return entry.next_hop if entry else None

    def routes(self) -> dict:
        """dict[destino] -> RouteEntry, para inspección (usado por la CLI)."""
        if self.mode == "dijkstra":
            return dict(self._static_table)
        if self.mode == "lsr" and self._lsr:
            return self._lsr.routes()
        return {}

    # --- Solo aplica en modo lsr ---
    def apply_lsp(self, origin: str, seq: int, neighbors: dict, age_s: float = 0) -> bool:
        if self._lsr is None:
            raise RuntimeError("apply_lsp solo es válido en modo 'lsr'")
        return self._lsr.apply_lsp(origin, seq, neighbors, age_s)

    def expire(self) -> list:
        return self._lsr.expire() if self._lsr else []

    def lsdb_snapshot_with_age(self) -> list:
        return self._lsr.snapshot_with_age() if self._lsr else []

    def next_own_seq(self) -> int:
        if self._lsr is None:
            raise RuntimeError("next_own_seq solo es válido en modo 'lsr'")
        return self._lsr.next_own_seq()

    def known_lsp_origins(self) -> list:
        if self._lsr is None:
            return []
        return self._lsr.known_origins()

    def lsdb_snapshot(self) -> list:
        """Copia de todos los LSP conocidos: [(origin, seq, neighbors), ...].

        La usa el forwarding para sincronizar la LSDB con un vecino que acaba
        de aparecer y que por lo tanto no recibió los LSP difundidos antes.
        Vacía fuera del modo `lsr`.
        """
        if self._lsr is None:
            return []
        return self._lsr.snapshot()
