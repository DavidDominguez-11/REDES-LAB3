"""Constructores de conveniencia para cada tipo de paquete del protocolo.

Mantiene la forma exacta del payload por tipo, documentada en docs/protocolo.md,
en un solo lugar para que forwarding/routing/algorithms no dupliquen esta lógica.
"""
from __future__ import annotations

import time

from router.protocol.packet import Packet


def make_hello(proto: str, from_: str, to: str, seq: int) -> Packet:
    return Packet(
        proto=proto,
        type="hello",
        from_=from_,
        to=to,
        ttl=1,  # HELLO nunca se reenvía, solo va a un vecino directo
        payload={"seq": seq, "sent_at": time.time()},
    )


def make_echo(proto: str, from_: str, to: str, hello_payload: dict) -> Packet:
    reply_payload = dict(hello_payload)
    reply_payload["echoed_at"] = time.time()
    return Packet(
        proto=proto,
        type="echo",
        from_=from_,
        to=to,
        ttl=1,
        payload=reply_payload,
    )


def make_message(proto: str, from_: str, to: str, text: str, ttl: int) -> Packet:
    return Packet(
        proto=proto,
        type="message",
        from_=from_,
        to=to,
        ttl=ttl,
        payload=text,
        headers=[{"hops": [from_]}],
    )


def make_lsp(from_: str, origin: str, seq: int, neighbors: dict, ttl: int) -> Packet:
    """`to` se usa como convención de broadcast lógico ("*") -- ver nota de
    coordinación pendiente en docs/protocolo.md."""
    return Packet(
        proto="lsr",
        type="info",
        from_=from_,
        to="*",
        ttl=ttl,
        payload={"origin": origin, "seq": seq, "neighbors": dict(neighbors)},
    )
