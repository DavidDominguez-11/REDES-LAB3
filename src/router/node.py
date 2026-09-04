"""Orquestador de un nodo: TCP, health-check, forwarding y mantenimiento LSR."""
from __future__ import annotations

import logging
import socket
import threading
from pathlib import Path

from router.config.loader import load_node_config, load_topology
from router.config.models import NodeConfig
from router.dedup.cache import DedupCache
from router.forwarding.engine import ForwardingEngine
from router.neighbors.health_check import HealthChecker
from router.neighbors.table import NeighborTable
from router.protocol.address import endpoint
from router.protocol.packet import Packet
from router.routing.engine import RoutingEngine
from router.transport.tcp import NeighborLink, TcpServer

logger = logging.getLogger(__name__)


class Node:
    def __init__(self, config: NodeConfig, repo_root: str = ".") -> None:
        self.config = config
        self.node_id = config.node_id
        self.address = endpoint(config.host, config.port)

        static_topology = None
        if config.mode == "dijkstra":
            topology_path = Path(config.topology_file or "")
            if not topology_path.is_absolute():
                topology_path = Path(repo_root) / topology_path
            static_topology = load_topology(topology_path)

        self.neighbor_table = NeighborTable(config.neighbors, default_port=config.port)
        self.dedup_cache = DedupCache(ttl_sec=config.params.dedup_cache_ttl_sec)

        # LSR anuncia direcciones de cable, mientras que una topología estática
        # puede conservar ids lógicos del archivo de configuración.
        routing_identity = self.address if config.mode == "lsr" else config.node_id
        if config.mode == "dijkstra" and static_topology and config.node_id not in static_topology.nodes:
            routing_identity = self.address
        self.routing_engine = RoutingEngine(
            routing_identity,
            mode=config.mode,
            static_topology=static_topology,
            lsp_expiry_sec=config.params.lsp_expiry_sec,
        )
        if config.mode == "dijkstra":
            self.routing_engine.add_alias(self.address, routing_identity)
            for neighbor in config.neighbors:
                self.routing_engine.add_alias(neighbor.node_id, neighbor.node_id)
                self.routing_engine.add_alias(neighbor.address, neighbor.node_id)
        else:
            self.routing_engine.add_alias(config.node_id, self.address)

        self._links: dict[str, NeighborLink] = {
            n.node_id: NeighborLink(n.host, n.port, connect_timeout=0.5, on_packet=self._on_outgoing_packet)
            for n in config.neighbors
        }

        self.forwarding_engine = ForwardingEngine(
            node_id=config.node_id,
            mode=config.mode,
            neighbor_table=self.neighbor_table,
            routing_engine=self.routing_engine,
            dedup_cache=self.dedup_cache,
            send_to_neighbor=self._send_to_neighbor,
            initial_ttl=config.params.initial_ttl,
            on_message_delivered=self._default_on_message_delivered,
            node_address=self.address,
            listen_port=config.port,
            address_for_neighbor=self.neighbor_table.address_for,
            neighbor_for_address=self.neighbor_table.resolve_id,
        )

        self._server = TcpServer(
            config.host,
            config.port,
            on_packet=self._on_packet_received,
            on_packet_with_connection=self._on_packet_received_with_connection,
        )

        self.health_checker = HealthChecker(
            node_id=config.node_id,
            neighbor_table=self.neighbor_table,
            send_hello=self.forwarding_engine.send_hello,
            interval_sec=config.params.hello_interval_sec,
            timeout_sec=config.params.hello_timeout_sec,
            max_failures=config.params.hello_max_failures,
            on_status_change=self._on_neighbor_status_change,
        )
        self.forwarding_engine._on_echo_received = self._on_echo_received
        self._maintenance_stop = threading.Event()
        self._maintenance_thread: threading.Thread | None = None

    @classmethod
    def from_config_path(cls, path: str, repo_root: str = ".") -> "Node":
        return cls(load_node_config(path), repo_root=repo_root)

    def _send_to_neighbor(self, neighbor_id: str, packet: Packet) -> None:
        link = self._links.get(neighbor_id)
        if link is None:
            resolved = self.neighbor_table.resolve_id(neighbor_id)
            link = self._links.get(resolved) if resolved else None
        if link is None:
            logger.warning("[%s] no existe enlace configurado hacia %s", self.node_id, neighbor_id)
            return
        try:
            link.send(packet)
        except (OSError, ValueError) as exc:
            logger.debug("[%s] no se pudo enviar a %s: %s", self.node_id, neighbor_id, exc)

    def _incoming_neighbor_id(self, packet: Packet, peer: tuple[str, int] | None = None) -> str:
        via = packet.header("via")
        resolved = self.neighbor_table.resolve_id(via) if isinstance(via, str) else None
        if resolved:
            return resolved
        resolved = self.neighbor_table.resolve_id(packet.from_)
        if resolved:
            return resolved
        if peer:
            resolved = self.neighbor_table.resolve_peer(peer, packet.from_, via)
            if resolved:
                return resolved
        return packet.from_

    def _on_packet_received(self, packet: Packet) -> None:
        self.forwarding_engine.handle_packet(packet, self._incoming_neighbor_id(packet))

    def _on_packet_received_with_connection(self, packet: Packet, connection: socket.socket) -> None:
        try:
            peer = connection.getpeername()
        except OSError:
            peer = None
        reply_to = lambda reply: self._server.send_on_connection(connection, reply)
        self.forwarding_engine.handle_packet(
            packet,
            self._incoming_neighbor_id(packet, peer),
            reply_to=reply_to,
        )

    def _on_outgoing_packet(self, packet: Packet) -> None:
        self.forwarding_engine.handle_packet(packet, self._incoming_neighbor_id(packet))

    def _on_echo_received(self, packet: Packet) -> None:
        neighbor_id = self.neighbor_table.resolve_id(packet.from_) or packet.from_
        seq = packet.payload.get("seq") if isinstance(packet.payload, dict) else None
        self.health_checker.record_echo(
            neighbor_id,
            seq=seq,
            msg_id=packet.msg_id,
            t0=packet.header("t0"),
        )

    def _on_neighbor_status_change(self, neighbor_id: str, is_up: bool) -> None:
        logger.info(
            "[%s] vecino %s cambia a %s",
            self.node_id,
            neighbor_id,
            "activo" if is_up else "inactivo",
        )
        if self.config.mode == "lsr":
            self.forwarding_engine.announce_own_lsp()

    def _default_on_message_delivered(self, packet: Packet) -> None:
        print(f"[{self.node_id}] << mensaje de {packet.from_}: {packet.payload}")

    def _maintenance_loop(self) -> None:
        interval = max(0.1, self.config.params.lsp_interval_sec)
        while not self._maintenance_stop.wait(interval):
            if self.config.mode != "lsr":
                continue
            expired = self.routing_engine.expire_lsp()
            if expired:
                logger.info("[%s] LSP expirados: %s; tabla recalculada", self.node_id, expired)
            self.forwarding_engine.announce_own_lsp()

    def start(self) -> None:
        self._server.start()
        self.health_checker.start()
        if self.config.mode == "lsr":
            # Un vecino puede arrancar después; los envíos periódicos y el
            # health-check se encargan de la convergencia sin bloquear start().
            threading.Thread(target=self.forwarding_engine.announce_own_lsp, daemon=True).start()
            self._maintenance_stop.clear()
            self._maintenance_thread = threading.Thread(target=self._maintenance_loop, daemon=True)
            self._maintenance_thread.start()
        logger.info(
            "[%s] nodo iniciado en %s:%s modo=%s",
            self.node_id,
            self.config.host,
            self.config.port,
            self.config.mode,
        )

    def stop(self) -> None:
        self.health_checker.stop()
        self._maintenance_stop.set()
        self._server.stop()
        for link in self._links.values():
            link.close()

    def send_message(self, destination: str, text: str) -> None:
        self.forwarding_engine.send_user_message(destination, text)

    def list_neighbors(self) -> list:
        return [self.neighbor_table.get(nid) for nid in self.neighbor_table.all_ids()]

    def list_routes(self) -> dict:
        return self.routing_engine.routes()
