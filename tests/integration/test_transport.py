import time

from router.protocol.packet import Packet
from router.transport.tcp import NeighborLink, TcpServer


def _free_port() -> int:
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_two_nodes_exchange_packet_over_tcp():
    received: list[Packet] = []
    port = _free_port()

    server = TcpServer("127.0.0.1", port, on_packet=received.append)
    server.start()
    time.sleep(0.1)

    link = NeighborLink("127.0.0.1", port)
    pkt = Packet(proto="flooding", type="message", from_="A", to="B", ttl=5, payload="hola B")
    link.send(pkt)

    deadline = time.time() + 2.0
    while not received and time.time() < deadline:
        time.sleep(0.02)

    assert len(received) == 1
    assert received[0].payload == "hola B"
    assert received[0].from_ == "A"

    link.close()
    server.stop()


def test_malformed_line_does_not_crash_server_and_next_packet_arrives():
    received: list[Packet] = []
    malformed: list[bytes] = []
    port = _free_port()

    server = TcpServer(
        "127.0.0.1", port, on_packet=received.append, on_malformed=lambda line, exc: malformed.append(line)
    )
    server.start()
    time.sleep(0.1)

    import socket as socket_mod

    raw = socket_mod.socket(socket_mod.AF_INET, socket_mod.SOCK_STREAM)
    raw.connect(("127.0.0.1", port))
    raw.sendall(b"esto no es json\n")
    good = Packet(proto="flooding", type="message", from_="A", to="B", ttl=5, payload="sigo vivo")
    raw.sendall((good.to_json() + "\n").encode("utf-8"))

    deadline = time.time() + 2.0
    while not received and time.time() < deadline:
        time.sleep(0.02)

    assert len(malformed) == 1
    assert len(received) == 1
    assert received[0].payload == "sigo vivo"

    raw.close()
    server.stop()


def test_neighbor_link_reconnects_after_drop():
    received: list[Packet] = []
    port = _free_port()

    server = TcpServer("127.0.0.1", port, on_packet=received.append)
    server.start()
    time.sleep(0.1)

    link = NeighborLink("127.0.0.1", port)
    link.send(Packet(proto="flooding", type="message", from_="A", to="B", ttl=5, payload="uno"))
    time.sleep(0.1)

    link.close()  # simula caída del lado del emisor

    link.send(Packet(proto="flooding", type="message", from_="A", to="B", ttl=5, payload="dos"))

    deadline = time.time() + 2.0
    while len(received) < 2 and time.time() < deadline:
        time.sleep(0.02)

    assert [p.payload for p in received] == ["uno", "dos"]

    link.close()
    server.stop()
