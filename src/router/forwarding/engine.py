"""Motor de entrega y reenvío para los cuatro tipos de paquete."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from router.algorithms import flooding
from router.algorithms.lsr import parse_lsp_payload
from router.dedup.cache import DedupCache
from router.neighbors.table import NeighborTable
from router.protocol import factory
from router.protocol.address import normalize_address
from router.protocol.packet import Packet
from router.routing.engine import RoutingEngine

logger = logging.getLogger(__name__)

OnMessageDelivered = Callable[[Packet], None]
OnEchoReceived = Callable[[Packet], None]
SendFn = Callable[[str, Packet], None]
ReplyFn = Callable[[Packet], None]
AddressForNeighbor = Callable[[str], str | None]
NeighborForAddress = Callable[[str], str | None]


class ForwardingEngine:
    def __init__(
        self,
        node_id: str,
        mode: str,
        neighbor_table: NeighborTable,
        routing_engine: RoutingEngine,
        dedup_cache: DedupCache,
        send_to_neighbor: SendFn,
        initial_ttl: int = 16,
        on_message_delivered: Optional[OnMessageDelivered] = None,
        on_echo_received: Optional[OnEchoReceived] = None,
        node_address: str | None = None,
        listen_port: int | None = None,
        address_for_neighbor: AddressForNeighbor | None = None,
        neighbor_for_address: NeighborForAddress | None = None,
    ) -> None:
        self.node_id = node_id
        self.node_address = node_address or node_id
        self.listen_port = listen_port
        self.mode = mode
        self.neighbor_table = neighbor_table
        self.routing_engine = routing_engine
        self.dedup_cache = dedup_cache
        self._send_to_neighbor = send_to_neighbor
        self.initial_ttl = initial_ttl
        self._on_message_delivered = on_message_delivered
        self._on_echo_received = on_echo_received
        self._address_for_neighbor = address_for_neighbor
        self._neighbor_for_address = neighbor_for_address

    def _active_neighbor_ids(self) -> list:
        return list(self.neighbor_table.active_neighbors().keys())

    def _neighbor_address(self, neighbor_id: str) -> str:
        if self._address_for_neighbor:
            return self._address_for_neighbor(neighbor_id) or neighbor_id
        return neighbor_id

    def _neighbor_id(self, address: str) -> str | None:
        if self._neighbor_for_address:
            return self._neighbor_for_address(address)
        return address

    def _destination_for_routing(self, destination: str) -> str:
        if self.mode == "lsr":
            # La base LSR se construye con las direcciones IP:puerto del LSP;
            # no hay que convertir el destino a un id lógico de vecino.
            return self._wire_address(destination)
        if self._neighbor_for_address:
            return self._neighbor_for_address(destination) or destination
        return destination

    def _wire_address(self, address: str) -> str:
        if self.listen_port is not None and ("." in address or ":" in address):
            return normalize_address(address, self.listen_port)
        return address

    def _is_local(self, address: str) -> bool:
        if address in {self.node_id, self.node_address}:
            return True
        if self.listen_port is not None:
            return normalize_address(address, self.listen_port) == normalize_address(self.node_address, self.listen_port)
        return False

    def handle_packet(
        self,
        packet: Packet,
        from_neighbor_id: str,
        reply_to: ReplyFn | None = None,
    ) -> None:
        if packet.type == "hello":
            self._handle_hello(packet, reply_to)
        elif packet.type == "echo":
            self._handle_echo(packet)
        elif packet.type == "message":
            self._handle_message(packet, from_neighbor_id)
        elif packet.type == "info":
            self._handle_info(packet, from_neighbor_id)
        else:
            logger.warning("[%s] tipo de paquete desconocido, se ignora: %s", self.node_id, packet.type)

    def _handle_hello(self, packet: Packet, reply_to: ReplyFn | None = None) -> None:
        echo = factory.make_echo(
            proto=packet.proto,
            from_=self.node_address,
            to=packet.from_,
            hello_packet=packet,
        )
        logger.debug("[%s] HELLO de %s -> respondo ECHO", self.node_id, packet.from_)
        if reply_to is not None:
            reply_to(echo)
            return
        neighbor_id = self._neighbor_id(packet.from_)
        if neighbor_id is not None:
            self._send_to_neighbor(neighbor_id, echo)

    def _handle_echo(self, packet: Packet) -> None:
        if self._on_echo_received:
            self._on_echo_received(packet)

    def _handle_message(self, packet: Packet, from_neighbor_id: str) -> None:
        if self.mode == "flooding":
            self._handle_message_flooding(packet, from_neighbor_id)
        else:
            self._handle_message_routed(packet)

    def _handle_message_flooding(self, packet: Packet, from_neighbor_id: str) -> None:
        if packet.to != "*":
            packet = packet.with_destination(self._wire_address(packet.to))
        decision = flooding.process_incoming_packet(
            packet,
            self.node_address,
            self._active_neighbor_ids(),
            from_neighbor_id,
            self.dedup_cache,
        )
        if decision.dropped_reason:
            logger.info("[%s] mensaje %s descartado (%s)", self.node_id, packet.msg_id, decision.dropped_reason)
            return
        if decision.deliver_locally:
            logger.info("[%s] MENSAJE recibido de %s: %r", self.node_id, packet.from_, packet.payload)
            if self._on_message_delivered:
                self._on_message_delivered(packet)
        for neighbor_id in decision.forward_to:
            logger.info("[%s] flooding: reenvío %s a %s", self.node_id, packet.msg_id, neighbor_id)
            self._send_to_neighbor(neighbor_id, decision.forwarded_packet)

    def _handle_message_routed(self, packet: Packet) -> None:
        if self._is_local(packet.to):
            logger.info("[%s] MENSAJE recibido de %s: %r", self.node_id, packet.from_, packet.payload)
            if self._on_message_delivered:
                self._on_message_delivered(packet)
            return
        if packet.ttl <= 0:
            logger.info("[%s] mensaje %s descartado (ttl_expired)", self.node_id, packet.msg_id)
            return
        destination = self._destination_for_routing(packet.to)
        next_hop = self.routing_engine.next_hop(destination)
        if next_hop is None:
            logger.warning("[%s] sin ruta hacia %s, se descarta mensaje %s", self.node_id, packet.to, packet.msg_id)
            return
        forwarded = packet.with_ttl_decremented().with_forward_metadata(
            self.node_address,
            trace_message=True,
        )
        logger.info("[%s] reenvío %s hacia %s vía next-hop %s", self.node_id, packet.msg_id, packet.to, next_hop)
        self._send_to_neighbor(next_hop, forwarded)

    def _handle_info(self, packet: Packet, from_neighbor_id: str) -> None:
        if self.mode != "lsr":
            logger.info("[%s] paquete info ignorado fuera de modo lsr", self.node_id)
            return
        parsed = parse_lsp_payload(packet.payload)
        if parsed is None:
            logger.warning("[%s] paquete info con payload inválido, se descarta", self.node_id)
            return
        if packet.ttl <= 0:
            logger.info("[%s] LSP %s descartado (ttl_expired)", self.node_id, packet.msg_id)
            return
        origin, seq, _age_s, neighbors = parsed
        origin = self._wire_address(origin)
        neighbors = {self._wire_address(node): cost for node, cost in neighbors.items()}
        applied = self.routing_engine.apply_lsp(origin, seq, neighbors)
        if not applied:
            logger.debug("[%s] LSP de %s (seq=%s) descartado por viejo/duplicado", self.node_id, origin, seq)
            return

        logger.info("[%s] LSP nuevo de %s (seq=%s), tabla recalculada", self.node_id, origin, seq)
        forwarded = packet.with_ttl_decremented().with_forward_metadata(self.node_address)
        for neighbor_id in self._active_neighbor_ids():
            if neighbor_id != from_neighbor_id:
                self._send_to_neighbor(neighbor_id, forwarded)

    def send_user_message(self, destination: str, text: str) -> None:
        wire_destination = self._neighbor_address(destination) if self._neighbor_for_address else destination
        pkt = factory.make_message(
            proto=self.mode,
            from_=self.node_address,
            to=wire_destination,
            text=text,
            ttl=self.initial_ttl,
        )
        if self.mode == "flooding":
            if self._is_local(wire_destination):
                if self._on_message_delivered:
                    self._on_message_delivered(pkt)
                return
            decision = flooding.originate_broadcast(pkt, self._active_neighbor_ids(), self.dedup_cache)
            for neighbor_id in decision.forward_to:
                self._send_to_neighbor(neighbor_id, decision.forwarded_packet)
            return

        if self._is_local(wire_destination):
            if self._on_message_delivered:
                self._on_message_delivered(pkt)
            return
        route_destination = self._destination_for_routing(wire_destination)
        next_hop = self.routing_engine.next_hop(route_destination)
        if next_hop is None:
            logger.warning("[%s] no hay ruta conocida hacia %s todavía", self.node_id, destination)
            return
        self._send_to_neighbor(next_hop, pkt)

    def send_hello(self, neighbor_id: str, seq: int | None = None) -> Packet:
        hello = factory.make_hello(
            proto=self.mode,
            from_=self.node_address,
            to=self._neighbor_address(neighbor_id),
            seq=seq,
            listen_port=self.listen_port,
        )
        self._send_to_neighbor(neighbor_id, hello)
        return hello

    def announce_own_lsp(self) -> None:
        if self.mode != "lsr":
            return
        seq = self.routing_engine.next_own_seq()
        neighbors = {
            self._neighbor_address(neighbor_id): cost
            for neighbor_id, cost in self.neighbor_table.active_neighbors().items()
        }
        self.routing_engine.apply_lsp(self.node_address, seq, neighbors)
        lsp = factory.make_lsp(
            from_=self.node_address,
            origin=self.node_address,
            seq=seq,
            neighbors=neighbors,
            ttl=self.initial_ttl,
        )
        logger.info("[%s] anuncio LSP propio seq=%s vecinos=%s", self.node_id, seq, neighbors)
        decision = flooding.originate_broadcast(lsp, self._active_neighbor_ids(), self.dedup_cache)
        for neighbor_id in decision.forward_to:
            self._send_to_neighbor(neighbor_id, decision.forwarded_packet)
