from router.config.models import NeighborConfig
from router.neighbors.health_check import HealthChecker
from router.neighbors.table import NeighborTable


def _make_checker(max_failures=3, interval=1.0, timeout=0.5):
    neighbors = [NeighborConfig("B", "127.0.0.1", 6001, cost=4)]
    table = NeighborTable(neighbors)
    fake_time = [0.0]
    sent_hellos: list = []

    def send_hello(neighbor_id, seq):
        sent_hellos.append((neighbor_id, seq))

    status_changes: list = []

    checker = HealthChecker(
        node_id="A",
        neighbor_table=table,
        send_hello=send_hello,
        interval_sec=interval,
        timeout_sec=timeout,
        max_failures=max_failures,
        on_status_change=lambda nid, up: status_changes.append((nid, up)),
        clock=lambda: fake_time[0],
    )
    return checker, table, fake_time, sent_hellos, status_changes


def test_tick_sends_hello_to_every_neighbor():
    checker, _table, _t, sent, _changes = _make_checker()
    checker.tick()
    assert sent == [("B", 1)]


def test_successful_echo_keeps_neighbor_up_and_records_rtt():
    checker, table, fake_time, _sent, changes = _make_checker()
    checker.tick()  # envía hello seq=1 en t=0
    fake_time[0] = 0.2
    checker.record_echo("B", seq=1)
    assert table.get("B").is_up is True
    assert table.get("B").last_rtt_sec == 0.2
    assert changes == []  # no cambió de estado (ya estaba activo)


def test_neighbor_marked_down_after_max_consecutive_failures():
    checker, table, fake_time, sent, changes = _make_checker(max_failures=3, interval=1.0, timeout=0.5)

    # Cada tick() primero evalúa el timeout del HELLO pendiente del ciclo
    # anterior y luego envía uno nuevo, así que se necesitan max_failures + 1
    # ticks para que el último fallo (el 3ro) sea evaluado.
    for i in range(4):
        checker.tick()
        if i < 3:
            fake_time[0] += 1.0  # avanza más allá del timeout antes del siguiente tick

    assert table.get("B").is_up is False
    assert changes == [("B", False)]
    assert len(sent) == 4


def test_neighbor_not_marked_down_before_reaching_max_failures():
    checker, table, fake_time, _sent, changes = _make_checker(max_failures=3, interval=1.0, timeout=0.5)
    checker.tick()
    fake_time[0] += 1.0
    checker.tick()  # solo 1 fallo acumulado tras este tick
    assert table.get("B").is_up is True
    assert changes == []


def test_recovery_after_being_marked_down():
    checker, table, fake_time, sent, changes = _make_checker(max_failures=2, interval=1.0, timeout=0.5)

    for i in range(3):  # max_failures + 1 ticks para que se evalúe el 2do fallo
        checker.tick()
        if i < 2:
            fake_time[0] += 1.0
    assert table.get("B").is_up is False
    assert changes == [("B", False)]

    # Ahora llega un ECHO correspondiente al último hello enviado
    last_seq = sent[-1][1]
    fake_time[0] += 0.1
    checker.record_echo("B", seq=last_seq)

    assert table.get("B").is_up is True
    assert changes == [("B", False), ("B", True)]


def test_stale_echo_after_timeout_is_ignored():
    checker, table, fake_time, sent, changes = _make_checker(max_failures=5, interval=1.0, timeout=0.5)
    checker.tick()  # hello seq=1
    fake_time[0] = 10.0  # muy tarde
    checker.tick()  # nuevo hello seq=2, seq=1 ya no está pendiente (se limpió por timeout)
    checker.record_echo("B", seq=1)  # eco tardío del seq viejo
    assert table.get("B").is_up is True  # no rompe nada, se ignora silenciosamente
    assert table.get("B").last_rtt_sec is None  # no se registró como éxito


def test_failure_counter_resets_on_success():
    checker, table, fake_time, _sent, _changes = _make_checker(max_failures=3, interval=1.0, timeout=0.5)
    checker.tick()
    fake_time[0] += 1.0  # 1 fallo
    checker.tick()
    assert table.get("B").consecutive_failures == 1
    last_seq = 2
    fake_time[0] += 0.1
    checker.record_echo("B", seq=last_seq)
    assert table.get("B").consecutive_failures == 0
