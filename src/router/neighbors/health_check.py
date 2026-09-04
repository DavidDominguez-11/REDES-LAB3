"""Health check de vecinos mediante HELLO/ECHO."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from router.neighbors.table import NeighborTable
from router.protocol.packet import Packet

logger = logging.getLogger(__name__)

OnStatusChange = Callable[[str, bool], None]
SendHelloFn = Callable[[str, int], Packet | None]


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
        clock: Callable[[], float] = time.time,
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
        # neighbor -> (seq, msg_id, t0, local_send_time)
        self._pending: dict[str, tuple[int, str | None, float | None, float]] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

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
        """Evalúa timeouts y sondea también a vecinos marcados como caídos."""
        now = self._clock()
        with self._lock:
            timed_out = [
                nid
                for nid, (_seq, _msg_id, _t0, sent_at) in self._pending.items()
                if now - sent_at > self._timeout_sec
            ]
        for nid in timed_out:
            self._on_timeout(nid)

        for nid in self._table.all_ids():
            with self._lock:
                seq = self._seq_counters.get(nid, 0) + 1
                self._seq_counters[nid] = seq
                self._pending[nid] = (seq, None, None, now)
            packet = self._send_hello(nid, seq)
            msg_id = packet.msg_id if isinstance(packet, Packet) else None
            t0 = packet.header("t0") if isinstance(packet, Packet) else None
            with self._lock:
                if self._pending.get(nid, (None, None, None, None))[0] == seq:
                    self._pending[nid] = (seq, msg_id, t0, now)

    def record_echo(
        self,
        neighbor_id: str,
        seq: int | None = None,
        *,
        msg_id: str | None = None,
        t0: float | None = None,
    ) -> None:
        """Acepta un ECHO solo si corresponde al HELLO aún pendiente."""
        now = self._clock()
        with self._lock:
            pending = self._pending.get(neighbor_id)
            if pending is None:
                return
            pending_seq, pending_id, pending_t0, sent_at = pending
            if msg_id is not None:
                matches = pending_id == msg_id if pending_id is not None else True
            elif t0 is not None and pending_t0 is not None:
                matches = pending_t0 == t0
            else:
                matches = seq == pending_seq
            if not matches:
                return
            del self._pending[neighbor_id]

        # t0 es del reloj del emisor y vuelve intacto en el ECHO. Al calcular
        # contra ese mismo reloj no hace falta sincronizar máquinas distintas.
        rtt = max(0.0, now - pending_t0) if pending_t0 is not None else max(0.0, now - sent_at)
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
        logger.debug(
            "[%s] HELLO a %s sin respuesta (fallo %d/%d)",
            self.node_id,
            neighbor_id,
            failures,
            self._max_failures,
        )
        if failures >= self._max_failures:
            became_down = self._table.mark_down(neighbor_id)
            if became_down:
                logger.warning(
                    "[%s] vecino %s marcado INACTIVO tras %d fallos",
                    self.node_id,
                    neighbor_id,
                    failures,
                )
                if self._on_status_change:
                    self._on_status_change(neighbor_id, False)
