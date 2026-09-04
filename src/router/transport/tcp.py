"""TCP persistente; lee tanto conexiones entrantes como salientes."""
from __future__ import annotations

import logging
import socket
import threading

from router.protocol.packet import Packet, PacketValidationError
from router.transport.ndjson import LineBuffer, encode_line

logger = logging.getLogger(__name__)


def _close(sock) -> None:
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()


def _handle_line(line: bytes, on_packet, on_malformed=None) -> None:
    if not line.strip():
        return
    try:
        packet = Packet.from_json(line.decode("utf-8"))
    except (PacketValidationError, UnicodeDecodeError) as exc:
        logger.warning("Paquete descartado (inválido): %s", exc)
        if on_malformed:
            on_malformed(line, exc)
        return
    try:
        on_packet(packet)
    except Exception:
        logger.exception("Error procesando paquete de %s; se descarta", packet.from_)


class TcpServer:
    def __init__(self, host: str, port: int, on_packet, on_malformed=None, on_peer_packet=None) -> None:
        self._host, self._port = host, port
        self._on_packet, self._on_malformed = on_packet, on_malformed
        self._on_peer_packet = on_peer_packet
        self._sock = None
        self._accept_thread = None
        self._client_socks = set()
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

    def stop(self) -> None:
        self._running.clear()
        _close(self._sock)
        with self._client_socks_lock:
            for sock in list(self._client_socks):
                _close(sock)
        if self._accept_thread:
            self._accept_thread.join(timeout=1)

    def _accept_loop(self) -> None:
        while self._running.is_set():
            try:
                conn, addr = self._sock.accept()
            except OSError:
                break
            with self._client_socks_lock:
                if not self._running.is_set():
                    _close(conn)
                    break
                self._client_socks.add(conn)
            threading.Thread(target=self._client_loop, args=(conn, addr), daemon=True).start()

    def _client_loop(self, conn, addr) -> None:
        buf = LineBuffer()
        peer_id = None

        def receive(packet):
            nonlocal peer_id
            via = packet.header("via")
            if packet.type in ("hello", "echo"):
                peer_id = packet.from_
            elif isinstance(via, str):
                peer_id = via
            if self._on_peer_packet:
                self._on_peer_packet(packet, peer_id, addr)
            else:
                self._on_packet(packet)

        try:
            while self._running.is_set():
                chunk = conn.recv(4096)
                if not chunk:
                    break
                for line in buf.feed(chunk):
                    _handle_line(line, receive, self._on_malformed)
        except OSError:
            pass
        finally:
            _close(conn)
            with self._client_socks_lock:
                self._client_socks.discard(conn)

    def _handle_line(self, line: bytes) -> None:
        _handle_line(line, self._on_packet, self._on_malformed)


class NeighborLink:
    def __init__(self, host: str, port: int, connect_timeout: float = 2.0, on_packet=None) -> None:
        self._host, self._port = host, port
        self._connect_timeout = connect_timeout
        self._on_packet = on_packet
        self._sock = None
        self._lock = threading.RLock()

    def _ensure_connected(self):
        if self._sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._connect_timeout)
            try:
                sock.connect((self._host, self._port))
            except OSError:
                sock.close()
                raise
            sock.settimeout(None)
            self._sock = sock
            if self._on_packet:
                threading.Thread(target=self._read_loop, args=(sock,), daemon=True).start()
        return self._sock

    def _read_loop(self, sock) -> None:
        buf = LineBuffer()
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                for line in buf.feed(chunk):
                    _handle_line(line, self._on_packet)
        except OSError:
            pass
        finally:
            with self._lock:
                if self._sock is sock:
                    self._reset()

    def send(self, packet: Packet) -> None:
        data = encode_line(packet.to_json())
        with self._lock:
            for attempt in range(2):
                try:
                    self._ensure_connected().sendall(data)
                    return
                except OSError:
                    self._reset()
                    if attempt:
                        raise

    def _reset(self) -> None:
        with self._lock:
            sock, self._sock = self._sock, None
            _close(sock)

    def close(self) -> None:
        self._reset()
