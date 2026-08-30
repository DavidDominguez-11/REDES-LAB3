"""Dijkstra sobre una topología completa (nodos + aristas con costo).

Usado directamente en modo `dijkstra` (topología estática de configuración)
y reutilizado dentro de `lsr.py` (topología reconstruida a partir de LSPs).
No conoce nada de sockets ni de cómo se obtuvo la topología: solo recibe un
`Topology` (o un dict de adyacencia equivalente) y calcula rutas.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteEntry:
    destination: str
    next_hop: str
    cost: int


def shortest_paths(source: str, edges: dict) -> dict:
    """Dijkstra clásico. `edges` es dict[node] -> dict[neighbor] -> cost (no dirigido).

    Devuelve dict[node] -> (cost, path) donde `path` es la lista de nodos
    desde `source` hasta `node`, ambos inclusive.
    """
    if source not in edges:
        raise ValueError(f"El nodo origen '{source}' no está en la topología")

    distances = {node: float("inf") for node in edges}
    distances[source] = 0
    previous: dict = {source: None}
    visited = set()
    heap = [(0, source)]

    while heap:
        dist, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        for neighbor, cost in edges.get(node, {}).items():
            if neighbor in visited:
                continue
            new_dist = dist + cost
            if new_dist < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_dist
                previous[neighbor] = node
                heapq.heappush(heap, (new_dist, neighbor))

    result = {}
    for node, dist in distances.items():
        if dist == float("inf"):
            continue
        path = _reconstruct_path(previous, source, node)
        result[node] = (dist, path)
    return result


def _reconstruct_path(previous: dict, source: str, target: str) -> list:
    path = [target]
    while path[-1] != source:
        prev = previous.get(path[-1])
        if prev is None:
            break
        path.append(prev)
    path.reverse()
    return path


def build_routing_table(source: str, edges: dict) -> dict:
    """Devuelve dict[destino] -> RouteEntry(next_hop, cost), sin incluir `source`."""
    paths = shortest_paths(source, edges)
    table = {}
    for dest, (cost, path) in paths.items():
        if dest == source:
            continue
        next_hop = path[1] if len(path) > 1 else dest
        table[dest] = RouteEntry(destination=dest, next_hop=next_hop, cost=int(cost))
    return table
