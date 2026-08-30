import pytest

from router.protocol.factory import make_echo, make_hello, make_lsp, make_message
from router.protocol.packet import Packet, PacketValidationError


def test_round_trip_serialization():
    pkt = Packet(proto="flooding", type="message", from_="A", to="E", ttl=5, payload="hola")
    line = pkt.to_json()
    assert "\n" not in line
    restored = Packet.from_json(line)
    assert restored.proto == "flooding"
    assert restored.type == "message"
    assert restored.from_ == "A"
    assert restored.to == "E"
    assert restored.ttl == 5
    assert restored.payload == "hola"
    assert restored.id == pkt.id


def test_missing_required_field_raises():
    bad = '{"proto":"flooding","type":"message","from":"A","to":"E","ttl":5}'  # falta payload e id
    with pytest.raises(PacketValidationError):
        Packet.from_json(bad)


def test_invalid_json_raises():
    with pytest.raises(PacketValidationError):
        Packet.from_json("{esto no es json")


def test_empty_line_raises():
    with pytest.raises(PacketValidationError):
        Packet.from_json("   ")


def test_invalid_proto_raises():
    pkt_dict = {
        "version": 1, "id": "x", "proto": "dvr", "type": "message",
        "from": "A", "to": "B", "ttl": 5, "headers": [], "payload": "hi",
    }
    with pytest.raises(PacketValidationError):
        Packet.from_dict(pkt_dict)


def test_invalid_type_raises():
    pkt_dict = {
        "version": 1, "id": "x", "proto": "flooding", "type": "ack",
        "from": "A", "to": "B", "ttl": 5, "headers": [], "payload": "hi",
    }
    with pytest.raises(PacketValidationError):
        Packet.from_dict(pkt_dict)


def test_missing_version_defaults_to_1():
    pkt_dict = {
        "id": "x", "proto": "flooding", "type": "message",
        "from": "A", "to": "B", "ttl": 5, "headers": [], "payload": "hi",
    }
    pkt = Packet.from_dict(pkt_dict)
    assert pkt.version == 1


def test_ttl_decrement_does_not_mutate_original():
    pkt = Packet(proto="flooding", type="message", from_="A", to="E", ttl=3, payload="x")
    decremented = pkt.with_ttl_decremented()
    assert pkt.ttl == 3
    assert decremented.ttl == 2
    assert decremented.id == pkt.id  # el id no cambia al reenviar


def test_hop_trace_appends_without_mutating_original():
    pkt = make_message(proto="flooding", from_="A", to="E", text="hola", ttl=5)
    assert pkt.headers[0]["hops"] == ["A"]
    hopped = pkt.with_hop_appended("C")
    assert pkt.headers[0]["hops"] == ["A"]
    assert hopped.headers[0]["hops"] == ["A", "C"]


def test_make_hello_and_echo_payload_shape():
    hello = make_hello(proto="lsr", from_="A", to="B", seq=1)
    assert hello.type == "hello"
    assert hello.ttl == 1
    assert hello.payload["seq"] == 1
    assert "sent_at" in hello.payload

    echo = make_echo(proto="lsr", from_="B", to="A", hello_payload=hello.payload)
    assert echo.type == "echo"
    assert echo.payload["seq"] == 1
    assert echo.payload["sent_at"] == hello.payload["sent_at"]
    assert "echoed_at" in echo.payload


def test_make_lsp_payload_shape():
    lsp = make_lsp(from_="A", origin="A", seq=3, neighbors={"B": 4, "C": 1}, ttl=5)
    assert lsp.proto == "lsr"
    assert lsp.type == "info"
    assert lsp.to == "*"
    assert lsp.payload == {"origin": "A", "seq": 3, "neighbors": {"B": 4, "C": 1}}
