"""Constructores del formato canónico del protocolo compartido."""
from __future__ import annotations

from router.protocol.packet import Packet


def make_hello(proto: str, from_: str, to: str, msg_id: str, t0: float, listen_port: int) -> Packet:
    return Packet(proto=proto, type="hello", from_=from_, to=to, ttl=1,
                  id=msg_id, headers=[{"t0": t0}], payload={"listen_port": listen_port})


def make_echo(hello: Packet, listen_port: int) -> Packet:
    return Packet(proto=hello.proto, type="echo", from_=hello.to, to=hello.from_, ttl=1,
                  id=hello.id, headers=[{"t0": hello.header("t0")}], payload={"listen_port": listen_port})


def make_message(proto: str, from_: str, to: str, text: str, ttl: int = 16) -> Packet:
    return Packet(proto=proto, type="message", from_=from_, to=to, ttl=ttl,
                  payload=text, headers=[{"trace": [from_]}])


def make_lsp(from_: str, origin: str, seq: int, neighbors: dict, ttl: int = 16, age_s: float = 0) -> Packet:
    return Packet(proto="lsr", type="info", from_=origin, to="*", ttl=ttl,
                  headers=[{"via": from_}],
                  payload={"origin": origin, "seq": seq, "age_s": age_s,
                           "neighbors": [{"id": n, "weight": cost} for n, cost in neighbors.items()]})
