"""Algoritmo de Flooding.

Reglas (ver docs/protocolo.md):
- Cada nodo reenvía un paquete a todos sus vecinos EXCEPTO a quien se lo envió.
- Un paquete repetido (mismo `id`, visto antes) se descarta sin reprocesar.
- TTL se decrementa en cada salto; si al llegar ttl <= 0, se descarta.
- `to == "*"` es la convención de broadcast lógico (usada por LSR para LSPs);
  un `to` igual al node_id local entrega el mensaje localmente y detiene el
  flooding de esa copia (flooding "controlado": no sigue después de llegar).

Esta pieza es puramente funcional (no toca sockets) para poder probarla con
pruebas unitarias simples y reutilizarla dentro de LSR sin duplicar lógica.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from router.dedup.cache import DedupCache
from router.protocol.packet import Packet


@dataclass
class FloodingDecision:
    deliver_locally: bool
    forward_to: list  # list[str] de node_ids vecinos a los que reenviar
    forwarded_packet: Optional[Packet]
    dropped_reason: Optional[str]  # "duplicate" | "ttl_expired" | None


def process_incoming_packet(
    packet: Packet,
    node_id: str,
    neighbor_ids: list,
    exclude_neighbor_id: str,
    dedup_cache: DedupCache | None,
) -> FloodingDecision:
    """Decide qué hacer con un paquete recibido, según las reglas de flooding."""
    if packet.ttl <= 0:
        return FloodingDecision(False, [], None, "ttl_expired")

    # Los LSP ya fueron deduplicados por (origin, seq) en la LSDB.
    if dedup_cache is not None and dedup_cache.check_and_mark(packet.id):
        return FloodingDecision(False, [], None, "duplicate")

    is_broadcast = packet.to == "*"
    is_for_me = packet.to == node_id
    deliver_locally = is_for_me or is_broadcast

    # Flooding controlado: si ya llegó a su destinatario puntual, no sigue.
    should_forward = is_broadcast or not is_for_me

    forward_to: list = []
    forwarded_packet: Optional[Packet] = None
    if should_forward:
        if packet.ttl <= 1:
            return FloodingDecision(deliver_locally, [], None, "ttl_expired")
        forwarded_packet = packet.forwarded_by(node_id)
        forward_to = [n for n in neighbor_ids if n != exclude_neighbor_id]

    return FloodingDecision(deliver_locally, forward_to, forwarded_packet, None)


def originate_broadcast(packet: Packet, neighbor_ids: list, dedup_cache: DedupCache) -> FloodingDecision:
    """Para cuando ESTE nodo origina un paquete a difundir (no lo recibió de nadie).

    No decrementa TTL: el TTL inicial ya representa el número de saltos
    permitidos a partir del primer envío, no del origen.
    """
    if packet.ttl <= 0:
        return FloodingDecision(False, [], None, "ttl_expired")
    dedup_cache.mark_seen(packet.id)
    return FloodingDecision(deliver_locally=False, forward_to=list(neighbor_ids), forwarded_packet=packet, dropped_reason=None)
