"""Motor de Forwarding.

Responsable de:
- Procesar paquetes entrantes (hello -> responder echo; echo -> notificar
  health check; message -> entregar o reenviar; info -> aplicar LSP y
  reflood si es nuevo).
- Enviar paquetes salientes: mensajes de usuario, HELLO, y el LSP propio.

No decide POR SÍ MISMO las rutas (eso es `routing/engine.py`) ni las reglas
de flooding (`algorithms/flooding.py`): las orquesta. Así se evita duplicar
lógica entre modos.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from router.algorithms import flooding
from router.dedup.cache import DedupCache
from router.neighbors.table import NeighborTable
from router.protocol import factory
from router.protocol.packet import Packet
from router.routing.engine import RoutingEngine

logger = logging.getLogger(__name__)

OnMessageDelivered = Callable[[Packet], None]
OnEchoReceived = Callable[[Packet], None]
SendFn = Callable[[str, Packet], None]  # (neighbor_id, packet) -> None


class ForwardingEngine:
    def __init__(
        self,
        node_id: str,
        mode: str,
        neighbor_table: NeighborTable,
        routing_engine: RoutingEngine,
        dedup_cache: DedupCache,
        send_to_neighbor: SendFn,
        initial_ttl: int = 5,
        on_message_delivered: Optional[OnMessageDelivered] = None,
        on_echo_received: Optional[OnEchoReceived] = None,
    ) -> None:
        self.node_id = node_id
        self.mode = mode
        self.neighbor_table = neighbor_table
        self.routing_engine = routing_engine
        self.dedup_cache = dedup_cache
        self._send_to_neighbor = send_to_neighbor
        self.initial_ttl = initial_ttl
        self._on_message_delivered = on_message_delivered
        self._on_echo_received = on_echo_received

    def _active_neighbor_ids(self) -> list:
        """Vecinos actualmente activos, para no intentar reenviar por enlaces caídos
        (evita reenvíos indefinidos/errores hacia un vecino inactivo)."""
        return list(self.neighbor_table.active_neighbors().keys())

    # ------------------------------------------------------------------ #
    # Entrada: un paquete llegó por la conexión asociada a `from_neighbor_id`
    # ------------------------------------------------------------------ #
    def handle_packet(self, packet: Packet, from_neighbor_id: str) -> None:
        if packet.type == "hello":
            self._handle_hello(packet)
        elif packet.type == "echo":
            self._handle_echo(packet)
        elif packet.type == "message":
            self._handle_message(packet, from_neighbor_id)
        elif packet.type == "info":
            self._handle_info(packet, from_neighbor_id)
        else:
            logger.warning("[%s] tipo de paquete desconocido, se ignora: %s", self.node_id, packet.type)

    def _handle_hello(self, packet: Packet) -> None:
        echo = factory.make_echo(proto=packet.proto, from_=self.node_id, to=packet.from_, hello_payload=packet.payload)
        logger.debug("[%s] HELLO de %s -> respondo ECHO", self.node_id, packet.from_)
        self._send_to_neighbor(packet.from_, echo)

    def _handle_echo(self, packet: Packet) -> None:
        if self._on_echo_received:
            self._on_echo_received(packet)

    def _handle_message(self, packet: Packet, from_neighbor_id: str) -> None:
        if self.mode == "flooding":
            self._handle_message_flooding(packet, from_neighbor_id)
        else:
            self._handle_message_routed(packet)

    def _handle_message_flooding(self, packet: Packet, from_neighbor_id: str) -> None:
        decision = flooding.process_incoming_packet(
            packet, self.node_id, self._active_neighbor_ids(), from_neighbor_id, self.dedup_cache
        )
        if decision.dropped_reason:
            logger.info("[%s] mensaje %s descartado (%s)", self.node_id, packet.id, decision.dropped_reason)
            return
        if decision.deliver_locally:
            logger.info("[%s] MENSAJE recibido de %s: %r", self.node_id, packet.from_, packet.payload)
            if self._on_message_delivered:
                self._on_message_delivered(packet)
        for neighbor_id in decision.forward_to:
            logger.info("[%s] flooding: reenvío %s a %s", self.node_id, packet.id, neighbor_id)
            self._send_to_neighbor(neighbor_id, decision.forwarded_packet)

    def _handle_message_routed(self, packet: Packet) -> None:
        if packet.to == self.node_id:
            logger.info("[%s] MENSAJE recibido de %s: %r", self.node_id, packet.from_, packet.payload)
            if self._on_message_delivered:
                self._on_message_delivered(packet)
            return
        if packet.ttl <= 0:
            logger.info("[%s] mensaje %s descartado (ttl_expired)", self.node_id, packet.id)
            return
        next_hop = self.routing_engine.next_hop(packet.to)
        if next_hop is None:
            logger.warning("[%s] sin ruta hacia %s, se descarta mensaje %s", self.node_id, packet.to, packet.id)
            return
        forwarded = packet.with_ttl_decremented(new_from=self.node_id).with_hop_appended(self.node_id)
        logger.info("[%s] reenvío %s hacia %s vía next-hop %s", self.node_id, packet.id, packet.to, next_hop)
        self._send_to_neighbor(next_hop, forwarded)

    def _handle_info(self, packet: Packet, from_neighbor_id: str) -> None:
        origin = packet.payload.get("origin")
        seq = packet.payload.get("seq")
        neighbors = packet.payload.get("neighbors", {})
        if origin is None or seq is None:
            logger.warning("[%s] paquete info con payload inválido, se descarta", self.node_id)
            return

        applied = self.routing_engine.apply_lsp(origin, seq, neighbors)
        if not applied:
            logger.debug("[%s] LSP de %s (seq=%s) descartado por viejo/duplicado", self.node_id, origin, seq)
            return

        logger.info("[%s] LSP nuevo de %s (seq=%s) aplicado, tabla recalculada", self.node_id, origin, seq)
        decision = flooding.process_incoming_packet(
            packet, self.node_id, self._active_neighbor_ids(), from_neighbor_id, self.dedup_cache
        )
        if decision.forwarded_packet:
            for neighbor_id in decision.forward_to:
                self._send_to_neighbor(neighbor_id, decision.forwarded_packet)

    # ------------------------------------------------------------------ #
    # Salida: acciones que origina este nodo
    # ------------------------------------------------------------------ #
    def send_user_message(self, destination: str, text: str) -> None:
        pkt = factory.make_message(proto=self.mode, from_=self.node_id, to=destination, text=text, ttl=self.initial_ttl)
        if self.mode == "flooding":
            decision = flooding.originate_broadcast(pkt, self._active_neighbor_ids(), self.dedup_cache)
            for neighbor_id in decision.forward_to:
                self._send_to_neighbor(neighbor_id, decision.forwarded_packet)
            return

        if destination == self.node_id:
            logger.info("[%s] mensaje dirigido a mí mismo", self.node_id)
            if self._on_message_delivered:
                self._on_message_delivered(pkt)
            return
        next_hop = self.routing_engine.next_hop(destination)
        if next_hop is None:
            logger.warning("[%s] no hay ruta conocida hacia %s todavía", self.node_id, destination)
            return
        self._send_to_neighbor(next_hop, pkt)

    def send_hello(self, neighbor_id: str, seq: int) -> None:
        hello = factory.make_hello(proto=self.mode, from_=self.node_id, to=neighbor_id, seq=seq)
        self._send_to_neighbor(neighbor_id, hello)

    def announce_own_lsp(self) -> None:
        """Genera y difunde el LSP propio a partir de los vecinos activos actuales."""
        if self.mode != "lsr":
            return
        seq = self.routing_engine.next_own_seq()
        neighbors = self.neighbor_table.active_neighbors()
        self.routing_engine.apply_lsp(self.node_id, seq, neighbors)
        lsp = factory.make_lsp(from_=self.node_id, origin=self.node_id, seq=seq, neighbors=neighbors, ttl=self.initial_ttl)
        logger.info("[%s] anuncio LSP propio seq=%s vecinos=%s", self.node_id, seq, neighbors)
        decision = flooding.originate_broadcast(lsp, self._active_neighbor_ids(), self.dedup_cache)
        for neighbor_id in decision.forward_to:
            self._send_to_neighbor(neighbor_id, decision.forwarded_packet)
