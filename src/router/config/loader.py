"""Carga de configuración desde archivos JSON.

Ver config/example_node.json y config/topologies/local_test_5nodes.json
como referencia de formato.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from router.config.models import NeighborConfig, NodeConfig, NodeParams, Topology

VALID_MODES = {"dijkstra", "flooding", "lsr"}


class ConfigError(ValueError):
    """Error de configuración: JSON inválido o campos faltantes/incorrectos."""


def _cost(value) -> float:
    try:
        cost = float(value)
    except (ValueError, TypeError) as exc:
        raise ConfigError(f"Costo inválido: {value!r}") from exc
    if isinstance(value, bool) or not math.isfinite(cost) or cost < 0:
        raise ConfigError("Los costos deben ser finitos y no negativos")
    return cost


def _require(data: dict, key: str, ctx: str):
    if key not in data:
        raise ConfigError(f"Falta el campo requerido '{key}' en {ctx}")
    return data[key]


def load_node_config(path: str | Path) -> NodeConfig:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON inválido en {path}: {exc}") from exc
    except FileNotFoundError as exc:
        raise ConfigError(f"No se encontró el archivo de configuración: {path}") from exc

    node_id = _require(raw, "node_id", str(path))
    listen = _require(raw, "listen", str(path))
    host = _require(listen, "host", f"listen de {path}")
    network_port = int(raw.get("network_port", 5000))
    port = listen.get("port", network_port)
    mode = _require(raw, "mode", str(path))
    if mode not in VALID_MODES:
        raise ConfigError(f"mode inválido '{mode}' en {path}; debe ser uno de {VALID_MODES}")

    neighbors = []
    for n in raw.get("neighbors", []):
        for key in ("node_id", "host", "cost"):
            _require(n, key, f"neighbors de {path}")
        neighbors.append(NeighborConfig(n["node_id"], n["host"], int(n.get("port", network_port)), _cost(n["cost"])))

    params_raw = raw.get("params", {})
    default_params = NodeParams()
    params = NodeParams(
        initial_ttl=int(params_raw.get("initial_ttl", default_params.initial_ttl)),
        hello_interval_sec=float(params_raw.get("hello_interval_sec", default_params.hello_interval_sec)),
        hello_timeout_sec=float(params_raw.get("hello_timeout_sec", default_params.hello_timeout_sec)),
        hello_max_failures=int(params_raw.get("hello_max_failures", default_params.hello_max_failures)),
        dedup_cache_ttl_sec=float(params_raw.get("dedup_cache_ttl_sec", default_params.dedup_cache_ttl_sec)),
        lsp_refresh_interval_sec=float(
            params_raw.get("lsp_refresh_interval_sec", default_params.lsp_refresh_interval_sec)
        ),
        log_level=str(params_raw.get("log_level", default_params.log_level)),
    )

    if not 1 <= int(port) <= 65535 or not 1 <= network_port <= 65535 or any(
        not 1 <= n.port <= 65535 for n in neighbors
    ):
        raise ConfigError("Los puertos deben estar entre 1 y 65535")
    if params.initial_ttl <= 0 or params.hello_max_failures <= 0:
        raise ConfigError("TTL y hello_max_failures deben ser positivos")
    intervals = (params.hello_interval_sec, params.hello_timeout_sec,
                 params.dedup_cache_ttl_sec, params.lsp_refresh_interval_sec)
    if any(not math.isfinite(v) or v <= 0 for v in intervals):
        raise ConfigError("Los intervalos deben ser positivos y finitos")
    if params.hello_timeout_sec >= params.hello_interval_sec:
        raise ConfigError("hello_timeout_sec debe ser menor que hello_interval_sec")
    if params.lsp_refresh_interval_sec >= 30:
        raise ConfigError("El refresco LSP debe ser menor que su expiración (30 s)")
    topology_file = raw.get("topology_file")
    if mode == "dijkstra" and not topology_file:
        raise ConfigError(
            f"mode='dijkstra' en {path} requiere 'topology_file' con la topología estática"
        )

    return NodeConfig(
        node_id=node_id,
        host=host,
        port=int(port),
        mode=mode,
        neighbors=neighbors,
        params=params,
        topology_file=topology_file,
        network_port=network_port,
        advertised_host=raw.get("advertised_host"),
        addresses=raw.get("addresses", {}),
    )


def load_topology(path: str | Path) -> Topology:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON inválido en {path}: {exc}") from exc
    except FileNotFoundError as exc:
        raise ConfigError(f"No se encontró el archivo de topología: {path}") from exc

    nodes = _require(raw, "nodes", str(path))
    links = _require(raw, "links", str(path))
    if not isinstance(nodes, list):
        raise ConfigError(f"'nodes' debe ser una lista en {path}")

    edges: dict = {n: {} for n in nodes}
    for link in links:
        for key in ("a", "b", "cost"):
            _require(link, key, f"links de {path}")
        a, b, cost = link["a"], link["b"], _cost(link["cost"])
        if a not in edges or b not in edges:
            raise ConfigError(f"Link {a}-{b} referencia un nodo no declarado en 'nodes'")
        edges[a][b] = cost
        edges[b][a] = cost  # topología no dirigida

    return Topology(nodes=list(nodes), edges=edges)
