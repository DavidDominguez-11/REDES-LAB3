"""Sondeo de vecinos correlacionado por msg_id y t0 del HELLO/ECHO."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Callable

from router.neighbors.table import NeighborTable

logger = logging.getLogger(__name__)


class HealthChecker:
    def __init__(self, node_id: str, neighbor_table: NeighborTable,
                 send_hello: Callable[[str, str, float], None],
                 interval_sec: float, timeout_sec: float, max_failures: int,
                 on_status_change=None, clock=time.time) -> None:
        self.node_id = node_id
        self._table = neighbor_table
        self._send_hello = send_hello
        self._interval_sec = interval_sec
        self._timeout_sec = timeout_sec
        self._max_failures = max_failures
        self._on_status_change = on_status_change
        self._clock = clock
        self._pending: dict[str, tuple[str, float]] = {}
        self._last_heard: dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.tick()
            self._stop_event.wait(self._interval_sec)

    def tick(self) -> None:
        for nid in self._table.all_ids():
            now = self._clock()
            with self._lock:
                pending = self._pending.get(nid)
                timed_out = pending is not None and now - pending[1] >= self._timeout_sec
                if timed_out:
                    del self._pending[nid]
                elif pending is not None:
                    continue
            if timed_out and self._last_heard.get(nid, float("-inf")) < pending[1]:
                failures = self._table.record_failure(nid)
                if failures >= self._max_failures and self._table.mark_down(nid):
                    self._notify(nid, False)
            msg_id = str(uuid.uuid4())
            t0 = self._clock()
            with self._lock:
                self._pending[nid] = (msg_id, t0)
            self._send_hello(nid, msg_id, t0)

    def record_echo(self, neighbor_id: str, msg_id: str, t0: float) -> None:
        now = self._clock()
        with self._lock:
            pending = self._pending.get(neighbor_id)
            if pending is None or pending != (msg_id, t0):
                return
            if now - pending[1] >= self._timeout_sec:
                return
            del self._pending[neighbor_id]
        self._table.record_success(neighbor_id, rtt_sec=max(0, now - t0))
        if self._table.mark_up(neighbor_id):
            self._notify(neighbor_id, True)

    def record_activity(self, neighbor_id: str) -> None:
        """Tráfico de un vecino directo también confirma que sigue activo."""
        with self._lock:
            self._last_heard[neighbor_id] = self._clock()
        self._table.record_success(neighbor_id)
        if self._table.mark_up(neighbor_id):
            self._notify(neighbor_id, True)

    def _notify(self, neighbor_id: str, is_up: bool) -> None:
        logger.info("[%s] vecino %s %s", self.node_id, neighbor_id, "RECUPERADO" if is_up else "INACTIVO")
        if self._on_status_change:
            self._on_status_change(neighbor_id, is_up)
