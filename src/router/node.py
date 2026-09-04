"""Orquesta un router: direcciones canónicas, transporte, forwarding y routing."""
from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import replace
from pathlib import Path

from router.config.addressing import AddressBook
from router.config.loader import ConfigError, load_node_config, load_topology
from router.config.models import NodeConfig, Topology
from router.dedup.cache import DedupCache
from router.forwarding.engine import ForwardingEngine
from router.neighbors.health_check import HealthChecker
from router.neighbors.table import NeighborTable
from router.protocol.packet import Packet
from router.routing.engine import RoutingEngine
from router.transport.tcp import NeighborLink, TcpServer

logger = logging.getLogger(__name__)


class Node:
    def __init__(self, config: NodeConfig, repo_root: str = ".") -> None:
        self.config = config
        self.node_id = config.node_id  # etiqueta visible, no identidad en el cable
        advertised = config.advertised_host or config.host
        if advertised == "0.0.0.0":
            raise ConfigError("Configura advertised_host con la IP accesible del nodo al escuchar en 0.0.0.0")
        aliases = dict(config.addresses)
        aliases.update({n.node_id: f"{n.host}:{n.port}" for n in config.neighbors})
        aliases[config.node_id] = f"{advertised}:{config.port}"
        try:
            self.addresses = AddressBook(aliases, config.network_port)
            self.address = self.addresses.resolve(config.node_id)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        neighbors = [replace(n, node_id=self.addresses.resolve(n.node_id)) for n in config.neighbors]
        topology = None
        if config.mode == "dijkstra":
            source = load_topology(Path(repo_root) / config.topology_file)
            try:
                edges = {self.addresses.resolve(origin):
                         {self.addresses.resolve(n): cost for n, cost in links.items()}
                         for origin, links in source.edges.items()}
            except ValueError as exc:
                raise ConfigError("Falta un alias de la topología en addresses: " + str(exc)) from exc
            topology = Topology(list(edges), edges)

        self.neighbor_table = NeighborTable(neighbors)
        self.dedup_cache = DedupCache(config.params.dedup_cache_ttl_sec)
        self.routing_engine = RoutingEngine(self.address, config.mode, topology)
        self._stopping = threading.Event()
        self._links = {
            n.node_id: NeighborLink(n.host, n.port,
                                   on_packet=lambda packet, nid=n.node_id: self._on_packet_received(packet, nid))
            for n in neighbors
        }
        self.forwarding_engine = ForwardingEngine(
            node_id=self.address, mode=config.mode, neighbor_table=self.neighbor_table,
            routing_engine=self.routing_engine, dedup_cache=self.dedup_cache,
            send_to_neighbor=self._send_to_neighbor, initial_ttl=config.params.initial_ttl,
            on_message_delivered=self._default_on_message_delivered,
            on_echo_received=self._on_echo_received, listen_port=config.port,
            normalize_address=self.addresses.resolve,
        )
        self._server = TcpServer(config.host, config.port, self._on_packet_received,
                                 on_peer_packet=self._on_packet_received)
        self.health_checker = HealthChecker(
            node_id=self.address, neighbor_table=self.neighbor_table,
            send_hello=self.forwarding_engine.send_hello,
            interval_sec=config.params.hello_interval_sec, timeout_sec=config.params.hello_timeout_sec,
            max_failures=config.params.hello_max_failures, on_status_change=self._on_neighbor_status_change,
        )
        self._routing_stop = threading.Event()
        self._routing_thread = None

    @classmethod
    def from_config_path(cls, path: str, repo_root: str = ".") -> "Node":
        return cls(load_node_config(path), repo_root=repo_root)

    def _send_to_neighbor(self, neighbor_id: str, packet: Packet) -> None:
        if self._stopping.is_set():
            return
        link = self._links.get(neighbor_id)
        if link is None:
            logger.warning("[%s] vecino sin enlace configurado: %s", self.node_id, neighbor_id)
            return
        try:
            link.send(packet)
        except (OSError, ValueError) as exc:
            logger.warning("[%s] no se pudo enviar a %s: %s", self.node_id, neighbor_id, exc)

    def _on_packet_received(self, packet: Packet, peer_id: str | None = None, peer=None) -> None:
        if self._stopping.is_set():
            return
        try:
            via = packet.header("via")
            sender = self.addresses.resolve(via) if isinstance(via, str) and via else (
                self.addresses.resolve(peer_id) if peer_id else None
            )
            if sender is None and peer:
                # El puerto TCP de origen suele ser efímero, no el de escucha.
                matches = [n.node_id for n in self.list_neighbors() if n.host == peer[0]]
                if len(matches) == 1:
                    sender = matches[0]
            if sender is None and packet.type in ("hello", "echo"):
                sender = self.addresses.resolve(packet.from_)
        except ValueError:
            logger.warning("[%s] dirección de emisor inválida", self.node_id)
            return
        if packet.ttl > 0 and packet.proto == self.config.mode and packet.type != "echo" and sender:
            self.health_checker.record_activity(sender)
        self.forwarding_engine.handle_packet(packet, from_neighbor_id=sender)

    def _on_echo_received(self, packet: Packet) -> None:
        t0 = packet.header("t0")
        if not isinstance(t0, bool) and isinstance(t0, (int, float)) and math.isfinite(t0):
            self.health_checker.record_echo(packet.from_, packet.id, t0)

    def _on_neighbor_status_change(self, neighbor_id: str, is_up: bool) -> None:
        self.forwarding_engine.announce_own_lsp()
        if is_up:
            self.forwarding_engine.send_lsdb_snapshot(neighbor_id)
        else:
            self.forwarding_engine.forget_lsdb_sync(neighbor_id)

    def update_neighbor_cost(self, neighbor_id: str, cost: float) -> None:
        if self.neighbor_table.update_cost(self.addresses.resolve(neighbor_id), cost):
            self.forwarding_engine.announce_own_lsp()

    def _default_on_message_delivered(self, packet: Packet) -> None:
        print(f"[{self.node_id}] << mensaje de {self.addresses.display(packet.from_)} ({packet.from_}): {packet.payload}")

    def _routing_loop(self) -> None:
        interval = self.config.params.lsp_refresh_interval_sec
        next_refresh = time.monotonic() + interval
        while not self._routing_stop.wait(min(0.25, interval)):
            try:
                expired = self.routing_engine.expire()
                if expired:
                    logger.info("[%s] LSP expirados: %s", self.node_id, expired)
                if time.monotonic() >= next_refresh:
                    self.forwarding_engine.announce_own_lsp()
                    next_refresh = time.monotonic() + interval
            except Exception:
                logger.exception("[%s] fallo de mantenimiento LSR", self.node_id)

    def start(self) -> None:
        self._stopping.clear()
        self._server.start()
        if self.config.mode == "lsr":
            self.forwarding_engine.announce_own_lsp()
            self._routing_stop.clear()
            self._routing_thread = threading.Thread(target=self._routing_loop, daemon=True)
            self._routing_thread.start()
        self.health_checker.start()
        logger.info("[%s] iniciado como %s, modo=%s", self.node_id, self.address, self.config.mode)

    def stop(self) -> None:
        self._stopping.set()
        self._routing_stop.set()
        self.health_checker.stop()
        self._server.stop()
        for link in self._links.values():
            link.close()
        if self._routing_thread:
            self._routing_thread.join(timeout=1)

    def send_message(self, destination: str, text: str) -> None:
        self.forwarding_engine.send_user_message(self.addresses.resolve(destination), text)

    def list_neighbors(self) -> list:
        return [self.neighbor_table.get(nid) for nid in self.neighbor_table.all_ids()]

    def list_routes(self) -> dict:
        return {self.addresses.display(dest):
                replace(entry, destination=self.addresses.display(dest),
                        next_hop=self.addresses.display(entry.next_hop))
                for dest, entry in self.routing_engine.routes().items()}
