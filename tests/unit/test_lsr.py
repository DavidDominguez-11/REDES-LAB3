from pathlib import Path

from router.algorithms.lsr import LinkStateDatabase, LsrRoutingEngine
from router.config.loader import load_topology

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY_PATH = REPO_ROOT / "config" / "topologies" / "local_test_5nodes.json"


def test_lsdb_applies_first_lsp():
    lsdb = LinkStateDatabase()
    assert lsdb.update("A", seq=1, neighbors={"B": 4, "C": 1}) is True
    assert lsdb.get_seq("A") == 1


def test_lsdb_ignores_stale_or_duplicate_seq():
    lsdb = LinkStateDatabase()
    lsdb.update("A", seq=5, neighbors={"B": 4})
    assert lsdb.update("A", seq=5, neighbors={"B": 4}) is False  # duplicado
    assert lsdb.update("A", seq=3, neighbors={"B": 99}) is False  # viejo
    assert lsdb.get_seq("A") == 5


def test_lsdb_applies_newer_seq_and_replaces_neighbors():
    lsdb = LinkStateDatabase()
    lsdb.update("A", seq=1, neighbors={"B": 4})
    assert lsdb.update("A", seq=2, neighbors={"B": 4, "C": 1}) is True
    assert lsdb.to_edges()["A"] == {"B": 4, "C": 1}


def test_lsr_engine_recomputes_table_on_new_lsp():
    engine = LsrRoutingEngine("A")
    assert engine.apply_lsp("A", 1, {"C": 1}) is True
    assert engine.next_hop("C") == "C"
    assert engine.next_hop("E") is None  # aún no se conoce el resto de la red


def test_lsr_engine_ignores_stale_lsp_and_does_not_recompute():
    engine = LsrRoutingEngine("A")
    engine.apply_lsp("A", 5, {"C": 1})
    table_before = dict(engine.table)
    applied = engine.apply_lsp("A", 2, {"C": 999})  # más viejo, cambia costo pero debe ignorarse
    assert applied is False
    assert engine.table == table_before
    assert engine.next_hop("C") == "C"


def test_lsr_converges_to_same_table_as_static_dijkstra():
    """Al recibir el LSP de cada uno de los 5 nodos, LSR debe llegar a la
    misma tabla que Dijkstra con la topología estática completa."""
    topo = load_topology(TOPOLOGY_PATH)

    engine = LsrRoutingEngine("A")
    for origin in topo.nodes:
        engine.apply_lsp(origin, seq=1, neighbors=topo.edges[origin])

    from router.algorithms.dijkstra import build_routing_table

    expected = build_routing_table("A", topo.edges)

    assert set(engine.table.keys()) == set(expected.keys())
    for dest, entry in expected.items():
        assert engine.table[dest].cost == entry.cost
        assert engine.table[dest].next_hop == entry.next_hop
    assert engine.next_hop("E") == "C"
    assert engine.route_entry("E").cost == 7
