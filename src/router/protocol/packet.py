"""Envelope compartido: origen estable, headers y checksum del payload."""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
import zlib
from dataclasses import dataclass, field, replace
from typing import Any

logger = logging.getLogger(__name__)
PROTOCOL_VERSION = 1
VALID_PROTOS = {"dijkstra", "flooding", "lsr"}
VALID_TYPES = {"hello", "echo", "message", "info"}
REQUIRED_FIELDS = ("proto", "type", "from", "to", "ttl", "headers", "payload")


class PacketValidationError(ValueError):
    """El paquete no cumple el envelope compartido."""


def canonical_payload(payload: Any) -> bytes:
    text = payload if isinstance(payload, str) else json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return text.encode("utf-8")


def payload_checksum(payload: Any) -> str:
    return f"{zlib.crc32(canonical_payload(payload)) & 0xffffffff:08x}"


@dataclass
class Packet:
    proto: str
    type: str
    from_: str
    to: str
    ttl: int
    payload: Any
    # Alias interno de headers.msg_id; nunca se emite un id en el envelope.
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: Any = PROTOCOL_VERSION
    headers: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.headers = [dict(h) for h in self.headers]
        msg_id = self.header("msg_id")
        if isinstance(msg_id, str) and msg_id:
            self.id = msg_id
        else:
            self._set_header("msg_id", self.id)
        if self.header("checksum") is None:
            self._set_header("checksum", payload_checksum(self.payload))

    def header(self, key: str, default=None):
        return next((h[key] for h in self.headers if key in h), default)

    def _set_header(self, key: str, value: Any) -> None:
        self.headers = [h for h in self.headers if key not in h] + [{key: value}]

    def with_header(self, key: str, value: Any) -> "Packet":
        packet = replace(self)
        packet._set_header(key, value)
        return packet

    def to_dict(self) -> dict:
        return {"version": self.version, "proto": self.proto, "type": self.type,
                "from": self.from_, "to": self.to, "ttl": self.ttl,
                "headers": self.headers, "payload": self.payload}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False, allow_nan=False)

    def with_ttl_decremented(self, new_from: str | None = None) -> "Packet":
        """Conserva el originador; new_from identifica el salto en via."""
        packet = replace(self, ttl=self.ttl - 1)
        return packet.with_header("via", new_from) if new_from else packet

    def with_hop_appended(self, node_id: str) -> "Packet":
        trace = self.header("trace", [])
        if not isinstance(trace, list):
            trace = []
        return self.with_header("trace", list(trace) + [node_id])

    def forwarded_by(self, node_id: str) -> "Packet":
        packet = self.with_ttl_decremented(new_from=node_id)
        return packet.with_hop_appended(node_id) if self.type == "message" else packet

    @staticmethod
    def from_dict(data: dict) -> "Packet":
        if not isinstance(data, dict):
            raise PacketValidationError("El paquete debe ser un objeto JSON")
        missing = [f for f in REQUIRED_FIELDS if f not in data]
        if missing:
            raise PacketValidationError(f"Campos faltantes: {missing}")
        if not isinstance(data["proto"], str) or data["proto"] not in VALID_PROTOS:
            raise PacketValidationError("proto inválido")
        if not isinstance(data["type"], str) or data["type"] not in VALID_TYPES:
            raise PacketValidationError("type inválido")
        if isinstance(data["ttl"], bool) or not isinstance(data["ttl"], int):
            raise PacketValidationError("ttl debe ser entero")
        if not all(isinstance(data[k], str) and data[k] for k in ("from", "to")):
            raise PacketValidationError("from/to deben ser strings no vacíos")
        headers = data["headers"]
        if not isinstance(headers, list) or any(not isinstance(h, dict) or len(h) != 1 for h in headers):
            raise PacketValidationError("headers debe ser una lista de objetos de una clave")
        keys = [next(iter(h)) for h in headers]
        if len(keys) != len(set(keys)):
            raise PacketValidationError("headers repetidos")
        payload = data["payload"]
        if data["type"] == "message" and not isinstance(payload, str):
            raise PacketValidationError("message.payload debe ser texto")
        if data["type"] in ("hello", "echo") and not isinstance(payload, dict):
            raise PacketValidationError("hello/echo.payload debe ser objeto")
        if data["type"] == "info" and not isinstance(payload, (dict, str)):
            raise PacketValidationError("info.payload debe ser objeto o texto JSON")
        try:
            checksum = payload_checksum(payload)
        except (TypeError, ValueError, UnicodeError) as exc:
            raise PacketValidationError(f"payload inválido: {exc}") from exc
        header_map = {k: v for h in headers for k, v in h.items()}
        if not isinstance(header_map.get("checksum"), str):
            raise PacketValidationError("Falta el header checksum")
        if header_map["checksum"] != checksum:
            logger.warning("Checksum discrepante de %s: recibido=%s calculado=%s",
                           data["from"], header_map["checksum"], checksum)
        msg_id = header_map.get("msg_id")
        if not isinstance(msg_id, str) or not msg_id:
            if data["type"] != "message":
                raise PacketValidationError("Falta el header msg_id")
            # Fallback estable, sin TTL ni headers que cambien en cada salto.
            identity = [data["from"], data["to"], data["type"], payload]
            msg_id = hashlib.sha256(canonical_payload(identity)).hexdigest()
            logger.warning("Mensaje sin msg_id; se usa hash de contenido")
        version = data.get("version", PROTOCOL_VERSION)
        if "version" not in data or type(version) is not int or version != PROTOCOL_VERSION:
            logger.warning("Versión ausente o distinta de 1: %r; se procesa", data.get("version"))
        return Packet(proto=data["proto"], type=data["type"], from_=data["from"], to=data["to"],
                      ttl=data["ttl"], payload=payload, id=msg_id, version=version, headers=headers)

    @staticmethod
    def from_json(line: str) -> "Packet":
        try:
            return Packet.from_dict(json.loads(line))
        except (json.JSONDecodeError, RecursionError) as exc:
            raise PacketValidationError(f"JSON inválido: {exc}") from exc
