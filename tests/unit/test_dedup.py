import time

from router.dedup.cache import DedupCache


def test_check_and_mark_first_time_false():
    cache = DedupCache(ttl_sec=10)
    assert cache.check_and_mark("pkt-1") is False


def test_check_and_mark_second_time_true():
    cache = DedupCache(ttl_sec=10)
    cache.check_and_mark("pkt-1")
    assert cache.check_and_mark("pkt-1") is True


def test_seen_before_does_not_register():
    cache = DedupCache(ttl_sec=10)
    assert cache.seen_before("pkt-1") is False
    assert cache.seen_before("pkt-1") is False  # sigue sin registrarse
    assert len(cache) == 0


def test_entries_expire_after_ttl():
    fake_time = [0.0]
    cache = DedupCache(ttl_sec=5, clock=lambda: fake_time[0])
    cache.mark_seen("pkt-1")
    assert cache.seen_before("pkt-1") is True
    fake_time[0] = 10.0  # avanza más allá del ttl
    assert cache.seen_before("pkt-1") is False


def test_different_ids_are_independent():
    cache = DedupCache(ttl_sec=10)
    assert cache.check_and_mark("a") is False
    assert cache.check_and_mark("b") is False
    assert cache.check_and_mark("a") is True
    assert cache.check_and_mark("b") is True
