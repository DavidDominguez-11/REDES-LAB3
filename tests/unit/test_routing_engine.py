from pathlib import Path

import pytest

from router.config.loader import load_topology
from router.routing.engine import RoutingEngine

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY_PATH = REPO_ROOT / "config" / "topologies" / "local_test_5nodes.json"


def test_dijkstra_mode_computes_table_once_at_init():
    topo = load_topology(TOPOLOGY_PATH)
    engine = RoutingEngine("A", mode="dijkstra", static_topology=topo)
    assert engine.next_hop("E") == "C"
    assert engine.routes()["E"].cost == 7


def test_dijkstra_mode_requires_topology():
    with pytest.raises(ValueError):
        RoutingEngine("A", mode="dijkstra", static_topology=None)


def test_flooding_mode_has_no_routing_table():
    engine = RoutingEngine("A", mode="flooding")
    assert engine.next_hop("E") is None
    assert engine.routes() == {}


def test_lsr_mode_updates_via_apply_lsp():
    engine = RoutingEngine("A", mode="lsr")
    assert engine.next_hop("C") is None
    engine.apply_lsp("A", 1, {"C": 1})
    assert engine.next_hop("C") == "C"


def test_apply_lsp_invalid_outside_lsr_mode():
    engine = RoutingEngine("A", mode="flooding")
    with pytest.raises(RuntimeError):
        engine.apply_lsp("A", 1, {})
