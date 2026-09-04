"""Modelo, validación y serialización del protocolo de red v1.

El formato de cable usa un envelope fijo y un identificador lógico en los
headers. ``id`` se conserva como alias de compatibilidad para el código del
laboratorio anterior, pero nunca se serializa como campo independiente.
"""
from __future__ import annotations

import json
import logging
import uuid
import zlib
from dataclasses import dataclass, field
from typing import Any

PROTOCOL_VERSION = 1
MAX_LINE_BYTES = 65536
VALID_PROTOS = {"dijkstra", "flooding", "lsr"}
VALID_TYPES = {"hello", "echo", "info", "message"}
REQUIRED_FIELDS = ("version", "proto", "type", "from", "to", "ttl", "headers", "payload")

logger = logging.getLogger(__name__)


class PacketValidationError(ValueError):
    """El paquete no cumple el esquema mínimo del protocolo."""


def canonical_payload(payload: Any) -> str:
    """Devuelve la serialización usada por el checksum CRC32."""
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_checksum(payload: Any) -> str:
    """CRC32 del payload canónico, como ocho dígitos hexadecimales."""
    value = zlib.crc32(canonical_payload(payload).encode("utf-8")) & 0xFFFFFFFF
    return f"{value:08x}"


def _copy_headers(headers: list[dict]) -> list[dict]:
    return [dict(header) for header in headers]


def _header_value(headers: list[dict], name: str, default: Any = None) -> Any:
    for header in headers:
        if name in header:
            return header[name]
    return default


def _legacy_node_id(value: str) -> bool:
    return ":" not in value and "." not in value


@dataclass
class Packet:
    proto: str
    type: str
    from_: str
    to: str
    ttl: int
    payload: Any
    id: str | None = None  # alias legacy de headers[{"msg_id": ...}]
    version: int = PROTOCOL_VERSION
    headers: list[dict] = field(default_factory=list)
    allow_missing_msg_id: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.headers = _copy_headers(self.headers)

        msg_id = _header_value(self.headers, "msg_id")
        if msg_id is None:
            if self.id is not None:
                msg_id = self.id
            elif self.allow_missing_msg_id:
                msg_id = None
            else:
                msg_id = str(uuid.uuid4())
            if msg_id is not None:
                if not _legacy_node_id(self.from_):
                    self.headers.insert(0, {"msg_id": msg_id})
                else:
                    self.headers.append({"msg_id": msg_id})
        self.id = str(msg_id) if msg_id is not None else None

        if _header_value(self.headers, "checksum") is None:
            self.headers.append({"checksum": payload_checksum(self.payload)})

    @property
    def msg_id(self) -> str:
        """UUID lógico del paquete (alias legible del antiguo ``id``)."""
        return self.id or ""

    def header(self, name: str, default: Any = None) -> Any:
        return _header_value(self.headers, name, default)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "proto": self.proto,
            "type": self.type,
            "from": self.from_,
            "to": self.to,
            "ttl": self.ttl,
            "headers": _copy_headers(self.headers),
            "payload": self.payload,
        }

    def to_json(self) -> str:
        """Serializa un objeto JSON compacto, sin salto de línea interno."""
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)

    def with_ttl_decremented(self, new_from: str | None = None) -> "Packet":
        """Devuelve una copia con TTL decrementado.

        ``new_from`` se ignora deliberadamente para el protocolo nuevo: el
        campo ``from`` es el originador absoluto. Se acepta el argumento para
        que las capas antiguas puedan seguir llamando al método.
        """
        return Packet(
            proto=self.proto,
            type=self.type,
            from_=self.from_ if new_from is None or not _legacy_node_id(self.from_) or not _legacy_node_id(new_from or "") else new_from,
            to=self.to,
            ttl=self.ttl - 1,
            payload=self.payload,
            id=self.id,
            version=self.version,
            headers=_copy_headers(self.headers),
            allow_missing_msg_id=self.allow_missing_msg_id,
        )

    def with_forward_metadata(self, node_address: str, trace_message: bool = False) -> "Packet":
        """Actualiza ``via`` y, para mensajes, agrega el nodo a ``trace``."""
        new_headers = _copy_headers(self.headers)
        via_header = next((h for h in new_headers if "via" in h), None)
        if via_header is None:
            new_headers.append({"via": node_address})
        else:
            via_header["via"] = node_address

        if trace_message:
            trace_header = next((h for h in new_headers if "trace" in h), None)
            if trace_header is None:
                new_headers.append({"trace": [self.from_, node_address]})
            else:
                trace = trace_header.get("trace")
                if not isinstance(trace, list):
                    trace = []
                trace_header["trace"] = list(trace) + [node_address]

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
            allow_missing_msg_id=self.allow_missing_msg_id,
        )

    def with_destination(self, destination: str) -> "Packet":
        """Devuelve una copia con ``to`` normalizado para el siguiente salto."""
        return Packet(
            proto=self.proto,
            type=self.type,
            from_=self.from_,
            to=destination,
            ttl=self.ttl,
            payload=self.payload,
            id=self.id,
            version=self.version,
            headers=_copy_headers(self.headers),
            allow_missing_msg_id=self.allow_missing_msg_id,
        )

    def with_hop_appended(self, node_id: str) -> "Packet":
        """Compatibilidad con el header ``hops`` del protocolo anterior."""
        new_headers = _copy_headers(self.headers)
        hop_header = next((h for h in new_headers if "hops" in h), None)
        if hop_header is None:
            new_headers.append({"hops": [node_id]})
        else:
            hops = hop_header.get("hops")
            hop_header["hops"] = (list(hops) if isinstance(hops, list) else []) + [node_id]
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
            allow_missing_msg_id=self.allow_missing_msg_id,
        )

    @staticmethod
    def from_dict(data: dict) -> "Packet":
        if not isinstance(data, dict):
            raise PacketValidationError("El paquete debe ser un objeto JSON")

        # La versión ausente se procesa como v1. Una versión distinta también
        # se procesa, pero se registra para no romper interoperabilidad.
        if "version" not in data:
            version = PROTOCOL_VERSION
        else:
            version = data["version"]
            if not isinstance(version, int) or isinstance(version, bool):
                raise PacketValidationError("version debe ser entero")
            if version != PROTOCOL_VERSION:
                logger.warning("Versión de protocolo no reconocida: %r", version)

        missing = [f for f in REQUIRED_FIELDS if f != "version" and f not in data]
        if missing:
            raise PacketValidationError(f"Campos faltantes: {missing}")

        if not isinstance(data["proto"], str) or data["proto"] not in VALID_PROTOS:
            raise PacketValidationError(f"proto inválido: {data.get('proto')!r}")
        if not isinstance(data["type"], str) or data["type"] not in VALID_TYPES:
            raise PacketValidationError(f"type inválido: {data.get('type')!r}")
        if not isinstance(data["ttl"], int) or isinstance(data["ttl"], bool) or data["ttl"] < 0:
            raise PacketValidationError("ttl debe ser entero no negativo")
        if not isinstance(data["from"], str) or not isinstance(data["to"], str):
            raise PacketValidationError("from/to deben ser strings")

        headers = data["headers"]
        if not isinstance(headers, list):
            raise PacketValidationError("headers debe ser una lista")
        for header in headers:
            if not isinstance(header, dict) or len(header) != 1:
                raise PacketValidationError("cada header debe ser un objeto de una sola clave")

        payload = data["payload"]
        if data["type"] == "message" and not isinstance(payload, str):
            raise PacketValidationError("payload debe ser string para message")
        if data["type"] != "message" and not isinstance(payload, dict):
            # Algunos nodos serializan el payload de un LSP como texto JSON;
            # se acepta solo para `info` y se normaliza al procesarlo.
            if data["type"] != "info" or not isinstance(payload, str):
                raise PacketValidationError("payload debe ser objeto para hello, echo e info")

        # Compatibilidad de lectura con el envelope anterior: si trae `id`,
        # se convierte a msg_id y se completa checksum. Los paquetes nuevos
        # deben traer ambos headers obligatorios.
        legacy_id = data.get("id")
        msg_id = _header_value(headers, "msg_id")
        checksum = _header_value(headers, "checksum")
        allow_missing_msg_id = msg_id is None and not isinstance(legacy_id, str) and data["proto"] == "flooding" and data["type"] == "message"
        if msg_id is None and not isinstance(legacy_id, str) and not allow_missing_msg_id:
            raise PacketValidationError("falta header msg_id")
        if checksum is None and not isinstance(legacy_id, str):
            raise PacketValidationError("falta header checksum")
        if msg_id is not None and (not isinstance(msg_id, str) or not msg_id):
            raise PacketValidationError("msg_id debe ser un string no vacío")
        if checksum is not None and (not isinstance(checksum, str) or not checksum):
            raise PacketValidationError("checksum debe ser un string no vacío")

        if msg_id is None and isinstance(legacy_id, str):
            headers = _copy_headers(headers)
            headers.insert(0, {"msg_id": legacy_id})
        if checksum is None:
            headers = _copy_headers(headers)
            headers.append({"checksum": payload_checksum(payload)})

        packet = Packet(
            proto=data["proto"],
            type=data["type"],
            from_=data["from"],
            to=data["to"],
            ttl=data["ttl"],
            payload=payload,
            id=msg_id or legacy_id,
            version=version,
            headers=headers,
            allow_missing_msg_id=allow_missing_msg_id,
        )

        received_checksum = packet.header("checksum")
        expected_checksum = payload_checksum(packet.payload)
        if received_checksum != expected_checksum:
            logger.warning(
                "Checksum CRC32 no coincide para %s: recibido=%s esperado=%s; se procesa",
                packet.msg_id,
                received_checksum,
                expected_checksum,
            )
        return packet

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
