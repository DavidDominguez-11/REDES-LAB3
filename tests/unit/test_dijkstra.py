from pathlib import Path

from router.algorithms.dijkstra import build_routing_table, shortest_paths
from router.config.loader import load_topology

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY_PATH = REPO_ROOT / "config" / "topologies" / "local_test_5nodes.json"


def _edges():
    return load_topology(TOPOLOGY_PATH).edges


def test_shortest_path_a_to_e_is_via_c():
    paths = shortest_paths("A", _edges())
    cost, path = paths["E"]
    assert cost == 7  # A-C(1) + C-E(6)
    assert path == ["A", "C", "E"]


def test_shortest_path_a_to_d():
    paths = shortest_paths("A", _edges())
    cost, path = paths["D"]
    # A-C-B-D = 1+2+5=8, A-C-D = 1+8=9 -> via B es mejor
    assert cost == 8
    assert path == ["A", "C", "B", "D"]


def test_routing_table_next_hops_from_a():
    table = build_routing_table("A", _edges())
    assert table["C"].next_hop == "C"
    assert table["C"].cost == 1
    assert table["E"].next_hop == "C"  # A->C->E
    assert table["E"].cost == 7
    assert table["B"].next_hop == "C"  # A-C-B(1+2=3) < A-B directo(4)
    assert table["B"].cost == 3


def test_routing_table_excludes_source():
    table = build_routing_table("A", _edges())
    assert "A" not in table


def test_alternate_route_when_direct_edge_removed():
    edges = _edges()
    # Simula caída del enlace C-E (se elimina en ambos sentidos)
    edges = {n: dict(neigh) for n, neigh in edges.items()}
    del edges["C"]["E"]
    del edges["E"]["C"]

    table = build_routing_table("A", edges)
    # Nueva ruta óptima esperada: A-C-B-D-E = 1+2+5+3 = 11
    assert table["E"].cost == 11
    assert table["E"].next_hop == "C"


def test_unreachable_node_not_in_table():
    edges = {"A": {"B": 1}, "B": {"A": 1}, "Z": {}}
    table = build_routing_table("A", edges)
    assert "Z" not in table
