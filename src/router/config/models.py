"""Modelos de configuración. Todo lo variable (IPs, puertos, vecinos, costos,
intervalos, timeouts) vive en archivos JSON externos -- nunca hardcodeado."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NeighborConfig:
    node_id: str
    host: str
    port: int
    cost: float


@dataclass(frozen=True)
class NodeParams:
    initial_ttl: int = 16
    hello_interval_sec: float = 2.0
    hello_timeout_sec: float = 1.0
    hello_max_failures: int = 3
    dedup_cache_ttl_sec: float = 30.0
    # Cada cuánto reanuncia un nodo LSR su propio LSP. Es un refresco local, no
    # parte del formato del protocolo: ver Node._routing_loop.
    lsp_refresh_interval_sec: float = 10.0
    log_level: str = "INFO"


@dataclass(frozen=True)
class NodeConfig:
    node_id: str
    host: str
    port: int
    mode: str  # "dijkstra" | "flooding" | "lsr"
    neighbors: list = field(default_factory=list)  # list[NeighborConfig]
    params: NodeParams = field(default_factory=NodeParams)
    topology_file: str | None = None  # requerido solo en modo "dijkstra"
    network_port: int = 5000
    advertised_host: str | None = None
    addresses: dict = field(default_factory=dict)  # alias -> IP:puerto, solo para configuración/CLI


@dataclass(frozen=True)
class Topology:
    nodes: list  # list[str]
    edges: dict  # dict[str, dict[str, float]] adyacencia con costo, simétrica

    def cost(self, a: str, b: str) -> float | None:
        return self.edges.get(a, {}).get(b)
