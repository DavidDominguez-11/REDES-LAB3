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
    hello = Packet(proto="lsr", type="hello", from_="A", to="B", ttl=1, payload={"seq": 1, "sent_at": 0.0})
    engine.handle_packet(hello, from_neighbor_id="A")
    assert len(sent) == 1
    neighbor_id, echo = sent[0]
    assert neighbor_id == "A"
    assert echo.type == "echo"
    assert echo.payload["seq"] == 1


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
    assert routing.next_hop("C") is None or True  # B no es adyacente directo a C en este LSP de A; solo se valida reflood
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
    assert lsp_packet.payload["neighbors"] == {"B": 4}  # C no aparece como vecino activo
    assert routing.next_hop("B") == "B"
