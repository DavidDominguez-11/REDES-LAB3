"""Orquestador de un nodo de la red.

Arquitectura de hilos (ver docs/arquitectura.md):
- Un hilo de aceptación de conexiones TCP (`TcpServer`).
- Un hilo por conexión entrante, que hace de "forwarding": parsea cada línea
  NDJSON y llama a `ForwardingEngine.handle_packet` (entrega/reenvío,
  dedup, TTL, actualización de rutas).
- Un hilo de "routing/mantenimiento" (`HealthChecker`): sondea vecinos con
  HELLO/ECHO a intervalos configurables y, ante caída o recuperación,
  dispara el reanuncio del LSP propio (solo en modo `lsr`).

Todos estos hilos comparten, de forma thread-safe, `NeighborTable`,
`DedupCache` y `RoutingEngine`.
"""
from __future__ import annotations

import logging
import threading
import time

from router.config.loader import ConfigError, load_node_config, load_topology
from router.config.models import NodeConfig
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
        self.node_id = config.node_id

        static_topology = None
        if config.mode == "dijkstra":
            static_topology = load_topology(f"{repo_root}/{config.topology_file}")

        self.neighbor_table = NeighborTable(config.neighbors)
        self.dedup_cache = DedupCache(ttl_sec=config.params.dedup_cache_ttl_sec)
        self.routing_engine = RoutingEngine(config.node_id, mode=config.mode, static_topology=static_topology)

        self._links: dict[str, NeighborLink] = {
            n.node_id: NeighborLink(n.host, n.port) for n in config.neighbors
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
        )

        self._server = TcpServer(config.host, config.port, on_packet=self._on_packet_received)

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

    # ------------------------------------------------------------------ #
    @classmethod
    def from_config_path(cls, path: str, repo_root: str = ".") -> "Node":
        cfg = load_node_config(path)
        return cls(cfg, repo_root=repo_root)

    # ------------------------------------------------------------------ #
    def _send_to_neighbor(self, neighbor_id: str, packet: Packet) -> None:
        link = self._links.get(neighbor_id)
        if link is None:
            logger.warning("[%s] no existe enlace configurado hacia %s", self.node_id, neighbor_id)
            return
        try:
            link.send(packet)
        except OSError as exc:
            logger.debug("[%s] no se pudo enviar a %s (probablemente caído): %s", self.node_id, neighbor_id, exc)

    def _on_packet_received(self, packet: Packet) -> None:
        # `from` se actualiza en cada salto para representar al emisor directo
        # (ver docs/protocolo.md), así que identifica de forma confiable al
        # vecino inmediato del que llegó este paquete.
        self.forwarding_engine.handle_packet(packet, from_neighbor_id=packet.from_)

    def _on_echo_received(self, packet: Packet) -> None:
        seq = packet.payload.get("seq")
        if seq is not None:
            self.health_checker.record_echo(packet.from_, seq)

    def _on_neighbor_status_change(self, neighbor_id: str, is_up: bool) -> None:
        logger.info("[%s] vecino %s cambia a %s", self.node_id, neighbor_id, "activo" if is_up else "inactivo")
        self.forwarding_engine.announce_own_lsp()

    def _default_on_message_delivered(self, packet: Packet) -> None:
        print(f"[{self.node_id}] << mensaje de {packet.from_}: {packet.payload}")

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self._server.start()
        self.health_checker.start()
        if self.config.mode == "lsr":
            time.sleep(0.2)  # da tiempo a que los demás nodos ya estén escuchando
            self.forwarding_engine.announce_own_lsp()
        logger.info("[%s] nodo iniciado en %s:%s modo=%s", self.node_id, self.config.host, self.config.port, self.config.mode)

    def stop(self) -> None:
        self.health_checker.stop()
        self._server.stop()
        for link in self._links.values():
            link.close()

    # ------------------------------------------------------------------ #
    def send_message(self, destination: str, text: str) -> None:
        self.forwarding_engine.send_user_message(destination, text)

    def list_neighbors(self) -> list:
        result = []
        for nid in self.neighbor_table.all_ids():
            n = self.neighbor_table.get(nid)
            result.append(n)
        return result

    def list_routes(self) -> dict:
        return self.routing_engine.routes()
