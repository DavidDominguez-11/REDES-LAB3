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
        ok = _wait_until(lambda: nodes["A"].routing_engine.next_hop("E") == "C", timeout=6.0)
        assert ok, f"la red de configs reales no convergió: {nodes['A'].list_routes()}"
        assert nodes["A"].routing_engine.routes()["E"].cost == 7
    finally:
        for node in nodes.values():
            node.stop()
