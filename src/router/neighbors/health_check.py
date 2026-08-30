"""Health check de vecinos mediante HELLO/ECHO.

Cada vecino se sondea cada `hello_interval_sec`. Si no llega el ECHO
correspondiente dentro de `hello_timeout_sec`, se cuenta como fallo. Tras
`hello_max_failures` fallos CONSECUTIVOS, el vecino se marca inactivo y se
notifica (para que LSR reanuncie su LSP sin ese vecino y recalcule rutas).
Si luego se recibe un ECHO de un vecino marcado inactivo, se marca activo
de nuevo y también se notifica.

Diseñado como pieza independiente de sockets: solo necesita una función
`send_hello(neighbor_id, seq)` y quien lo use debe llamar
`record_echo(neighbor_id, seq)` cuando llegue la respuesta.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from router.neighbors.table import NeighborTable

logger = logging.getLogger(__name__)

OnStatusChange = Callable[[str, bool], None]  # (neighbor_id, is_up) -> None
SendHelloFn = Callable[[str, int], None]  # (neighbor_id, seq) -> None


class HealthChecker:
    def __init__(
        self,
        node_id: str,
        neighbor_table: NeighborTable,
        send_hello: SendHelloFn,
        interval_sec: float,
        timeout_sec: float,
        max_failures: int,
        on_status_change: Optional[OnStatusChange] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.node_id = node_id
        self._table = neighbor_table
        self._send_hello = send_hello
        self._interval_sec = interval_sec
        self._timeout_sec = timeout_sec
        self._max_failures = max_failures
        self._on_status_change = on_status_change
        self._clock = clock

        self._seq_counters: dict[str, int] = {n: 0 for n in neighbor_table.all_ids()}
        self._pending: dict[str, tuple[int, float]] = {}  # neighbor_id -> (seq, sent_at)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # -------------------------------------------------------------- #
    # Ciclo de vida
    # -------------------------------------------------------------- #
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

    # -------------------------------------------------------------- #
    # Lógica (testeable sin threads reales)
    # -------------------------------------------------------------- #
    def tick(self) -> None:
        """Un ciclo de sondeo: envía HELLO a cada vecino y evalúa timeouts pendientes."""
        now = self._clock()
        with self._lock:
            timed_out = [
                nid for nid, (_seq, sent_at) in self._pending.items() if now - sent_at > self._timeout_sec
            ]
        for nid in timed_out:
            self._on_timeout(nid)

        for nid in self._table.all_ids():
            with self._lock:
                seq = self._seq_counters.get(nid, 0) + 1
                self._seq_counters[nid] = seq
                self._pending[nid] = (seq, now)
            self._send_hello(nid, seq)

    def record_echo(self, neighbor_id: str, seq: int) -> None:
        """Debe llamarse cuando llega un ECHO. Calcula RTT y marca éxito."""
        now = self._clock()
        with self._lock:
            pending = self._pending.get(neighbor_id)
            if pending is None or pending[0] != seq:
                return  # echo tardío de un seq viejo, ya expirado; se ignora
            _seq, sent_at = pending
            del self._pending[neighbor_id]
        rtt = now - sent_at
        self._table.record_success(neighbor_id, rtt_sec=rtt)
        became_up = self._table.mark_up(neighbor_id)
        if became_up:
            logger.info("[%s] vecino %s RECUPERADO (rtt=%.3fs)", self.node_id, neighbor_id, rtt)
            if self._on_status_change:
                self._on_status_change(neighbor_id, True)

    def _on_timeout(self, neighbor_id: str) -> None:
        with self._lock:
            self._pending.pop(neighbor_id, None)
        failures = self._table.record_failure(neighbor_id)
        logger.debug("[%s] HELLO a %s sin respuesta (fallo %d/%d)", self.node_id, neighbor_id, failures, self._max_failures)
        if failures >= self._max_failures:
            became_down = self._table.mark_down(neighbor_id)
            if became_down:
                logger.warning("[%s] vecino %s marcado INACTIVO tras %d fallos", self.node_id, neighbor_id, failures)
                if self._on_status_change:
                    self._on_status_change(neighbor_id, False)
