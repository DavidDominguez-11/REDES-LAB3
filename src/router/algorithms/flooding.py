"""Decisiones puras de inundación para mensajes y LSP."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional

from router.dedup.cache import DedupCache
from router.protocol.packet import Packet


@dataclass
class FloodingDecision:
    deliver_locally: bool
    forward_to: list
    forwarded_packet: Optional[Packet]
    dropped_reason: Optional[str]


def packet_dedup_key(packet: Packet) -> str:
    """Clave estable que no incluye TTL, para evitar loops en anillos."""
    if packet.msg_id:
        return packet.msg_id
    canonical = json.dumps(
        (packet.from_, packet.to, packet.type, packet.payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def process_incoming_packet(
    packet: Packet,
    node_id: str,
    neighbor_ids: list,
    exclude_neighbor_id: str | None,
    dedup_cache: DedupCache,
) -> FloodingDecision:
    """Procesa una copia entrante: entrega si corresponde y reflood si no."""
    if dedup_cache.check_and_mark(packet_dedup_key(packet)):
        return FloodingDecision(False, [], None, "duplicate")

    is_broadcast = packet.to == "*"
    is_for_me = packet.to == node_id
    if is_for_me:
        return FloodingDecision(True, [], None, None)
    if packet.ttl <= 0:
        return FloodingDecision(False, [], None, "ttl_expired")
    deliver_locally = is_for_me or is_broadcast
    should_forward = is_broadcast or not is_for_me
    if not should_forward:
        return FloodingDecision(True, [], None, None)

    forwarded = packet.with_ttl_decremented()
    if all("." not in value and ":" not in value for value in (node_id, packet.from_)):
        # Compatibilidad con el ejercicio local anterior, que usaba `from`
        # como salto actual y `hops` para la traza. En el protocolo nuevo las
        # direcciones son host:puerto y se conserva el originador absoluto.
        forwarded = packet.with_ttl_decremented(new_from=node_id).with_hop_appended(node_id)
    else:
        forwarded = forwarded.with_forward_metadata(node_id, trace_message=packet.type == "message")
    forward_to = [neighbor for neighbor in neighbor_ids if neighbor != exclude_neighbor_id]
    return FloodingDecision(deliver_locally, forward_to, forwarded, None)


def originate_broadcast(packet: Packet, neighbor_ids: list, dedup_cache: DedupCache) -> FloodingDecision:
    """Registra un paquete originado localmente y lo envía a vecinos activos."""
    dedup_cache.mark_seen(packet_dedup_key(packet))
    return FloodingDecision(False, list(neighbor_ids), packet, None)
