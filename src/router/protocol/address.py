"""Utilidades para las direcciones del protocolo (host:puerto)."""
from __future__ import annotations


def normalize_address(address: str, default_port: int) -> str:
    """Completa el puerto omitido sin alterar una dirección ya completa."""
    if not isinstance(address, str) or not address:
        return address
    if address == "*":
        return address
    if address.startswith("[") and "]" in address:
        if address[address.index("]") + 1 :].startswith(":"):
            return address
        return f"{address}:{default_port}"
    if address.count(":") == 1:
        host, port = address.rsplit(":", 1)
        if host and port.isdigit():
            return address
    if address.count(":") > 1:  # IPv6 sin corchetes
        return f"[{address}]:{default_port}"
    return f"{address}:{default_port}"


def endpoint(host: str, port: int) -> str:
    """Construye una dirección de cable a partir de host y puerto."""
    return normalize_address(host, int(port))
