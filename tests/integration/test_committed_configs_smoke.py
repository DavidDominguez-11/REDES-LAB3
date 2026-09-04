"""Smoke test de los archivos de configuración reales del repo (los que se
usarían el día de la demo), no configs construidos en memoria como en
test_node_network.py. Verifica que cargan y que los 5 nodos, tal cual están
committeados, forman una red funcional en localhost.
"""
from __future__ import annotations

import time
from pathlib import Path

from router.node import Node

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config" / "local_test_5nodes"


def _wait_until(predicate, timeout=6.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_committed_local_test_5nodes_configs_form_a_working_network():
    nodes = {}
    for letter in ("A", "B", "C", "D", "E"):
        node = Node.from_config_path(str(CONFIG_DIR / f"node_{letter}.json"), repo_root=str(REPO_ROOT))
        nodes[letter] = node

    for node in nodes.values():
        node.start()

    try:
        ok = _wait_until(lambda: nodes["A"].list_routes().get("E") is not None and nodes["A"].list_routes()["E"].next_hop == "C", timeout=6.0)
        assert ok, f"la red de configs reales no convergió: {nodes['A'].list_routes()}"
        assert nodes["A"].list_routes()["E"].cost == 7
    finally:
        for node in nodes.values():
            node.stop()


LAB_CONFIG_DIR = REPO_ROOT / "config" / "lab_9nodes_local"
LAB_NODES = ("A", "B", "C", "D", "E", "F", "G", "H", "I")


def test_committed_lab_9nodes_configs_converge_and_deliver_end_to_end():
    """La topología de la Imagen 1 de la guía, levantada completa en localhost.

    A y H están en extremos opuestos del grafo (4 saltos, A-I-D-F-H, costo 12),
    así que sirve para comprobar convergencia y entrega end-to-end, no solo
    entre vecinos directos.
    """
    nodes = {
        letter: Node.from_config_path(str(LAB_CONFIG_DIR / f"node_{letter}.json"), repo_root=str(REPO_ROOT))
        for letter in LAB_NODES
    }
    for node in nodes.values():
        node.start()

    try:
        def todos_convergieron():
            # Se espera a TODOS, no solo al origen: un nodo intermedio que
            # todavía no tiene ruta descarta el mensaje al reenviarlo.
            return all(set(n.list_routes()) == set(LAB_NODES) - {letter} for letter, n in nodes.items())

        assert _wait_until(todos_convergieron, timeout=15.0), (
            "la red de 9 nodos no convergió: "
            + str({letter: sorted(n.list_routes()) for letter, n in nodes.items()})
        )

        ruta_a_h = nodes["A"].list_routes()["H"]
        assert ruta_a_h.next_hop == "I"
        assert ruta_a_h.cost == 12  # A-I-D-F-H = 1+6+1+4

        entregados = []
        nodes["H"].forwarding_engine._on_message_delivered = lambda pkt: entregados.append(pkt)
        nodes["A"].send_message("H", "mensaje de punta a punta")
        assert _wait_until(lambda: len(entregados) == 1, timeout=6.0), "el mensaje no llegó a H"
        assert entregados[0].payload == "mensaje de punta a punta"
        assert entregados[0].header("trace") == [nodes[n].address for n in ("A", "I", "D", "F")]
        assert entregados[0].from_ == nodes["A"].address
    finally:
        for node in nodes.values():
            node.stop()
