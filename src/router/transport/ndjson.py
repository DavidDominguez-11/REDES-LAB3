"""Framing NDJSON: cada paquete es una línea JSON terminada en '\\n'.

TCP es un stream de bytes sin límites de mensaje, así que este buffer
acumula bytes recibidos y va emitiendo líneas completas conforme llegan,
sin asumir que un recv() corresponde a un paquete completo.
"""
from __future__ import annotations


class LineBuffer:
    """Acumula bytes y va liberando líneas completas (sin el '\\n')."""

    def __init__(self) -> None:
        self._buffer = b""

    def feed(self, chunk: bytes) -> list[bytes]:
        """Agrega bytes recibidos y devuelve las líneas completas nuevas."""
        self._buffer += chunk
        lines: list[bytes] = []
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            lines.append(line)
        return lines

    def pending_bytes(self) -> int:
        """Bytes acumulados que aún no forman una línea completa."""
        return len(self._buffer)


def encode_line(json_line: str) -> bytes:
    """Codifica una línea JSON (sin '\\n') a bytes listos para enviar por socket."""
    if "\n" in json_line:
        raise ValueError("La línea JSON no debe contener '\\n' interno")
    return (json_line + "\n").encode("utf-8")
