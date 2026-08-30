"""Pruebas de integración con procesos (hilos) reales y sockets TCP reales
en localhost. No requieren la red del aula.
"""
from __future__ import annotations

import socket
import time

from router.config.models import NeighborConfig, NodeConfig, NodeParams
from router.node import Node

TOPOLOGY_EDGES = {
    "A": {"B": 4, "C": 1},
    "B": {"A": 4, "C": 2, "D": 5, "E": 10},
    "C": {"A": 1, "B": 2, "D": 8, "E": 6},
    "D": {"B": 5, "C": 8, "E": 3},
    "E": {"B": 10, "C": 6, "D": 3},
}


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _build_lsr_configs(fast_health_check: bool = True) -> dict:
    ports = {nid: _free_port() for nid in TOPOLOGY_EDGES}
    params = NodeParams(
        initial_ttl=5,
        hello_interval_sec=0.15 if fast_health_check else 1.0,
        hello_timeout_sec=0.1 if fast_health_check else 0.5,
        hello_max_failures=2,
        dedup_cache_ttl_sec=30.0,
    )
    configs = {}
    for nid, neighbor_costs in TOPOLOGY_EDGES.items():
        neighbors = [
            NeighborConfig(other_id, "127.0.0.1", ports[other_id], cost)
            for other_id, cost in neighbor_costs.items()
        ]
        configs[nid] = NodeConfig(
            node_id=nid, host="127.0.0.1", port=ports[nid], mode="lsr", neighbors=neighbors, params=params
        )
    return configs


def _build_flooding_configs() -> dict:
    ports = {nid: _free_port() for nid in TOPOLOGY_EDGES}
    params = NodeParams(initial_ttl=5, dedup_cache_ttl_sec=30.0)
    configs = {}
    for nid, neighbor_costs in TOPOLOGY_EDGES.items():
        neighbors = [
            NeighborConfig(other_id, "127.0.0.1", ports[other_id], cost)
            for other_id, cost in neighbor_costs.items()
        ]
        configs[nid] = NodeConfig(
            node_id=nid, host="127.0.0.1", port=ports[nid], mode="flooding", neighbors=neighbors, params=params
        )
    return configs


def _start_all(configs: dict) -> dict:
    nodes = {nid: Node(cfg) for nid, cfg in configs.items()}
    for node in nodes.values():
        node.start()
    return nodes


def _stop_all(nodes: dict) -> None:
    for node in nodes.values():
        node.stop()


def _wait_until(predicate, timeout=5.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_lsr_converges_and_routes_optimally_a_to_e():
    configs = _build_lsr_configs()
    nodes = _start_all(configs)
    try:
        ok = _wait_until(lambda: nodes["A"].routing_engine.next_hop("E") == "C", timeout=5.0)
        assert ok, f"no convergió a tiempo, tabla actual: {nodes['A'].list_routes()}"
        entry = nodes["A"].routing_engine.routes().get("E")
        assert entry.cost == 7
        assert entry.next_hop == "C"
    finally:
        _stop_all(nodes)


def test_lsr_message_delivered_via_expected_route():
    configs = _build_lsr_configs()
    nodes = _start_all(configs)
    delivered = []
    nodes["E"].forwarding_engine._on_message_delivered = lambda pkt: delivered.append(pkt)
    try:
        assert _wait_until(lambda: nodes["A"].routing_engine.next_hop("E") == "C", timeout=5.0)
        nodes["A"].send_message("E", "hola E desde A")
        assert _wait_until(lambda: len(delivered) == 1, timeout=3.0)
        pkt = delivered[0]
        assert pkt.payload == "hola E desde A"
        # Traza de saltos: se originó en A y se reenvió por C antes de llegar a E
        assert pkt.headers[0]["hops"] == ["A", "C"]
    finally:
        _stop_all(nodes)


def test_flooding_message_reaches_destination_and_stabilizes_without_loop():
    configs = _build_flooding_configs()
    nodes = _start_all(configs)
    delivered = []
    nodes["E"].forwarding_engine._on_message_delivered = lambda pkt: delivered.append(pkt)

    send_counts: dict = {nid: 0 for nid in configs}
    for nid, node in nodes.items():
        original_send = node._send_to_neighbor

        def wrapped(neighbor_id, packet, _nid=nid, _orig=original_send):
            send_counts[_nid] += 1
            return _orig(neighbor_id, packet)

        node._send_to_neighbor = wrapped
        node.forwarding_engine._send_to_neighbor = wrapped

    try:
        nodes["A"].send_message("E", "flood hasta E")
        assert _wait_until(lambda: len(delivered) == 1, timeout=3.0)
        assert delivered[0].payload == "flood hasta E"

        time.sleep(0.3)  # deja asentar cualquier paquete todavía en tránsito
        snapshot_1 = sum(send_counts.values())
        time.sleep(0.5)  # ventana de silencio: si hubiera loop, el conteo seguiría creciendo
        snapshot_2 = sum(send_counts.values())
        assert snapshot_2 == snapshot_1, "el conteo de envíos siguió creciendo: posible loop de flooding"
        # Cota generosa: con 5 nodos y 8 enlaces, cada nodo reenvía a lo sumo una
        # vez por vecino (gracias al dedup); el número exacto depende del orden de
        # llegada, pero debe quedarse muy por debajo de una reinundación indefinida.
        assert snapshot_1 <= 20, f"reenvíos inesperadamente altos ({snapshot_1}) para una sola difusión"
    finally:
        _stop_all(nodes)


def test_route_changes_after_simulated_neighbor_down_and_recovers():
    configs = _build_lsr_configs()
    nodes = _start_all(configs)
    try:
        assert _wait_until(lambda: nodes["A"].routing_engine.next_hop("E") == "C", timeout=5.0)
        assert nodes["A"].routing_engine.routes()["E"].cost == 7

        # Simula la caída del nodo C (vecino de A en la ruta óptima)
        nodes["C"].stop()

        def rerouted():
            entry = nodes["A"].routing_engine.routes().get("E")
            return entry is not None and entry.next_hop != "C"

        assert _wait_until(rerouted, timeout=6.0), f"no recalculó tras la caída: {nodes['A'].list_routes()}"
        entry = nodes["A"].routing_engine.routes()["E"]
        assert entry.next_hop == "B"
        assert entry.cost == 12  # A-B-D-E = 4+5+3, sin pasar por C

        # Recuperación: se levanta un nuevo proceso lógico para C con la misma config
        nodes["C"] = Node(configs["C"])
        nodes["C"].start()

        def recovered():
            entry = nodes["A"].routing_engine.routes().get("E")
            return entry is not None and entry.next_hop == "C" and entry.cost == 7

        assert _wait_until(recovered, timeout=6.0), f"no se recuperó la ruta óptima: {nodes['A'].list_routes()}"
    finally:
        _stop_all(nodes)
