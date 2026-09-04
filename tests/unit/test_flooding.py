from router.algorithms.flooding import originate_broadcast, process_incoming_packet
from router.dedup.cache import DedupCache
from router.protocol.packet import Packet


def _msg(from_="A", to="E", ttl=3, pkt_id="pkt-1"):
    return Packet(proto="flooding", type="message", from_=from_, to=to, ttl=ttl, payload="hola", id=pkt_id)


def test_forwards_to_all_neighbors_except_sender():
    cache = DedupCache(ttl_sec=30)
    pkt = _msg(from_="A", to="E", ttl=3)
    decision = process_incoming_packet(pkt, node_id="B", neighbor_ids=["A", "C", "D"], exclude_neighbor_id="A", dedup_cache=cache)
    assert set(decision.forward_to) == {"C", "D"}
    assert decision.deliver_locally is False
    assert decision.forwarded_packet.ttl == 2
    assert decision.forwarded_packet.from_ == "A"
    assert decision.forwarded_packet.header("via") == "B"


def test_delivers_locally_when_addressed_to_self_and_stops_forwarding():
    cache = DedupCache(ttl_sec=30)
    pkt = _msg(from_="A", to="B", ttl=3)
    decision = process_incoming_packet(pkt, node_id="B", neighbor_ids=["A", "C"], exclude_neighbor_id="A", dedup_cache=cache)
    assert decision.deliver_locally is True
    assert decision.forward_to == []
    assert decision.forwarded_packet is None


def test_broadcast_delivers_locally_and_keeps_forwarding():
    cache = DedupCache(ttl_sec=30)
    pkt = _msg(from_="A", to="*", ttl=3)
    decision = process_incoming_packet(pkt, node_id="B", neighbor_ids=["A", "C"], exclude_neighbor_id="A", dedup_cache=cache)
    assert decision.deliver_locally is True
    assert decision.forward_to == ["C"]


def test_ttl_zero_is_dropped():
    cache = DedupCache(ttl_sec=30)
    pkt = _msg(ttl=0)
    decision = process_incoming_packet(pkt, node_id="B", neighbor_ids=["A", "C"], exclude_neighbor_id="A", dedup_cache=cache)
    assert decision.dropped_reason == "ttl_expired"
    assert decision.forward_to == []
    assert decision.deliver_locally is False


def test_duplicate_packet_is_dropped_without_reprocessing():
    cache = DedupCache(ttl_sec=30)
    pkt = _msg(pkt_id="dup-1")
    first = process_incoming_packet(pkt, node_id="B", neighbor_ids=["A", "C"], exclude_neighbor_id="A", dedup_cache=cache)
    assert first.dropped_reason is None

    second = process_incoming_packet(pkt, node_id="B", neighbor_ids=["A", "C"], exclude_neighbor_id="A", dedup_cache=cache)
    assert second.dropped_reason == "duplicate"
    assert second.forward_to == []


def test_no_infinite_reflooding_across_a_small_ring():
    """Simula flooding en un anillo A-B-C-A: el mismo id nunca debe reenviarse
    más de una vez por nodo, gracias a la deduplicación (no debe haber loops)."""
    neighbors = {"A": ["B", "C"], "B": ["A", "C"], "C": ["A", "B"]}
    caches = {n: DedupCache(ttl_sec=30) for n in neighbors}
    forwards_processed: dict[str, int] = {n: 0 for n in neighbors}

    origin_pkt = _msg(from_="A", to="*", ttl=5, pkt_id="broadcast-1")
    origin_decision = originate_broadcast(origin_pkt, neighbor_ids=neighbors["A"], dedup_cache=caches["A"])

    # cola de (destino, emisor_anterior, paquete)
    queue = [(dst, "A", origin_decision.forwarded_packet) for dst in origin_decision.forward_to]

    while queue:
        node_id, sender, pkt = queue.pop()
        forwards_processed[node_id] += 1
        decision = process_incoming_packet(
            pkt, node_id=node_id, neighbor_ids=neighbors[node_id], exclude_neighbor_id=sender, dedup_cache=caches[node_id]
        )
        for dst in decision.forward_to:
            queue.append((dst, node_id, decision.forwarded_packet))

    # Cada nodo procesa el paquete original como máximo una vez por vecino que se lo envía,
    # y gracias al dedup no vuelve a reenviarlo en bucle infinito.
    assert forwards_processed["B"] <= 2
    assert forwards_processed["C"] <= 2
