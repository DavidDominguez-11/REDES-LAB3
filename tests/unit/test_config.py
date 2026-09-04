import json

import pytest

from router.config.loader import ConfigError, load_node_config, load_topology

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


def test_load_example_node_config():
    cfg = load_node_config(REPO_ROOT / "config" / "example_node.json")
    assert cfg.node_id == "A"
    assert cfg.host == "0.0.0.0"
    assert cfg.advertised_host == "10.0.0.1"
    assert cfg.port == 5000
    assert cfg.mode == "lsr"
    assert len(cfg.neighbors) == 2
    assert cfg.neighbors[0].node_id == "B"
    assert cfg.neighbors[0].cost == 4.8
    assert cfg.params.initial_ttl == 16
    assert cfg.params.hello_interval_sec == 2.0


def test_load_local_test_5nodes_configs():
    for node_id, port in [("A", 6000), ("B", 6001), ("C", 6002), ("D", 6003), ("E", 6004)]:
        cfg = load_node_config(REPO_ROOT / "config" / "local_test_5nodes" / f"node_{node_id}.json")
        assert cfg.node_id == node_id
        assert cfg.port == port
        assert cfg.mode == "lsr"


def test_load_topology_local_5nodes():
    topo = load_topology(REPO_ROOT / "config" / "topologies" / "local_test_5nodes.json")
    assert set(topo.nodes) == {"A", "B", "C", "D", "E"}
    assert topo.cost("A", "C") == 1
    assert topo.cost("C", "A") == 1  # simétrico
    assert topo.cost("A", "E") is None  # no son vecinos directos


def test_default_network_port_and_missing_neighbor_port(tmp_path):
    from router.node import Node

    path = tmp_path / "node.json"
    path.write_text(json.dumps({
        "node_id": "A", "listen": {"host": "0.0.0.0"},
        "advertised_host": "10.0.0.1", "mode": "lsr",
        "neighbors": [{"node_id": "B", "host": "10.0.0.2", "cost": 4.8}]
    }))
    config = load_node_config(path)
    node = Node(config)
    assert node.address == "10.0.0.1:5000"
    assert config.neighbors[0].port == 5000
    assert node.addresses.resolve("10.0.0.2") == node.addresses.resolve("B")
    assert config.params.initial_ttl == 16


def test_missing_required_field_raises(tmp_path):
    bad = tmp_path / "bad_node.json"
    bad.write_text(json.dumps({"node_id": "A"}))  # falta listen, mode
    with pytest.raises(ConfigError):
        load_node_config(bad)


def test_invalid_mode_raises(tmp_path):
    bad = tmp_path / "bad_mode.json"
    bad.write_text(json.dumps({
        "node_id": "A", "listen": {"host": "127.0.0.1", "port": 6000}, "mode": "dvr",
    }))
    with pytest.raises(ConfigError):
        load_node_config(bad)


def test_dijkstra_mode_requires_topology_file(tmp_path):
    bad = tmp_path / "no_topo.json"
    bad.write_text(json.dumps({
        "node_id": "A", "listen": {"host": "127.0.0.1", "port": 6000}, "mode": "dijkstra",
    }))
    with pytest.raises(ConfigError):
        load_node_config(bad)


def test_invalid_json_raises(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text("{not valid json")
    with pytest.raises(ConfigError):
        load_node_config(bad)


def test_topology_link_with_unknown_node_raises(tmp_path):
    bad = tmp_path / "bad_topo.json"
    bad.write_text(json.dumps({
        "nodes": ["A", "B"],
        "links": [{"a": "A", "b": "Z", "cost": 1}],
    }))
    with pytest.raises(ConfigError):
        load_topology(bad)


# --------------------------------------------------------------------------- #
# Override de modo desde la CLI: la guía pide poder levantar la red en
# 'flooding' o en 'dijkstra' de forma independiente de su uso dentro de LSR.
# --------------------------------------------------------------------------- #
def test_cli_mode_override_cambia_el_modo(tmp_path, monkeypatch, capsys):
    from router import cli

    cfg_path = tmp_path / "node.json"
    cfg_path.write_text(
        json.dumps(
            {
                "node_id": "A",
                "listen": {"host": "127.0.0.1", "port": 6000},
                "mode": "lsr",
                "neighbors": [],
                "topology_file": "config/topologies/local_test_5nodes.json",
            }
        ),
        encoding="utf-8",
    )

    capturado = {}

    class NodeFalso:
        """Evita abrir sockets: solo interesa con qué config se construye el nodo."""

        def __init__(self, cfg, repo_root="."):
            capturado["cfg"] = cfg

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(cli, "Node", NodeFalso)
    monkeypatch.setattr(cli, "run_repl", lambda node: None)

    assert cli.main(["--config", str(cfg_path), "--mode", "flooding"]) == 0
    assert capturado["cfg"].mode == "flooding"
    assert capturado["cfg"].node_id == "A"


def test_cli_mode_dijkstra_sin_topologia_falla(tmp_path, capsys):
    from router import cli

    cfg_path = tmp_path / "node.json"
    cfg_path.write_text(
        json.dumps(
            {
                "node_id": "A",
                "listen": {"host": "127.0.0.1", "port": 6000},
                "mode": "flooding",
                "neighbors": [],
            }
        ),
        encoding="utf-8",
    )

    assert cli.main(["--config", str(cfg_path), "--mode", "dijkstra"]) == 1
    assert "topology_file" in capsys.readouterr().err
