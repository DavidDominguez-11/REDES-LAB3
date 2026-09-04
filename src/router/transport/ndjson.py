"""NDJSON UTF-8 con límite de 65536 bytes, sin contar el delimitador."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
MAX_LINE_BYTES = 65536


class LineBuffer:
    def __init__(self, max_line_bytes: int = MAX_LINE_BYTES) -> None:
        self._buffer = bytearray()
        self._discarding = False
        self._max_line_bytes = max_line_bytes

    def feed(self, chunk: bytes) -> list[bytes]:
        lines = []
        start = 0
        while start < len(chunk):
            end = chunk.find(b"\n", start)
            complete = end >= 0
            end = end if complete else len(chunk)
            if not self._discarding:
                if len(self._buffer) + end - start > self._max_line_bytes:
                    logger.warning("Línea NDJSON mayor que %d bytes; se descarta", self._max_line_bytes)
                    self._buffer.clear()
                    self._discarding = True
                else:
                    self._buffer.extend(chunk[start:end])
            if complete:
                if not self._discarding:
                    lines.append(bytes(self._buffer))
                self._buffer.clear()
                self._discarding = False
            start = end + 1
        return lines

    def pending_bytes(self) -> int:
        return len(self._buffer)


def encode_line(json_line: str) -> bytes:
    if "\n" in json_line:
        raise ValueError("La línea JSON no debe contener saltos de línea internos")
    data = json_line.encode("utf-8")
    if len(data) > MAX_LINE_BYTES:
        raise ValueError("La línea JSON supera 65536 bytes")
    return data + b"\n"
