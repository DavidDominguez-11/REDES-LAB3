"""Transporte TCP bidireccional para paquetes NDJSON."""
from __future__ import annotations

import logging
import socket
import threading
from typing import Callable, Optional

from router.protocol.packet import Packet, PacketValidationError
from router.transport.ndjson import LineBuffer, LineTooLongError, encode_line

logger = logging.getLogger(__name__)

OnPacket = Callable[[Packet], None]
OnPacketWithConnection = Callable[[Packet, socket.socket], None]
OnMalformed = Callable[[bytes, Exception], None]


class TcpServer:
    """Servidor TCP que procesa múltiples conexiones entrantes concurrentes."""

    def __init__(
        self,
        host: str,
        port: int,
        on_packet: OnPacket,
        on_malformed: Optional[OnMalformed] = None,
        on_packet_with_connection: Optional[OnPacketWithConnection] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._on_packet = on_packet
        self._on_packet_with_connection = on_packet_with_connection
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
        self._running.clear()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        with self._client_socks_lock:
            socks = list(self._client_socks)
        for conn in socks:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass

    def send_on_connection(self, conn: socket.socket, packet: Packet) -> None:
        """Responde por el mismo socket que recibió el paquete."""
        conn.sendall(encode_line(packet.to_json()))

    def _accept_loop(self) -> None:
        while self._running.is_set():
            try:
                conn, addr = self._sock.accept()  # type: ignore[union-attr]
            except OSError:
                break
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
                    break
                for line in buf.feed(chunk):
                    self._handle_line(line, conn)
                self._handle_oversized_lines(buf)
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass
            with self._client_socks_lock:
                if conn in self._client_socks:
                    self._client_socks.remove(conn)

    def _handle_oversized_lines(self, buf: LineBuffer) -> None:
        for _ in range(buf.take_oversized_count()):
            exc = LineTooLongError("Línea JSON descartada por superar 65536 bytes")
            logger.warning("Paquete descartado: %s", exc)
            if self._on_malformed:
                self._on_malformed(b"", exc)

    def _handle_line(self, line: bytes, conn: socket.socket | None = None) -> None:
        if not line.strip():
            return
        try:
            packet = Packet.from_json(line.decode("utf-8"))
        except (PacketValidationError, UnicodeDecodeError) as exc:
            logger.warning("Paquete descartado (inválido): %s", exc)
            if self._on_malformed:
                self._on_malformed(line, exc)
            return
        if self._on_packet_with_connection is not None and conn is not None:
            self._on_packet_with_connection(packet, conn)
        else:
            self._on_packet(packet)


class NeighborLink:
    """Conexión saliente persistente y reconectable hacia un vecino.

    Cuando se proporciona ``on_packet`` también se lee el socket saliente.
    Esto permite recibir ECHO o cualquier otro paquete que el vecino devuelva
    por la misma conexión TCP en la que llegó el envío.
    """

    def __init__(
        self,
        host: str,
        port: int,
        connect_timeout: float = 2.0,
        on_packet: Optional[OnPacket] = None,
        on_malformed: Optional[OnMalformed] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._connect_timeout = connect_timeout
        self._on_packet = on_packet
        self._on_malformed = on_malformed
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._read_stop: Optional[threading.Event] = None

    def _ensure_connected(self) -> socket.socket:
        with self._lock:
            if self._sock is None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self._connect_timeout)
                sock.connect((self._host, self._port))
                sock.settimeout(None)
                self._sock = sock
                if self._on_packet is not None:
                    self._read_stop = threading.Event()
                    threading.Thread(
                        target=self._read_loop,
                        args=(sock, self._read_stop),
                        daemon=True,
                    ).start()
            return self._sock

    def send(self, packet: Packet) -> None:
        data = encode_line(packet.to_json())
        try:
            sock = self._ensure_connected()
            sock.sendall(data)
        except OSError:
            self._reset()
            sock = self._ensure_connected()
            sock.sendall(data)

    def _read_loop(self, sock: socket.socket, stop_event: threading.Event) -> None:
        buf = LineBuffer()
        try:
            while not stop_event.is_set():
                chunk = sock.recv(4096)
                if not chunk:
                    break
                for line in buf.feed(chunk):
                    self._handle_incoming_line(line)
                for _ in range(buf.take_oversized_count()):
                    logger.warning("Paquete recibido descartado: línea demasiado larga")
        except OSError:
            pass
        finally:
            with self._lock:
                if self._sock is sock:
                    self._sock = None

    def _handle_incoming_line(self, line: bytes) -> None:
        if not line.strip():
            return
        try:
            packet = Packet.from_json(line.decode("utf-8"))
        except (PacketValidationError, UnicodeDecodeError) as exc:
            logger.warning("Paquete recibido inválido: %s", exc)
            if self._on_malformed:
                self._on_malformed(line, exc)
            return
        if self._on_packet:
            self._on_packet(packet)

    def _reset(self) -> None:
        with self._lock:
            if self._read_stop is not None:
                self._read_stop.set()
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
            self._sock = None
            self._read_stop = None

    def close(self) -> None:
        self._reset()
