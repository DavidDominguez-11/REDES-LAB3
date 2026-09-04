import json

import pytest

from router.config.loader import ConfigError, load_node_config, load_topology

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


def test_load_example_node_config():
    cfg = load_node_config(REPO_ROOT / "config" / "node_template.json")
    assert cfg.node_id == "A"
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 6000
    assert cfg.mode == "lsr"
    assert len(cfg.neighbors) == 2
    assert cfg.neighbors[0].node_id == "B"
    assert cfg.neighbors[0].cost == 4
    assert cfg.params.initial_ttl == 5
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
