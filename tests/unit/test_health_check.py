import uuid

from router.config.models import NeighborConfig
from router.neighbors.health_check import HealthChecker
from router.neighbors.table import NeighborTable


def make_checker(max_failures=3):
    table = NeighborTable([NeighborConfig("B", "127.0.0.1", 5000, 4.8)])
    clock, sent, changes = [0.0], [], []
    checker = HealthChecker("A", table, lambda *args: sent.append(args),
                            interval_sec=1, timeout_sec=0.5, max_failures=max_failures,
                            on_status_change=lambda *args: changes.append(args),
                            clock=lambda: clock[0])
    return checker, table, clock, sent, changes


def test_tick_sends_unique_uuid_and_t0():
    checker, _, clock, sent, _ = make_checker()
    checker.tick()
    assert sent[0][0] == "B" and sent[0][2] == 0
    assert uuid.UUID(sent[0][1]).version == 4
    clock[0] = 1
    checker.tick()
    assert sent[1][1] != sent[0][1]


def test_echo_correlates_and_records_rtt():
    checker, table, clock, sent, changes = make_checker()
    checker.tick()
    clock[0] = 0.2
    checker.record_echo(*sent[-1])
    assert table.get("B").last_rtt_sec == 0.2
    assert changes == []


def test_neighbor_down_after_consecutive_failures_and_recovers():
    checker, table, clock, sent, changes = make_checker()
    for i in range(4):
        clock[0] = i
        checker.tick()
        if i < 3:
            assert table.get("B").is_up
    assert not table.get("B").is_up
    assert changes == [("B", False)]
    clock[0] += 0.1
    checker.record_echo(*sent[-1])
    assert table.get("B").is_up
    assert changes == [("B", False), ("B", True)]


def test_stale_or_wrong_echo_cannot_reset_failures():
    checker, table, clock, sent, _ = make_checker()
    checker.tick()
    clock[0] = 1
    checker.tick()
    checker.record_echo(*sent[0])
    checker.record_echo("B", sent[-1][1], 0.99)
    assert table.get("B").consecutive_failures == 1
    assert table.get("B").last_rtt_sec is None
    clock[0] = 1.1
    checker.record_echo(*sent[-1])
    assert table.get("B").consecutive_failures == 0


def test_echo_after_timeout_before_next_tick_is_ignored():
    checker, table, clock, sent, _ = make_checker()
    checker.tick()
    clock[0] = 0.6
    checker.record_echo(*sent[-1])
    assert table.get("B").last_rtt_sec is None


def test_hearing_neighbor_keeps_it_active_and_allows_recovery():
    checker, table, clock, sent, changes = make_checker(max_failures=1)
    checker.tick()
    clock[0] = 0.2
    checker.record_activity("B")
    clock[0] = 1
    checker.tick()
    assert table.get("B").is_up
    clock[0] = 2
    checker.tick()
    assert not table.get("B").is_up
    checker.record_activity("B")
    assert table.get("B").is_up
    assert changes == [("B", False), ("B", True)]
