"""Identidades en el cable y alias locales de la consola."""
from __future__ import annotations

import ipaddress


def normalize_address(value: str, default_port: int) -> str:
    if value == "*":
        return value
    host, separator, port = value.partition(":")
    try:
        ip = ipaddress.IPv4Address(host)
        number = int(port) if separator else default_port
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Dirección inválida: {value!r}; usa IPv4:puerto") from exc
    if not 1 <= number <= 65535:
        raise ValueError(f"Puerto inválido en {value!r}")
    return f"{ip}:{number}"


class AddressBook:
    def __init__(self, aliases: dict[str, str], default_port: int):
        self.default_port = default_port
        self.aliases = {name: normalize_address(address, default_port) for name, address in aliases.items()}
        self._names = {address: name for name, address in self.aliases.items()}

    def resolve(self, value: str) -> str:
        return self.aliases.get(value) or normalize_address(value, self.default_port)

    def display(self, value: str) -> str:
        return self._names.get(value, value)
