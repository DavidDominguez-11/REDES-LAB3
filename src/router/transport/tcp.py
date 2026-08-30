"""Transporte TCP para la red de nodos.

- `TcpServer`: escucha conexiones entrantes, una por vecino/cliente, y entrega
  cada paquete parseado a un callback. Un JSON inválido en una línea no
  detiene el nodo: se loguea y se sigue leyendo la conexión.
- `NeighborLink`: conexión saliente persistente hacia un vecino, con
  reconexión perezosa si el socket se cae (para health check / recuperación).

Todo el manejo de sockets vive aquí; el resto del sistema (forwarding,
routing, algorithms) solo conoce `Packet`, nunca sockets directamente.
"""
from __future__ import annotations

import logging
import socket
import threading
from typing import Callable, Optional

from router.protocol.packet import Packet, PacketValidationError
from router.transport.ndjson import LineBuffer, encode_line

logger = logging.getLogger(__name__)

OnPacket = Callable[[Packet], None]
OnMalformed = Callable[[bytes, Exception], None]


class TcpServer:
    """Servidor TCP que acepta múltiples conexiones entrantes concurrentes."""

    def __init__(
        self,
        host: str,
        port: int,
        on_packet: OnPacket,
        on_malformed: Optional[OnMalformed] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._on_packet = on_packet
        self._on_malformed = on_malformed
        self._sock: Optional[socket.socket] = None
        self._accept_thread: Optional[threading.Thread] = None
        self._client_threads: list[threading.Thread] = []
        self._client_socks: list[socket.socket] = []
        self._client_socks_lock = threading.Lock()
        self._running = threading.Event()

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._host, self._port))
        self._sock.listen()
        self._running.set()
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        logger.info("TcpServer escuchando en %s:%s", self._host, self._port)

    def stop(self) -> None:
        """Detiene el servidor: cierra el socket de escucha Y todas las
        conexiones ya aceptadas, para simular una caída real del nodo (si no
        se cerraran, una conexión ya establecida podría seguir respondiendo
        un rato más y el health check de los vecinos no detectaría la caída)."""
        self._running.clear()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        with self._client_socks_lock:
            socks = list(self._client_socks)
        for s in socks:
            try:
                s.close()
            except OSError:
                pass

    def _accept_loop(self) -> None:
        while self._running.is_set():
            try:
                conn, addr = self._sock.accept()
            except OSError:
                break  # socket cerrado por stop()
            with self._client_socks_lock:
                self._client_socks.append(conn)
            t = threading.Thread(target=self._client_loop, args=(conn, addr), daemon=True)
            t.start()
            self._client_threads.append(t)

    def _client_loop(self, conn: socket.socket, addr) -> None:
        buf = LineBuffer()
        try:
            while self._running.is_set():
                chunk = conn.recv(4096)
                if not chunk:
                    break  # peer cerró la conexión
                for line in buf.feed(chunk):
                    self._handle_line(line)
        except OSError:
            pass
        finally:
            conn.close()
            with self._client_socks_lock:
                if conn in self._client_socks:
                    self._client_socks.remove(conn)

    def _handle_line(self, line: bytes) -> None:
        if not line.strip():
            return
        try:
            packet = Packet.from_json(line.decode("utf-8"))
        except (PacketValidationError, UnicodeDecodeError) as exc:
            logger.warning("Paquete descartado (inválido): %s", exc)
            if self._on_malformed:
                self._on_malformed(line, exc)
            return
        self._on_packet(packet)


class NeighborLink:
    """Conexión saliente persistente y reconectable hacia un vecino."""

    def __init__(self, host: str, port: int, connect_timeout: float = 2.0) -> None:
        self._host = host
        self._port = port
        self._connect_timeout = connect_timeout
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()

    def _ensure_connected(self) -> socket.socket:
        with self._lock:
            if self._sock is None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self._connect_timeout)
                sock.connect((self._host, self._port))
                sock.settimeout(None)
                self._sock = sock
            return self._sock

    def send(self, packet: Packet) -> None:
        """Envía un paquete; si la conexión se había caído, reconecta antes de enviar."""
        data = encode_line(packet.to_json())
        try:
            sock = self._ensure_connected()
            sock.sendall(data)
        except OSError:
            self._reset()
            sock = self._ensure_connected()
            sock.sendall(data)

    def _reset(self) -> None:
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
            self._sock = None

    def close(self) -> None:
        self._reset()
