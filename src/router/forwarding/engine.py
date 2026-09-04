"""Entrega, forwarding y distribución de LSP según el protocolo compartido."""
from __future__ import annotations

import json
import logging
import math
import threading
from dataclasses import replace

from router.algorithms import flooding
from router.dedup.cache import DedupCache
from router.neighbors.table import NeighborTable
from router.protocol import factory
from router.protocol.packet import Packet
from router.routing.engine import RoutingEngine

logger = logging.getLogger(__name__)


def parse_lsp_payload(payload, normalize=lambda value: value):
    """Recibe lista canónica y variantes: mapa, links, node/cost o JSON textual."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (ValueError, RecursionError):
            return None
    if not isinstance(payload, dict):
        return None
    origin, seq = payload.get("origin"), payload.get("seq")
    raw = payload.get("neighbors", payload.get("links"))
    age = payload.get("age_s", 0)
    if not isinstance(origin, str) or not origin or type(seq) is not int or seq < 0:
        return None
    if isinstance(age, bool) or not isinstance(age, (int, float)) or not math.isfinite(age) or age < 0:
        return None
    try:
        origin = normalize(origin)
    except ValueError:
        return None
    if isinstance(raw, dict):
        pairs = raw.items()
    elif isinstance(raw, list):
        pairs = [(n.get("id", n.get("node")), n.get("weight", n.get("cost")))
                 for n in raw if isinstance(n, dict)]
    else:
        return None
    neighbors = {}
    for nid, value in pairs:
        try:
            cost = float(value)
            if not isinstance(nid, str) or not nid or isinstance(value, bool) or not math.isfinite(cost) or cost < 0:
                raise ValueError("vecino/costo inválido")
            neighbors[normalize(nid)] = cost
        except (ValueError, TypeError, OverflowError):
            logger.warning("Vecino/costo inválido en LSP de %s: %r=%r", origin, nid, value)
    return origin, seq, neighbors, age


class ForwardingEngine:
    def __init__(self, node_id: str, mode: str, neighbor_table: NeighborTable,
                 routing_engine: RoutingEngine, dedup_cache: DedupCache, send_to_neighbor,
                 initial_ttl: int = 16, on_message_delivered=None, on_echo_received=None,
                 listen_port: int = 5000, normalize_address=lambda value: value) -> None:
        self.node_id = node_id
        self.mode = mode
        self.neighbor_table = neighbor_table
        self.routing_engine = routing_engine
        self.dedup_cache = dedup_cache
        self._send_to_neighbor = send_to_neighbor
        self.initial_ttl = initial_ttl
        self.listen_port = listen_port
        self._normalize = normalize_address
        self._on_message_delivered = on_message_delivered
        self._on_echo_received = on_echo_received
        self._lsdb_synced_with = set()
        self._sync_lock = threading.Lock()
        self._announce_lock = threading.Lock()

    def _active_neighbor_ids(self) -> list:
        return list(self.neighbor_table.active_neighbors())

    def handle_packet(self, packet: Packet, from_neighbor_id: str | None = None) -> None:
        if packet.ttl <= 0:
            logger.info("[%s] paquete descartado (ttl_expired)", self.node_id)
            return
        if packet.proto != self.mode:
            logger.warning("[%s] proto %s distinto del modo %s; se ignora", self.node_id, packet.proto, self.mode)
            return
        try:
            packet = replace(packet, from_=self._normalize(packet.from_), to=self._normalize(packet.to))
            via = packet.header("via")
            sender = self._normalize(via) if isinstance(via, str) and via else from_neighbor_id
        except ValueError:
            logger.warning("[%s] dirección inválida; se descarta", self.node_id)
            return
        if packet.type in ("hello", "echo"):
            if packet.to != self.node_id or packet.from_ not in self.neighbor_table.all_ids():
                return
            if packet.type == "hello":
                self._send_to_neighbor(packet.from_, factory.make_echo(packet, self.listen_port))
                self._sync_lsdb_on_first_contact(packet.from_)
            elif isinstance(packet.payload, dict) and self._on_echo_received:
                self._on_echo_received(packet)
        elif packet.type == "message":
            if self.mode == "flooding":
                decision = flooding.process_incoming_packet(
                    packet, self.node_id, self._active_neighbor_ids(), sender, self.dedup_cache
                )
                if decision.deliver_locally:
                    self._deliver(packet)
                self._send_decision(decision)
            elif packet.to == self.node_id:
                self._deliver(packet)
            elif packet.ttl <= 1:
                logger.info("[%s] mensaje descartado (ttl_expired)", self.node_id)
            else:
                self._send_routed(packet.forwarded_by(self.node_id))
        elif packet.type == "info" and self.mode == "lsr":
            parsed = parse_lsp_payload(packet.payload, self._normalize)
            if parsed is None or packet.to != "*":
                logger.warning("[%s] LSP inválido; se descarta", self.node_id)
                return
            origin, seq, neighbors, age = parsed
            if self.routing_engine.apply_lsp(origin, seq, neighbors, age):
                # La identidad LSP es (origin, seq), nunca msg_id.
                decision = flooding.process_incoming_packet(
                    packet, self.node_id, self._active_neighbor_ids(), sender, None
                )
                self._send_decision(decision)

    def _deliver(self, packet: Packet) -> None:
        logger.info("[%s] MENSAJE de %s: %r", self.node_id, packet.from_, packet.payload)
        if self._on_message_delivered:
            self._on_message_delivered(packet)

    def _send_decision(self, decision) -> None:
        if decision.dropped_reason:
            logger.info("[%s] paquete descartado (%s)", self.node_id, decision.dropped_reason)
        for nid in decision.forward_to:
            self._send_to_neighbor(nid, decision.forwarded_packet)

    def _send_routed(self, packet: Packet) -> None:
        next_hop = self.routing_engine.next_hop(packet.to)
        if next_hop not in self.neighbor_table.active_neighbors():
            logger.warning("[%s] sin ruta activa hacia %s; se descarta", self.node_id, packet.to)
            return
        self._send_to_neighbor(next_hop, packet)

    def send_user_message(self, destination: str, text: str) -> None:
        packet = factory.make_message(self.mode, self.node_id, destination, text, self.initial_ttl)
        if packet.ttl <= 0:
            return
        if destination == self.node_id:
            self._deliver(packet)
        elif self.mode == "flooding":
            self._send_decision(flooding.originate_broadcast(packet, self._active_neighbor_ids(), self.dedup_cache))
        else:
            self._send_routed(packet)

    def send_hello(self, neighbor_id: str, msg_id: str, t0: float) -> None:
        packet = factory.make_hello(self.mode, self.node_id, neighbor_id, msg_id, t0, self.listen_port)
        self._send_to_neighbor(neighbor_id, packet)

    def _sync_lsdb_on_first_contact(self, neighbor_id: str) -> None:
        if self.mode != "lsr":
            return
        with self._sync_lock:
            if neighbor_id in self._lsdb_synced_with:
                return
            self._lsdb_synced_with.add(neighbor_id)
        self.send_lsdb_snapshot(neighbor_id)

    def forget_lsdb_sync(self, neighbor_id: str) -> None:
        with self._sync_lock:
            self._lsdb_synced_with.discard(neighbor_id)

    def send_lsdb_snapshot(self, neighbor_id: str) -> None:
        for origin, seq, neighbors, age in self.routing_engine.lsdb_snapshot_with_age():
            packet = factory.make_lsp(self.node_id, origin, seq, neighbors, self.initial_ttl, age)
            self._send_to_neighbor(neighbor_id, packet)

    def announce_own_lsp(self) -> None:
        if self.mode != "lsr":
            return
        # Captura estado, secuencia y actualización local de manera ordenada.
        with self._announce_lock:
            seq = self.routing_engine.next_own_seq()
            neighbors = self.neighbor_table.active_neighbors()
            self.routing_engine.apply_lsp(self.node_id, seq, neighbors)
            packet = factory.make_lsp(self.node_id, self.node_id, seq, neighbors, self.initial_ttl)
        self._send_decision(flooding.originate_broadcast(packet, self._active_neighbor_ids(), self.dedup_cache))
