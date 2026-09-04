import json

import pytest

from router.algorithms.dijkstra import build_routing_table
from router.algorithms.lsr import LsrRoutingEngine
from router.config.addressing import normalize_address
from router.forwarding.engine import parse_lsp_payload
from router.protocol.packet import Packet
from router.transport.ndjson import LineBuffer, encode_line
from tests.unit.test_forwarding_engine import _make_engine


def test_decimal_weights_choose_the_actual_shortest_path():
    routes = build_routing_table("A", {"A": {"B": 1.9, "C": 1.1}, "B": {"D": 0.2}, "C": {"D": 1.1}})
    assert routes["D"].cost == pytest.approx(2.1)
    assert routes["D"].next_hop == "B"


@pytest.mark.parametrize("neighbors", [
    {"10.0.0.2": "4.8"},
    [{"id": "10.0.0.2", "weight": 4.8}],
    [{"node": "10.0.0.2", "cost": "4.8"}],
])
@pytest.mark.parametrize("textual", [True, False])
def test_lsp_variants_normalize_addresses_without_truncating(neighbors, textual):
    payload = {"origin": "10.0.0.1", "seq": 7, "age_s": 2, "links": neighbors}
    if textual:
        payload = json.dumps(payload)
    assert parse_lsp_payload(payload, lambda v: normalize_address(v, 5000)) == (
        "10.0.0.1:5000", 7, {"10.0.0.2:5000": 4.8}, 2
    )


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True, "barato"])
def test_invalid_lsp_weights_do_not_enter_dijkstra(bad):
    assert parse_lsp_payload({"origin": "A", "seq": 1, "neighbors": {"B": bad, "C": 4.8}})[2] == {"C": 4.8}


def test_expiration_removes_routes_and_accepts_restarted_sequence():
    now = [0.0]
    engine = LsrRoutingEngine("A", clock=lambda: now[0])
    engine.apply_lsp("A", 1, {"B": 1})
    engine.apply_lsp("B", 100, {"C": 4.8})
    now[0] = 20
    engine.apply_lsp("A", 2, {"B": 1})
    assert not engine.apply_lsp("B", 100, {"C": 4.8})  # no renueva la recepción
    now[0] = 29.9
    assert engine.next_hop("C") == "B"
    now[0] = 30
    assert engine.expire() == ["B"]
    assert engine.next_hop("C") is None
    assert engine.apply_lsp("B", 1, {"C": 2.5})
    assert engine.route_entry("C").cost == 3.5


def test_snapshot_preserves_origin_sequence_and_elapsed_age():
    now = [0.0]
    engine = LsrRoutingEngine("A", clock=lambda: now[0])
    engine.apply_lsp("B", 7, {"C": 4.8}, age_s=2)
    now[0] = 3
    assert engine.snapshot_with_age() == [("B", 7, {"C": 4.8}, 5)]


def test_own_sequence_advances_past_snapshot_after_restart():
    engine = LsrRoutingEngine("A")
    engine.apply_lsp("A", 100, {"B": 1})
    assert engine.next_own_seq() == 101


@pytest.mark.parametrize("mode", ["lsr", "flooding"])
def test_ttl_zero_never_delivers_and_one_never_forwards(mode):
    delivered = []
    engine, _, routing, sent = _make_engine("B", mode, {"A": 1, "C": 1}, delivered.append)
    if mode == "lsr":
        routing.apply_lsp("B", 1, {"C": 1})
    for destination, ttl in [("B", 0), ("C", 1)]:
        engine.handle_packet(Packet(mode, "message", "A", destination, ttl, "hola"), "A")
    assert delivered == sent == []
    engine.handle_packet(Packet(mode, "message", "A", "B", 1, "hola"), "A")
    assert len(delivered) == 1


def test_lsp_identity_uses_origin_seq_and_expired_ttl_is_not_applied():
    engine, _, routing, sent = _make_engine("B", "lsr", {"A": 1, "C": 1})
    def info(seq, msg_id, ttl=16):
        return Packet("lsr", "info", "A", "*", ttl,
                      {"origin": "A", "seq": seq, "neighbors": [{"id": "B", "weight": 4.8}]}, id=msg_id)
    engine.handle_packet(info(1, "same"), "A")
    engine.handle_packet(info(1, "different"), "A")
    engine.handle_packet(info(2, "same"), "A")
    engine.handle_packet(info(3, "new", ttl=0), "A")
    assert len(sent) == 2
    assert routing.lsdb_snapshot()[0][1] == 2


def test_via_excludes_previous_hop_even_when_from_is_far_away():
    engine, _, _, sent = _make_engine("B", "flooding", {"A": 1, "C": 1})
    packet = Packet("flooding", "message", "Z", "D", 16, "hola", headers=[{"via": "A"}])
    engine.handle_packet(packet, from_neighbor_id="C")
    assert [n for n, _ in sent] == ["C"]
    forwarded = sent[0][1]
    assert forwarded.from_ == "Z"
    assert forwarded.header("via") == "B"
    assert forwarded.header("trace") == ["B"]


def test_oversized_line_is_discarded_until_delimiter_and_buffer_is_bounded(caplog):
    buffer = LineBuffer()
    assert buffer.feed(b"x" * 65536) == []
    assert buffer.pending_bytes() == 65536
    assert buffer.feed(b"x" * 65536) == []
    assert buffer.pending_bytes() == 0
    assert buffer.feed(b"discarded\n{}\n") == [b"{}"]
    assert "se descarta" in caplog.text
    assert LineBuffer().feed(b"x" * 65536 + b"\n") == [b"x" * 65536]


def test_outgoing_line_limit_is_measured_in_utf8_bytes():
    assert len(encode_line("á" * 32768)) == 65537
    with pytest.raises(ValueError):
        encode_line("á" * 32769)
