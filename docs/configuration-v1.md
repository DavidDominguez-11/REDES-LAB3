# Configuración JSON v1

## Propósito

Todos los nodos de una topología usan una misma versión del archivo JSON. Cada proceso selecciona su sección mediante `--node`. Las IPs y puertos se actualizan coordinadamente antes de una prueba de clase.

## Esquema conceptual

```json
{
  "nodes": {
    "A": {"ip": "192.168.1.35", "port": 5001},
    "B": {"ip": "192.168.1.36", "port": 5002},
    "D": {"ip": "192.168.1.44", "port": 5004}
  },
  "neighbors": {
    "A": [{"node_id": "B", "cost": 2}],
    "B": [{"node_id": "A", "cost": 2}, {"node_id": "D", "cost": 1}],
    "D": [{"node_id": "B", "cost": 1}]
  },
  "defaults": {
    "hello_interval_seconds": 3,
    "missed_hello_limit": 3,
    "lsp_max_age_seconds": 30,
    "lsp_refresh_seconds": 10,
    "dedup_cache_ttl_seconds": 60,
    "dedup_cache_max_entries": 10000,
    "max_line_bytes": 65536,
    "log_level": "INFO"
  }
}
```

La estructura exacta podrá refinarse en un cambio OpenSpec posterior, pero no debe perder la separación entre ID lógico, IP, puerto, vecino y costo.

## Validaciones

La configuración debe rechazar IDs duplicados o vacíos, IP/puerto faltantes o inválidos, vecinos inexistentes, costos negativos o no numéricos, parámetros temporales no positivos y nodos solicitados por CLI que no estén definidos.

Los costos permanecen fijos y no se reemplazan por latencia medida. La simetría de vecinos se valida o se marca explícitamente para que un enlace unilateral sea diagnóstico y no utilizable por LSR.

## Adaptación para clase

1. Mantener los mismos IDs lógicos y la misma topología.
2. Actualizar IPs y puertos coordinadamente.
3. Distribuir la misma versión del archivo.
4. Confirmar conectividad y puertos permitidos.
5. Registrar la configuración utilizada junto con los logs.

No se codifican IPs, puertos, vecinos, costos ni topologías en el programa.
