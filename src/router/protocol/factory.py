"""Constructores de paquetes en la forma única del protocolo de cable."""
from __future__ import annotations

import time
from typing import Any, Iterable

from router.protocol.packet import Packet


def _legacy_node_id(value: str) -> bool:
    return ":" not in value and "." not in value


def make_hello(
    proto: str,
    from_: str,
    to: str,
    seq: int | None = None,
    *,
    listen_port: int | None = None,
    t0: float | None = None,
    msg_id: str | None = None,
) -> Packet:
    """Construye un HELLO con ``msg_id`` y ``t0`` en headers.

    ``seq`` se acepta únicamente para compatibilidad con la API previa. Si se
    usa la forma nueva (``listen_port``), el payload solo contiene
    ``listen_port`` como define el protocolo.
    """
    t0 = time.time() if t0 is None else t0
    if listen_port is None and seq is not None:
        payload: dict[str, Any] = {"seq": seq, "sent_at": t0}
    else:
        payload = {"listen_port": listen_port}
    return Packet(
        proto=proto,
        type="hello",
        from_=from_,
        to=to,
        ttl=1,
        payload=payload,
        id=msg_id,
        headers=[{"t0": t0}],
    )


def make_echo(
    proto: str,
    from_: str,
    to: str,
    hello_payload: dict | None = None,
    *,
    hello_packet: Packet | None = None,
    msg_id: str | None = None,
    t0: float | None = None,
) -> Packet:
    """Construye el ECHO conservando el ``msg_id`` y ``t0`` del HELLO."""
    if hello_packet is not None:
        hello_payload = dict(hello_packet.payload)
        msg_id = hello_packet.msg_id
        t0 = hello_packet.header("t0", t0)
    payload = dict(hello_payload or {})
    # En la API anterior el echo llevaba estos campos dentro del payload. Se
    # conserva solo para llamadas antiguas que no entregan un Packet.
    if hello_packet is None and "seq" in payload:
        payload["echoed_at"] = time.time()
    if t0 is None:
        t0 = time.time()
    return Packet(
        proto=proto,
        type="echo",
        from_=from_,
        to=to,
        ttl=1,
        payload=payload,
        id=msg_id,
        headers=[{"t0": t0}],
    )


def make_message(proto: str, from_: str, to: str, text: str, ttl: int = 16) -> Packet:
    headers = [{"hops": [from_]}] if _legacy_node_id(from_) else [{"trace": [from_]}]
    return Packet(
        proto=proto,
        type="message",
        from_=from_,
        to=to,
        ttl=ttl,
        payload=text,
        headers=headers,
    )


def _wire_neighbors(neighbors: dict | Iterable[dict]) -> list[dict]:
    if isinstance(neighbors, dict):
        return [{"id": node_id, "weight": weight} for node_id, weight in neighbors.items()]
    result = []
    for item in neighbors:
        if not isinstance(item, dict):
            continue
        node_id = item.get("id", item.get("node"))
        weight = item.get("weight", item.get("cost"))
        if node_id is not None and weight is not None:
            result.append({"id": node_id, "weight": weight})
    return result


def make_lsp(
    from_: str,
    origin: str,
    seq: int,
    neighbors: dict | Iterable[dict],
    ttl: int = 16,
    *,
    age_s: float = 0,
) -> Packet:
    """Construye un LSP ``info`` con la forma canónica ``[{id, weight}]``."""
    if _legacy_node_id(from_):
        # Compatibilidad con las pruebas/locales antiguas que usaban ids
        # lógicos; los paquetes de cable usan siempre la rama canónica.
        payload = {"origin": origin, "seq": seq, "neighbors": dict(neighbors) if isinstance(neighbors, dict) else _wire_neighbors(neighbors)}
    else:
        payload = {
            "origin": origin,
            "seq": seq,
            "age_s": age_s,
            "neighbors": _wire_neighbors(neighbors),
        }
    return Packet(
        proto="lsr",
        type="info",
        from_=from_,
        to="*",
        ttl=ttl,
        payload=payload,
    )
