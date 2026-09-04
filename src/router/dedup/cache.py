"""Caché de deduplicación de mensajes por `msg_id`.

Usada por flooding de mensajes para no
reprocesar ni reenviar un paquete ya visto -- así se evitan loops.
"""
from __future__ import annotations

import threading
import time


class DedupCache:
    def __init__(self, ttl_sec: float = 30.0, clock=time.monotonic) -> None:
        self._ttl_sec = ttl_sec
        self._clock = clock
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def seen_before(self, packet_id: str) -> bool:
        """Devuelve True si ya se vio este id (y no ha expirado). No lo registra."""
        with self._lock:
            self._evict_expired()
            return packet_id in self._seen

    def mark_seen(self, packet_id: str) -> None:
        with self._lock:
            self._seen[packet_id] = self._clock()

    def check_and_mark(self, packet_id: str) -> bool:
        """Operación atómica: devuelve True si YA estaba visto; si no, lo marca y devuelve False."""
        with self._lock:
            self._evict_expired()
            if packet_id in self._seen:
                return True
            self._seen[packet_id] = self._clock()
            return False

    def _evict_expired(self) -> None:
        now = self._clock()
        expired = [pid for pid, seen_at in self._seen.items() if now - seen_at > self._ttl_sec]
        for pid in expired:
            del self._seen[pid]

    def __len__(self) -> int:
        with self._lock:
            self._evict_expired()
            return len(self._seen)
