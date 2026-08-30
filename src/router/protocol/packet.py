"""Paquete de protocolo v1 para la red de nodos (CC3067 Lab 3).

Especificación completa en docs/protocolo.md. Resumen:
- Un paquete es un objeto JSON con los campos: version, id, proto, type,
  from, to, ttl, headers, payload.
- Se transmite como una línea NDJSON (JSON compacto + '\\n') sobre TCP.
- `proto` in {"dijkstra", "flooding", "lsr"}
- `type` in {"hello", "echo", "message", "info"}

Los campos `from`/`to` se tratan como strings opacos: en pruebas locales son
IDs lógicos de nodo ("A", "B", ...); el diseño no asume ningún formato
específico para permitir cambiarlos a IP:puerto sin tocar esta clase.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

PROTOCOL_VERSION = 1

VALID_PROTOS = {"dijkstra", "flooding", "lsr"}
VALID_TYPES = {"hello", "echo", "message", "info"}

REQUIRED_FIELDS = ("id", "proto", "type", "from", "to", "ttl", "payload")


class PacketValidationError(ValueError):
    """Se lanza cuando un paquete no cumple con el esquema mínimo del protocolo."""


@dataclass
class Packet:
    proto: str
    type: str
    from_: str
    to: str
    ttl: int
    payload: Any
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: int = PROTOCOL_VERSION
    headers: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "id": self.id,
            "proto": self.proto,
            "type": self.type,
            "from": self.from_,
            "to": self.to,
            "ttl": self.ttl,
            "headers": self.headers,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        """Serializa a una línea JSON compacta, sin '\\n' interno."""
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)

    def with_ttl_decremented(self, new_from: str | None = None) -> "Packet":
        """Devuelve una copia del paquete con ttl - 1 (no muta el original).

        `new_from` permite actualizar `from` al reenviar, representando el
        nodo que retransmite este salto (útil para que el próximo receptor
        sepa a quién no debe reenviar de vuelta). El `id` del paquete nunca
        cambia, ya que es la clave usada para deduplicación end-to-end.
        """
        return Packet(
            proto=self.proto,
            type=self.type,
            from_=self.from_ if new_from is None else new_from,
            to=self.to,
            ttl=self.ttl - 1,
            payload=self.payload,
            id=self.id,
            version=self.version,
            headers=list(self.headers),
        )

    def with_hop_appended(self, node_id: str) -> "Packet":
        """Devuelve una copia con `node_id` anexado a headers[].hops (traza opcional)."""
        new_headers = [dict(h) for h in self.headers]
        hop_header = None
        for h in new_headers:
            if "hops" in h:
                hop_header = h
                break
        if hop_header is None:
            new_headers.append({"hops": [node_id]})
        else:
            hop_header["hops"] = list(hop_header["hops"]) + [node_id]
        return Packet(
            proto=self.proto,
            type=self.type,
            from_=self.from_,
            to=self.to,
            ttl=self.ttl,
            payload=self.payload,
            id=self.id,
            version=self.version,
            headers=new_headers,
        )

    @staticmethod
    def from_dict(data: dict) -> "Packet":
        if not isinstance(data, dict):
            raise PacketValidationError("El paquete debe ser un objeto JSON")

        missing = [f for f in REQUIRED_FIELDS if f not in data]
        if missing:
            raise PacketValidationError(f"Campos faltantes: {missing}")

        if not isinstance(data["proto"], str) or data["proto"] not in VALID_PROTOS:
            raise PacketValidationError(f"proto inválido: {data.get('proto')!r}")
        if not isinstance(data["type"], str) or data["type"] not in VALID_TYPES:
            raise PacketValidationError(f"type inválido: {data.get('type')!r}")
        if not isinstance(data["ttl"], int) or isinstance(data["ttl"], bool):
            raise PacketValidationError("ttl debe ser entero")
        if not isinstance(data["id"], str) or not data["id"]:
            raise PacketValidationError("id debe ser un string no vacío")
        if not isinstance(data["from"], str) or not isinstance(data["to"], str):
            raise PacketValidationError("from/to deben ser strings")

        headers = data.get("headers", [])
        if not isinstance(headers, list):
            raise PacketValidationError("headers debe ser una lista")

        version = data.get("version", PROTOCOL_VERSION)
        if not isinstance(version, int):
            raise PacketValidationError("version debe ser entero")

        return Packet(
            proto=data["proto"],
            type=data["type"],
            from_=data["from"],
            to=data["to"],
            ttl=data["ttl"],
            payload=data["payload"],
            id=data["id"],
            version=version,
            headers=headers,
        )

    @staticmethod
    def from_json(line: str) -> "Packet":
        line = line.strip()
        if not line:
            raise PacketValidationError("Línea vacía, no es un paquete válido")
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PacketValidationError(f"JSON inválido: {exc}") from exc
        return Packet.from_dict(data)
