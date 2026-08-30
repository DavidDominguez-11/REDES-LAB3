"""Modelos de configuración. Todo lo variable (IPs, puertos, vecinos, costos,
intervalos, timeouts) vive en archivos JSON externos -- nunca hardcodeado."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NeighborConfig:
    node_id: str
    host: str
    port: int
    cost: int


@dataclass(frozen=True)
class NodeParams:
    initial_ttl: int = 5
    hello_interval_sec: float = 2.0
    hello_timeout_sec: float = 1.0
    hello_max_failures: int = 3
    dedup_cache_ttl_sec: float = 30.0
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


@dataclass(frozen=True)
class Topology:
    nodes: list  # list[str]
    edges: dict  # dict[str, dict[str, int]] adyacencia con costo, simétrica

    def cost(self, a: str, b: str) -> int | None:
        return self.edges.get(a, {}).get(b)
