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
DEFAULT_PORT = 5000


class ConfigError(ValueError):
    """Error de configuración: JSON inválido o campos faltantes/incorrectos."""


def _require(data: dict, key: str, ctx: str):
    if key not in data:
        raise ConfigError(f"Falta el campo requerido '{key}' en {ctx}")
    return data[key]


def _cost(value, ctx: str) -> int | float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"costo inválido en {ctx}: {value!r}") from exc
    if not math.isfinite(result) or result < 0:
        raise ConfigError(f"costo inválido en {ctx}: {value!r}")
    return int(result) if result.is_integer() else result


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
    port = listen.get("port", DEFAULT_PORT)
    mode = _require(raw, "mode", str(path))
    if mode not in VALID_MODES:
        raise ConfigError(f"mode inválido '{mode}' en {path}; debe ser uno de {VALID_MODES}")

    neighbors = []
    for n in raw.get("neighbors", []):
        for key in ("node_id", "host", "cost"):
            _require(n, key, f"neighbors de {path}")
        neighbors.append(
            NeighborConfig(
                n["node_id"],
                n["host"],
                int(n.get("port", port)),
                _cost(n["cost"], f"neighbors de {path}"),
            )
        )

    params_raw = raw.get("params", {})
    default_params = NodeParams()
    params = NodeParams(
        initial_ttl=int(params_raw.get("initial_ttl", default_params.initial_ttl)),
        hello_interval_sec=float(params_raw.get("hello_interval_sec", default_params.hello_interval_sec)),
        hello_timeout_sec=float(params_raw.get("hello_timeout_sec", default_params.hello_timeout_sec)),
        hello_max_failures=int(params_raw.get("hello_max_failures", default_params.hello_max_failures)),
        dedup_cache_ttl_sec=float(params_raw.get("dedup_cache_ttl_sec", default_params.dedup_cache_ttl_sec)),
        lsp_interval_sec=float(params_raw.get("lsp_interval_sec", default_params.lsp_interval_sec)),
        lsp_expiry_sec=float(params_raw.get("lsp_expiry_sec", default_params.lsp_expiry_sec)),
        log_level=str(params_raw.get("log_level", default_params.log_level)),
    )

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
        a, b, cost = link["a"], link["b"], _cost(link["cost"], f"links de {path}")
        if a not in edges or b not in edges:
            raise ConfigError(f"Link {a}-{b} referencia un nodo no declarado en 'nodes'")
        edges[a][b] = cost
        edges[b][a] = cost  # topología no dirigida

    return Topology(nodes=list(nodes), edges=edges)
