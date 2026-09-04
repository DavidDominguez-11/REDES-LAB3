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


def test_concurrent_sends_do_not_corrupt_ndjson_framing():
    """Varios hilos comparten el mismo NeighborLink (health check + forwarding).

    `sendall` puede escribir en varias pasadas, así que sin exclusión mutua los
    bytes de dos paquetes se entrelazan y el receptor ve líneas JSON corruptas.
    Se usan payloads grandes para forzar escrituras parciales.
    """
    import threading

    received: list[Packet] = []
    malformed: list[bytes] = []
    port = _free_port()

    server = TcpServer(
        "127.0.0.1", port, on_packet=received.append, on_malformed=lambda line, exc: malformed.append(line)
    )
    server.start()
    time.sleep(0.1)

    link = NeighborLink("127.0.0.1", port)
    n_threads, n_each = 6, 100
    relleno = "x" * 20000

    def worker(k: int) -> None:
        for i in range(n_each):
            link.send(
                Packet(proto="lsr", type="message", from_="A", to="B", ttl=5, payload=f"{k}-{i}-{relleno}")
            )

    hilos = [threading.Thread(target=worker, args=(k,)) for k in range(n_threads)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    esperados = n_threads * n_each
    deadline = time.time() + 10.0
    while len(received) + len(malformed) < esperados and time.time() < deadline:
        time.sleep(0.05)

    assert malformed == [], f"{len(malformed)} líneas corruptas: los envíos concurrentes se entrelazaron"
    assert len(received) == esperados

    link.close()
    server.stop()


def test_handler_exception_does_not_close_the_connection():
    """Un paquete problemático no debe cerrar la conexión."""
    received: list[Packet] = []
    port = _free_port()

    def on_packet(packet: Packet) -> None:
        if packet.payload == "explota":
            raise RuntimeError("fallo simulado en el handler")
        received.append(packet)

    server = TcpServer("127.0.0.1", port, on_packet=on_packet)
    server.start()
    time.sleep(0.1)

    link = NeighborLink("127.0.0.1", port)
    link.send(Packet(proto="flooding", type="message", from_="A", to="B", ttl=5, payload="explota"))
    time.sleep(0.2)
    link.send(Packet(proto="flooding", type="message", from_="A", to="B", ttl=5, payload="sigo vivo"))

    deadline = time.time() + 2.0
    while not received and time.time() < deadline:
        time.sleep(0.02)

    assert [p.payload for p in received] == ["sigo vivo"]

    link.close()
    server.stop()
