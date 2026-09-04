"""Framing NDJSON con límite de 65536 bytes por línea."""
from __future__ import annotations

from router.protocol.packet import MAX_LINE_BYTES


class LineTooLongError(ValueError):
    """Una línea NDJSON superó el máximo permitido."""


class LineBuffer:
    """Acumula bytes sin asumir que ``recv`` coincide con una línea."""

    def __init__(self, max_line_bytes: int = MAX_LINE_BYTES) -> None:
        self._max_line_bytes = max_line_bytes
        self._buffer = b""
        self._discarding = False
        self._oversized_lines = 0

    def feed(self, chunk: bytes) -> list[bytes]:
        if not chunk:
            return []
        lines: list[bytes] = []
        remaining = chunk
        while remaining:
            if self._discarding:
                if b"\n" not in remaining:
                    return lines
                _discarded, remaining = remaining.split(b"\n", 1)
                self._discarding = False
                self._oversized_lines += 1
                continue

            self._buffer += remaining
            remaining = b""
            while b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                if len(line) > self._max_line_bytes:
                    self._oversized_lines += 1
                else:
                    lines.append(line)
            if len(self._buffer) > self._max_line_bytes:
                self._buffer = b""
                self._discarding = True
        return lines

    def take_oversized_count(self) -> int:
        count = self._oversized_lines
        self._oversized_lines = 0
        return count

    def pending_bytes(self) -> int:
        return len(self._buffer)


def encode_line(json_line: str) -> bytes:
    """Codifica una línea JSON y valida el límite en bytes UTF-8."""
    if "\n" in json_line:
        raise ValueError("La línea JSON no debe contener '\\n' interno")
    encoded = (json_line + "\n").encode("utf-8")
    if len(encoded) - 1 > MAX_LINE_BYTES:
        raise LineTooLongError(f"La línea JSON supera {MAX_LINE_BYTES} bytes")
    return encoded
