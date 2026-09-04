from router.config.models import NeighborConfig
from router.dedup.cache import DedupCache
from router.forwarding.engine import ForwardingEngine
from router.neighbors.table import NeighborTable
from router.protocol.packet import Packet
from router.routing.engine import RoutingEngine


def _make_engine(node_id, mode, neighbor_ids_costs, on_delivered=None):
    neighbors = [NeighborConfig(nid, "127.0.0.1", 6000, cost) for nid, cost in neighbor_ids_costs.items()]
    table = NeighborTable(neighbors)
    routing = RoutingEngine(node_id, mode=mode)
    sent: list = []

    def send_to_neighbor(neighbor_id, packet):
        sent.append((neighbor_id, packet))

    engine = ForwardingEngine(
        node_id=node_id,
        mode=mode,
        neighbor_table=table,
        routing_engine=routing,
        dedup_cache=DedupCache(ttl_sec=30),
        send_to_neighbor=send_to_neighbor,
        initial_ttl=5,
        on_message_delivered=on_delivered,
    )
    return engine, table, routing, sent


def test_hello_triggers_echo_response():
    engine, _, _, sent = _make_engine("B", "lsr", {"A": 4})
    hello = Packet(proto="lsr", type="hello", from_="A", to="B", ttl=1, payload={"listen_port": 5000}, headers=[{"t0": 0.0}])
    engine.handle_packet(hello, from_neighbor_id="A")
    assert len(sent) == 1
    neighbor_id, echo = sent[0]
    assert neighbor_id == "A"
    assert echo.type == "echo"
    assert echo.id == hello.id
    assert echo.header("t0") == 0.0
    assert echo.payload == {"listen_port": 5000}


def test_echo_triggers_callback():
    received = []
    engine, _, _, _sent = _make_engine("A", "lsr", {"B": 4})
    engine._on_echo_received = received.append
    echo = Packet(proto="lsr", type="echo", from_="B", to="A", ttl=1, payload={"seq": 1})
    engine.handle_packet(echo, from_neighbor_id="B")
    assert len(received) == 1


def test_flooding_message_forwards_to_all_except_sender():
    engine, _, _, sent = _make_engine("B", "flooding", {"A": 1, "C": 1, "D": 1})
    pkt = Packet(proto="flooding", type="message", from_="A", to="Z", ttl=5, payload="hola", id="m1")
    engine.handle_packet(pkt, from_neighbor_id="A")
    assert {n for n, _ in sent} == {"C", "D"}


def test_flooding_delivers_when_addressed_to_self():
    delivered = []
    engine, _, _, sent = _make_engine("B", "flooding", {"A": 1, "C": 1}, on_delivered=delivered.append)
    pkt = Packet(proto="flooding", type="message", from_="A", to="B", ttl=5, payload="hola B", id="m2")
    engine.handle_packet(pkt, from_neighbor_id="A")
    assert len(delivered) == 1
    assert sent == []  # no reenvía más, ya llegó a destino


def test_routed_mode_forwards_via_next_hop_from_lsr_table():
    engine, table, routing, sent = _make_engine("A", "lsr", {"B": 4, "C": 1})
    routing.apply_lsp("A", 1, {"B": 4, "C": 1})
    routing.apply_lsp("C", 1, {"A": 1, "E": 6})
    routing.apply_lsp("E", 1, {"C": 6})
    pkt = Packet(proto="lsr", type="message", from_="A", to="E", ttl=5, payload="hola E", id="m3")
    engine.handle_packet(pkt, from_neighbor_id="A")
    assert len(sent) == 1
    neighbor_id, forwarded = sent[0]
    assert neighbor_id == "C"  # next hop hacia E
    assert forwarded.ttl == 4
    assert forwarded.from_ == "A"


def test_routed_mode_delivers_locally_when_destination_is_self():
    delivered = []
    engine, _, routing, sent = _make_engine("E", "lsr", {"C": 6}, on_delivered=delivered.append)
    pkt = Packet(proto="lsr", type="message", from_="A", to="E", ttl=3, payload="hola", id="m4")
    engine.handle_packet(pkt, from_neighbor_id="C")
    assert len(delivered) == 1
    assert sent == []


def test_routed_mode_drops_without_route():
    engine, _, _, sent = _make_engine("A", "lsr", {"B": 4})
    pkt = Packet(proto="lsr", type="message", from_="A", to="Z", ttl=5, payload="hola", id="m5")
    engine.handle_packet(pkt, from_neighbor_id="B")
    assert sent == []


def test_info_packet_applies_lsp_and_refloods_when_new():
    engine, _, routing, sent = _make_engine("B", "lsr", {"A": 4, "C": 2, "D": 5})
    info = Packet(
        proto="lsr", type="info", from_="A", to="*", ttl=5,
        payload={"origin": "A", "seq": 1, "neighbors": {"C": 1}}, id="lsp-1",
    )
    engine.handle_packet(info, from_neighbor_id="A")
    assert "A" in routing.known_lsp_origins()
    assert {n for n, _ in sent} == {"C", "D"}  # reenvía a todos menos a quien lo envió (A)


def test_info_packet_stale_seq_is_not_reflooded():
    engine, _, routing, sent = _make_engine("B", "lsr", {"A": 4, "C": 2})
    routing.apply_lsp("A", 5, {"C": 1})
    info = Packet(
        proto="lsr", type="info", from_="A", to="*", ttl=5,
        payload={"origin": "A", "seq": 2, "neighbors": {"C": 999}}, id="lsp-old",
    )
    engine.handle_packet(info, from_neighbor_id="A")
    assert sent == []


def test_send_user_message_flooding_originates_broadcast():
    engine, _, _, sent = _make_engine("A", "flooding", {"B": 1, "C": 1})
    engine.send_user_message("Z", "hola a todos")
    assert {n for n, _ in sent} == {"B", "C"}


def test_announce_own_lsp_floods_active_neighbors_only():
    engine, table, routing, sent = _make_engine("A", "lsr", {"B": 4, "C": 1})
    table.mark_down("C")  # C caído: no debe aparecer en el LSP propio ni recibir el reenvío
    engine.announce_own_lsp()
    assert {n for n, _ in sent} == {"B"}  # solo se reenvía por enlaces activos
    _, lsp_packet = sent[0]
    assert lsp_packet.payload["neighbors"] == [{"id": "B", "weight": 4}]  # C no aparece como vecino activo
    assert routing.next_hop("B") == "B"


# --------------------------------------------------------------------------- #
# Robustez: un paquete inesperado no debe reventar el manejo de la conexión.
# Todos estos casos aparecen en la prueba conjunta, donde llegan paquetes de
# implementaciones de otros grupos (docs/protocolo.md).
# --------------------------------------------------------------------------- #
def test_info_packet_is_ignored_outside_lsr_mode():
    """Un nodo en flooding/dijkstra no tiene LSDB: debe ignorar el LSP, no fallar."""
    engine, _, _, sent = _make_engine("B", "flooding", {"A": 1, "C": 1})
    info = Packet(
        proto="lsr", type="info", from_="A", to="*", ttl=5,
        payload={"origin": "A", "seq": 1, "neighbors": {"C": 1}}, id="lsp-x",
    )
    engine.handle_packet(info, from_neighbor_id="A")
    assert sent == []


def test_info_packet_with_non_dict_payload_is_discarded():
    engine, _, _, sent = _make_engine("B", "lsr", {"A": 4, "C": 2})
    info = Packet(proto="lsr", type="info", from_="A", to="*", ttl=5, payload="no soy un objeto", id="lsp-y")
    engine.handle_packet(info, from_neighbor_id="A")
    assert sent == []


def test_info_packet_with_missing_origin_is_discarded():
    engine, _, _, sent = _make_engine("B", "lsr", {"A": 4, "C": 2})
    info = Packet(
        proto="lsr", type="info", from_="A", to="*", ttl=5,
        payload={"seq": 1, "neighbors": {"C": 1}}, id="lsp-z",
    )
    engine.handle_packet(info, from_neighbor_id="A")
    assert sent == []


def test_info_packet_with_string_costs_is_accepted():
    """Tolerancia a otra implementación que serialice los costos como texto.

    El costo se normaliza a número al aplicarlo: dejarlo como string haría
    fallar la suma de distancias dentro de Dijkstra.
    """
    engine, _, routing, _sent = _make_engine("B", "lsr", {"A": 4, "C": 2})
    engine.announce_own_lsp()  # B necesita su propio LSP para poder calcular rutas
    info = Packet(
        proto="lsr", type="info", from_="A", to="*", ttl=5,
        payload={"origin": "A", "seq": 1, "neighbors": {"B": "4", "C": "1"}}, id="lsp-str",
    )
    engine.handle_packet(info, from_neighbor_id="A")

    lsp_de_a = {origin: neighbors for origin, _seq, neighbors in routing.lsdb_snapshot()}["A"]
    assert lsp_de_a == {"B": 4, "C": 1}
    assert routing.next_hop("A") == "A"


def test_info_packet_with_unparseable_cost_drops_only_that_neighbor():
    engine, _, routing, _sent = _make_engine("B", "lsr", {"A": 4})
    info = Packet(
        proto="lsr", type="info", from_="A", to="*", ttl=5,
        payload={"origin": "A", "seq": 1, "neighbors": {"B": 4, "C": "barato"}}, id="lsp-bad-cost",
    )
    engine.handle_packet(info, from_neighbor_id="A")
    lsp_de_a = {origin: neighbors for origin, _seq, neighbors in routing.lsdb_snapshot()}["A"]
    assert lsp_de_a == {"B": 4}


def test_echo_with_non_dict_payload_does_not_reach_callback():
    received = []
    engine, _, _, _sent = _make_engine("A", "lsr", {"B": 4})
    engine._on_echo_received = received.append
    echo = Packet(proto="lsr", type="echo", from_="B", to="A", ttl=1, payload="no soy un objeto")
    engine.handle_packet(echo, from_neighbor_id="B")
    assert received == []


def test_hello_with_non_dict_payload_still_gets_echo():
    """No responder dejaría que el vecino nos marque como caídos por timeout."""
    engine, _, _, sent = _make_engine("B", "lsr", {"A": 4})
    hello = Packet(proto="lsr", type="hello", from_="A", to="B", ttl=1, payload="no soy un objeto")
    engine.handle_packet(hello, from_neighbor_id="A")
    assert len(sent) == 1
    assert sent[0][1].type == "echo"


# --------------------------------------------------------------------------- #
# Sincronización de LSDB hacia un vecino que aparece
# --------------------------------------------------------------------------- #
def test_send_lsdb_snapshot_reenvia_todos_los_lsp_conocidos():
    engine, _, routing, sent = _make_engine("B", "lsr", {"A": 4, "C": 2})
    routing.apply_lsp("A", 3, {"B": 4})
    routing.apply_lsp("D", 7, {"C": 8})
    engine.send_lsdb_snapshot("C")

    assert {n for n, _ in sent} == {"C"}
    enviados = {p.payload["origin"]: p.payload for _, p in sent}
    assert enviados["A"]["seq"] == 3
    assert enviados["D"]["seq"] == 7
    assert enviados["D"]["neighbors"] == [{"id": "C", "weight": 8}]


def test_send_lsdb_snapshot_no_hace_nada_fuera_de_lsr():
    engine, _, _, sent = _make_engine("B", "flooding", {"A": 1})
    engine.send_lsdb_snapshot("A")
    assert sent == []


def test_primer_hello_de_un_vecino_dispara_volcado_de_lsdb():
    engine, _, routing, sent = _make_engine("B", "lsr", {"A": 4})
    routing.apply_lsp("D", 7, {"C": 8})
    hello = Packet(proto="lsr", type="hello", from_="A", to="B", ttl=1, payload={"listen_port": 5000}, headers=[{"t0": 0.0}])

    engine.handle_packet(hello, from_neighbor_id="A")
    tipos = [p.type for _, p in sent]
    assert tipos == ["echo", "info"]  # el ECHO va primero: no se retrasa el health check
    assert sent[1][1].payload["origin"] == "D"

    # El segundo HELLO ya no vuelve a volcar la LSDB.
    sent.clear()
    engine.handle_packet(hello, from_neighbor_id="A")
    assert [p.type for _, p in sent] == ["echo"]


def test_forget_lsdb_sync_permite_volver_a_sincronizar():
    engine, _, routing, sent = _make_engine("B", "lsr", {"A": 4})
    routing.apply_lsp("D", 7, {"C": 8})
    hello = Packet(proto="lsr", type="hello", from_="A", to="B", ttl=1, payload={"listen_port": 5000}, headers=[{"t0": 0.0}])
    engine.handle_packet(hello, from_neighbor_id="A")

    engine.forget_lsdb_sync("A")  # el vecino se marcó caído: pudo reiniciarse
    sent.clear()
    engine.handle_packet(hello, from_neighbor_id="A")
    assert [p.type for _, p in sent] == ["echo", "info"]


def test_hello_no_vuelca_lsdb_fuera_de_lsr():
    engine, _, _, sent = _make_engine("B", "flooding", {"A": 4})
    hello = Packet(proto="flooding", type="hello", from_="A", to="B", ttl=1, payload={"listen_port": 5000}, headers=[{"t0": 0.0}])
    engine.handle_packet(hello, from_neighbor_id="A")
    assert [p.type for _, p in sent] == ["echo"]
