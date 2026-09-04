"""Pruebas de integración con procesos (hilos) reales y sockets TCP reales
en localhost. No requieren la red del aula.
"""
from __future__ import annotations

import socket
import time
from dataclasses import replace
from pathlib import Path

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
            node_id=nid, host="127.0.0.1", port=ports[nid], mode="lsr", neighbors=neighbors, params=params,
            addresses={name: f"127.0.0.1:{port}" for name, port in ports.items()}
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
            node_id=nid, host="127.0.0.1", port=ports[nid], mode="flooding", neighbors=neighbors, params=params,
            addresses={name: f"127.0.0.1:{port}" for name, port in ports.items()}
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
        ok = _wait_until(lambda: nodes["A"].list_routes().get("E") is not None and nodes["A"].list_routes()["E"].next_hop == "C", timeout=5.0)
        assert ok, f"no convergió a tiempo, tabla actual: {nodes['A'].list_routes()}"
        entry = nodes["A"].list_routes().get("E")
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
        assert _wait_until(lambda: nodes["A"].list_routes().get("E") is not None and nodes["A"].list_routes()["E"].next_hop == "C", timeout=5.0)
        nodes["A"].send_message("E", "hola E desde A")
        assert _wait_until(lambda: len(delivered) == 1, timeout=3.0)
        pkt = delivered[0]
        assert pkt.payload == "hola E desde A"
        # Traza de saltos: se originó en A y se reenvió por C antes de llegar a E
        assert pkt.header("trace") == [nodes["A"].address, nodes["C"].address]
        assert pkt.from_ == nodes["A"].address
        assert pkt.header("via") == nodes["C"].address
    finally:
        _stop_all(nodes)


def test_dijkstra_static_addresses_deliver_end_to_end():
    topology = str(Path(__file__).resolve().parents[2] / "config/topologies/local_test_5nodes.json")
    configs = {nid: replace(cfg, mode="dijkstra", topology_file=topology)
               for nid, cfg in _build_lsr_configs().items()}
    nodes = _start_all(configs)
    delivered = []
    nodes["E"].forwarding_engine._on_message_delivered = delivered.append
    try:
        assert nodes["A"].list_routes()["E"].cost == 7
        nodes["A"].send_message("E", "Dijkstra con direcciones")
        assert _wait_until(lambda: len(delivered) == 1)
        assert delivered[0].from_ == nodes["A"].address
        assert delivered[0].header("trace") == [nodes["A"].address, nodes["C"].address]
    finally:
        _stop_all(nodes)


def test_neighbor_cost_change_reannounces_decimal_lsp():
    nodes = _start_all(_build_lsr_configs())
    try:
        assert _wait_until(lambda: all(len(n.list_routes()) == 4 for n in nodes.values()))
        nodes["A"].update_neighbor_cost("C", 1.5)
        assert nodes["A"].list_routes()["E"].cost == 7.5

        def propagated():
            lsp = {origin: links for origin, _, links in nodes["E"].routing_engine.lsdb_snapshot()}
            return lsp.get(nodes["A"].address, {}).get(nodes["C"].address) == 1.5

        assert _wait_until(propagated)
    finally:
        _stop_all(nodes)


def test_flooding_message_reaches_destination_and_stabilizes_without_loop():
    configs = _build_flooding_configs()
    nodes = _start_all(configs)
    delivered = []
    nodes["E"].forwarding_engine._on_message_delivered = lambda pkt: delivered.append(pkt)

    # Solo se cuentan los paquetes `message`: por el mismo enlace viaja el
    # tráfico de health check (hello/echo), que es periódico e independiente
    # del flooding y ensuciaría la medición del número de reenvíos.
    send_counts: dict = {nid: 0 for nid in configs}
    for nid, node in nodes.items():
        original_send = node._send_to_neighbor

        def wrapped(neighbor_id, packet, _nid=nid, _orig=original_send):
            if packet.type == "message":
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
        # Cota: con 5 nodos y 8 enlaces, cada nodo reenvía a lo sumo una vez por
        # vecino (gracias al dedup) y E, que es el destino, no reenvía. El
        # máximo teórico es 2 (A) + 3 (B) + 3 (C) + 2 (D) = 10 envíos.
        assert snapshot_1 <= 10, f"reenvíos inesperadamente altos ({snapshot_1}) para una sola difusión"
    finally:
        _stop_all(nodes)


def test_route_changes_after_simulated_neighbor_down_and_recovers():
    configs = _build_lsr_configs()
    nodes = _start_all(configs)
    try:
        assert _wait_until(lambda: nodes["A"].list_routes().get("E") is not None and nodes["A"].list_routes()["E"].next_hop == "C", timeout=5.0)
        assert nodes["A"].list_routes()["E"].cost == 7

        # Simula la caída del nodo C (vecino de A en la ruta óptima)
        nodes["C"].stop()

        def rerouted():
            entry = nodes["A"].list_routes().get("E")
            return entry is not None and entry.next_hop != "C"

        assert _wait_until(rerouted, timeout=6.0), f"no recalculó tras la caída: {nodes['A'].list_routes()}"
        entry = nodes["A"].list_routes()["E"]
        assert entry.next_hop == "B"
        assert entry.cost == 12  # A-B-D-E = 4+5+3, sin pasar por C

        # Recuperación: se levanta un nuevo proceso lógico para C con la misma config
        nodes["C"] = Node(configs["C"])
        nodes["C"].start()

        def recovered():
            entry = nodes["A"].list_routes().get("E")
            return entry is not None and entry.next_hop == "C" and entry.cost == 7

        assert _wait_until(recovered, timeout=6.0), f"no se recuperó la ruta óptima: {nodes['A'].list_routes()}"
    finally:
        _stop_all(nodes)


# Topología en LÍNEA A-B-C-D-E: a diferencia de la topología casi completa de
# arriba, aquí ningún nodo es vecino de todos, así que un LSP que no se propaga
# deja huecos reales en la LSDB en vez de quedar disimulado por la redundancia.
LINE_EDGES = {
    "A": {"B": 1},
    "B": {"A": 1, "C": 1},
    "C": {"B": 1, "D": 1},
    "D": {"C": 1, "E": 1},
    "E": {"D": 1},
}


def _build_line_lsr_configs() -> dict:
    ports = {nid: _free_port() for nid in LINE_EDGES}
    params = NodeParams(
        initial_ttl=8,
        hello_interval_sec=0.15,
        hello_timeout_sec=0.1,
        hello_max_failures=2,
        dedup_cache_ttl_sec=30.0,
        lsp_refresh_interval_sec=0.5,
    )
    return {
        nid: NodeConfig(
            node_id=nid,
            host="127.0.0.1",
            port=ports[nid],
            mode="lsr",
            neighbors=[
                NeighborConfig(other_id, "127.0.0.1", ports[other_id], cost)
                for other_id, cost in neighbor_costs.items()
            ],
            params=params,
            addresses={name: f"127.0.0.1:{port}" for name, port in ports.items()},
        )
        for nid, neighbor_costs in LINE_EDGES.items()
    }


def test_late_joining_node_converges_to_full_topology():
    """Un nodo que se levanta tarde debe terminar conociendo toda la red.

    El flooding solo reenvía un LSP en el instante en que llega, así que sin
    reanuncio periódico (ni volcado de LSDB al reaparecer un vecino) el nodo
    tardío nunca recibe los LSP difundidos antes de existir y su LSDB queda
    incompleta para siempre. En el aula los nodos se levantan en momentos
    distintos, así que este es el caso normal, no el excepcional.
    """
    configs = _build_line_lsr_configs()
    nodes = {nid: Node(configs[nid]) for nid in ["A", "B", "C", "D"]}
    for node in nodes.values():
        node.start()
    try:
        assert _wait_until(lambda: nodes["D"].list_routes().get("A") is not None and nodes["D"].list_routes()["A"].next_hop == "C", timeout=6.0)

        # E entra tarde, cuando el resto de la red ya difundió sus LSP.
        nodes["E"] = Node(configs["E"])
        nodes["E"].start()

        def e_conoce_toda_la_red():
            return set(nodes["E"].routing_engine.known_lsp_origins()) == {n.address for n in nodes.values()}

        assert _wait_until(e_conoce_toda_la_red, timeout=8.0), (
            f"LSDB incompleta en E: {sorted(nodes['E'].routing_engine.known_lsp_origins())}"
        )
        ruta_a_a = nodes["E"].list_routes()["A"]
        assert ruta_a_a.next_hop == "D"
        assert ruta_a_a.cost == 4  # E-D-C-B-A

        # Y la ruta debe servir de verdad, extremo a extremo.
        entregados = []
        nodes["A"].forwarding_engine._on_message_delivered = lambda pkt: entregados.append(pkt)
        nodes["E"].send_message("A", "hola A desde E")
        assert _wait_until(lambda: len(entregados) == 1, timeout=4.0)
        assert entregados[0].payload == "hola A desde E"
    finally:
        _stop_all(nodes)
