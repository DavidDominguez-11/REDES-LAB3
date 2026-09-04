import uuid

import pytest

from router.protocol.factory import make_echo, make_hello, make_lsp, make_message
from router.protocol.packet import Packet, PacketValidationError, payload_checksum, canonical_payload

A, B = "10.0.0.1:5000", "10.0.0.2:5000"


def message():
    return make_message("lsr", A, B, "hola G")


def test_round_trip_serialization_and_exact_envelope():
    pkt = message()
    data = pkt.to_dict()
    assert set(data) == {"version", "proto", "type", "from", "to", "ttl", "headers", "payload"}
    assert pkt.ttl == 16
    assert uuid.UUID(pkt.header("msg_id")).version == 4
    assert pkt.header("checksum") == "0bded535"
    restored = Packet.from_json(pkt.to_json())
    assert restored.to_dict() == data
    assert restored.id == pkt.id


@pytest.mark.parametrize("payload, expected", [
    ("hola G", "0bded535"),
    ({"origin": A, "seq": 7, "neighbors": [{"id": B, "weight": 4.8}]}, "cbd08356"),
])
def test_checksum_vectors_from_shared_protocol(payload, expected):
    assert payload_checksum(payload) == expected


def test_checksum_sorts_keys_and_preserves_utf8():
    first = {"z": "á漢", "a": {"c": 2, "b": 1}}
    second = {"a": {"b": 1, "c": 2}, "z": "á漢"}
    assert payload_checksum(first) == payload_checksum(second)
    assert canonical_payload("á") == bytes([0xc3, 0xa1])


@pytest.mark.parametrize("field", ["proto", "type", "from", "to", "ttl", "headers", "payload"])
def test_missing_required_field_raises(field):
    data = message().to_dict()
    del data[field]
    with pytest.raises(PacketValidationError):
        Packet.from_dict(data)


@pytest.mark.parametrize("line", ["", "   ", "{esto no es json", "[]"])
def test_invalid_json_or_envelope_raises(line):
    with pytest.raises(PacketValidationError):
        Packet.from_json(line)


@pytest.mark.parametrize("field, value", [("proto", "dvr"), ("type", "ACK"), ("ttl", True),
                                         ("payload", {}), ("headers", [{"a": 1, "b": 2}])])
def test_invalid_fields_raise(field, value):
    data = message().to_dict()
    data[field] = value
    with pytest.raises(PacketValidationError):
        Packet.from_dict(data)


@pytest.mark.parametrize("version", [None, 2, "otra", True])
def test_unknown_or_missing_version_warns_but_is_processed(version, caplog):
    data = message().to_dict()
    if version is None:
        del data["version"]
    else:
        data["version"] = version
    assert Packet.from_dict(data).payload == "hola G"
    assert "Versión" in caplog.text


def test_checksum_mismatch_warns_without_dropping(caplog):
    data = message().with_header("checksum", "00000000").to_dict()
    pkt = Packet.from_dict(data)
    assert pkt.payload == "hola G"
    assert "Checksum discrepante" in caplog.text


def test_missing_checksum_is_rejected():
    data = message().to_dict()
    data["headers"] = [h for h in data["headers"] if "checksum" not in h]
    with pytest.raises(PacketValidationError):
        Packet.from_dict(data)


def test_fallback_dedup_does_not_depend_on_ttl_or_via():
    data = message().to_dict()
    data["headers"] = [h for h in data["headers"] if "msg_id" not in h]
    first = Packet.from_dict(data)
    data["ttl"] -= 2
    data["headers"].append({"via": B})
    second = Packet.from_dict(data)
    assert first.id == second.id


def test_forwarding_preserves_origin_id_checksum_and_unknown_headers():
    pkt = message().with_header("extension", {"valor": 7})
    forwarded = pkt.forwarded_by(B)
    assert pkt.ttl == 16 and forwarded.ttl == 15
    assert pkt.header("via") is None
    assert forwarded.from_ == A
    assert forwarded.id == pkt.id
    assert forwarded.header("via") == B
    assert forwarded.header("trace") == [A, B]
    assert pkt.header("trace") == [A]
    assert forwarded.header("checksum") == pkt.header("checksum")
    assert forwarded.header("extension") == {"valor": 7}


def test_ttl_decrement_does_not_mutate_original():
    pkt = message()
    decremented = pkt.with_ttl_decremented()
    assert decremented.ttl == pkt.ttl - 1
    assert decremented.id == pkt.id


def test_hello_and_echo_keep_msg_id_and_t0():
    hello = make_hello("lsr", A, B, str(uuid.uuid4()), 1770000000.125, 5000)
    echo = make_echo(hello, 5000)
    assert hello.payload == {"listen_port": 5000}
    assert echo.payload == {"listen_port": 5000}
    assert echo.ttl == hello.ttl == 1
    assert echo.id == hello.id
    assert echo.header("t0") == hello.header("t0")
    assert (echo.from_, echo.to) == (hello.to, hello.from_)
    assert echo.header("checksum") == payload_checksum(echo.payload)


def test_lsp_emits_list_weights_age_and_original_from():
    lsp = make_lsp(B, A, 3, {B: 4.8})
    assert lsp.proto == "lsr" and lsp.type == "info" and lsp.to == "*"
    assert lsp.from_ == A
    assert lsp.header("via") == B
    assert lsp.payload == {"origin": A, "seq": 3, "age_s": 0,
                           "neighbors": [{"id": B, "weight": 4.8}]}
