"""Interoperabilidad con JSON construido sin Packet ni factory."""
import json
import socket
import threading
import time
import uuid
import zlib

from router.config.models import NeighborConfig, NodeConfig, NodeParams
from router.node import Node
from router.transport.tcp import TcpServer


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def wire(kind, origin, destination, payload, extra=(), msg_id=None):
    raw = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {"version": 1, "proto": "lsr", "type": kind, "from": origin, "to": destination,
            "ttl": 1 if kind in ("hello", "echo") else 16,
            "headers": [{"msg_id": msg_id or str(uuid.uuid4())},
                        {"checksum": f"{zlib.crc32(raw.encode('utf-8')):08x}"}, *extra],
            "payload": payload}


def line(data):
    return (json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")


def test_external_peer_echoes_on_same_socket_and_exchanges_lsp_and_messages():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    remote_port = listener.getsockname()[1]
    temporary = socket.socket()
    temporary.bind(("127.0.0.1", 0))
    local_port = temporary.getsockname()[1]
    temporary.close()
    local, remote, far = f"127.0.0.1:{local_port}", f"127.0.0.1:{remote_port}", "10.0.0.7:5000"
    observed, errors, delivered = [], [], []
    connections = []
    stopping = threading.Event()

    def peer():
        try:
            conn, _ = listener.accept()
            connections.append(conn)
            with conn.makefile("rb") as stream:
                for raw in stream:
                    packet = json.loads(raw)
                    observed.append(packet)
                    headers = {k: v for h in packet["headers"] for k, v in h.items()}
                    assert "id" not in packet
                    assert set(packet) == {"version", "proto", "type", "from", "to", "ttl", "headers", "payload"}
                    assert "msg_id" in headers and "checksum" in headers
                    if packet["type"] == "hello":
                        assert packet["payload"] == {"listen_port": local_port}
                        echo = wire("echo", remote, local, {"listen_port": remote_port},
                                    [{"t0": headers["t0"]}], headers["msg_id"])
                        conn.sendall(line(echo))
                        # Variante textual y links/node/cost; destino remoto sin puerto.
                        info = wire("info", remote, "*", json.dumps({
                            "origin": remote, "seq": 7, "age_s": 0,
                            "links": [{"node": local, "cost": 2.5}, {"node": "10.0.0.7", "cost": 4.8}]
                        }))
                        conn.sendall(line(info))
                        message = wire("message", far, local, "¡hola desde G!", [{"via": remote}])
                        # El protocolo exige advertir y procesar estas discrepancias.
                        message["version"] = 2
                        message["headers"][1] = {"checksum": "00000000"}
                        conn.sendall(line(message))
        except (OSError, ValueError) as exc:
            if not stopping.is_set():
                errors.append(exc)
        except Exception as exc:
            errors.append(exc)

    node = Node(NodeConfig("A", "127.0.0.1", local_port, "lsr",
                         [NeighborConfig("B", "127.0.0.1", remote_port, 2.5)],
                         NodeParams(hello_interval_sec=0.2, hello_timeout_sec=0.15)))
    node.forwarding_engine._on_message_delivered = delivered.append
    worker = threading.Thread(target=peer, daemon=True)
    worker.start()
    try:
        node.start()
        assert wait_until(lambda: node.neighbor_table.get(remote).last_rtt_sec is not None)
        assert wait_until(lambda: node.routing_engine.next_hop(far) == remote)
        assert node.routing_engine.routes()[far].cost == 7.3
        node.send_message(far, "respuesta a G")
        assert wait_until(lambda: any(p["type"] == "message" for p in observed))
        sent = next(p for p in observed if p["type"] == "message")
        assert (sent["from"], sent["to"], sent["ttl"]) == (local, far, 16)
        assert wait_until(lambda: bool(delivered))
        assert delivered[0].from_ == far and delivered[0].payload == "¡hola desde G!"
        own_lsp = next(p for p in observed if p["type"] == "info")
        assert own_lsp["payload"]["neighbors"] == [{"id": remote, "weight": 2.5}]
        assert not errors
    finally:
        stopping.set()
        node.stop()
        for conn in connections:
            conn.close()
        listener.close()
        worker.join(timeout=1)


def test_incoming_connection_remembers_previous_hop_without_via_and_survives_oversize():
    received = []
    server = TcpServer("127.0.0.1", 0, lambda p: None,
                       on_peer_packet=lambda p, sender, peer: received.append((p, sender)))
    server.start()
    sock = socket.create_connection(server._sock.getsockname())
    try:
        a, b, c = "10.0.0.1:5000", "10.0.0.2:5000", "10.0.0.3:5000"
        sock.sendall(line(wire("hello", a, b, {"listen_port": 5000}, [{"t0": 1}])))
        sock.sendall(b"x" * 70000 + b"\n")
        sock.sendall(line(wire("message", c, b, "reenviado sin via")))
        assert wait_until(lambda: len(received) == 2)
        assert received[1][0].from_ == c
        assert received[1][1] == a
    finally:
        sock.close()
        server.stop()
