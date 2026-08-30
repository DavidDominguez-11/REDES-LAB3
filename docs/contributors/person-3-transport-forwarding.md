# Persona 3 — Transport and Forwarding

## Objetivo

Preparar el listener TCP por paquete, framing JSON, colas, TTL, deduplicación, forwarding y logs base, consumiendo las interfaces aprobadas por Foundation.

## Dependencias

- Debe esperar el merge de Foundation.
- Puede leer y preparar el paquete mientras Foundation se revisa, pero no asumir interfaces no aprobadas.
- No depende de Algorithms para el transporte básico; usa la abstracción de siguiente salto definida por Foundation.
- LSR/health depende de este paquete integrado.

## Alcance futuro

- Listener TCP que procesa una línea JSON no vacía por conexión.
- Envío TCP no persistente: una conexión, una línea, cierre.
- Timeout configurable y errores no fatales.
- Cola entrante, cola de routing y cola saliente priorizada.
- Validación del sobre y framing.
- Entrega local por IP `to`, reenvío usando siguiente salto interno y conservación de `from`/`to`.
- TTL, UUID4, deduplicación y logs base.

## Límites

- No implementar Dijkstra, Flooding algorítmico, LSP, HELLO/ACK ni convergencia LSR.
- No usar conexiones persistentes, UDP, broadcast real, ACK o reintentos de usuario.
- No cambiar el sobre principal ni agregar `next_hop`.

## Archivos permitidos y prohibidos

Permitidos después del merge de Foundation:

- `router/transport.py`
- `router/framing.py`
- `router/forwarding.py`
- `router/queues.py`
- `router/logging_setup.py`
- pruebas futuras del paquete en la ubicación acordada por un cambio de implementación.

Prohibidos:

- modelos o validadores de Foundation sin coordinación;
- `router/algorithms/`, LSR, health checks o configuración global;
- cambios a `Laboratorio3.md`, specs, protocolo v1 o archivos de otros paquetes;
- `src/`, dependencias o configuración ejecutable no aprobada.

## Pruebas futuras

- Una línea JSON válida y conexión cerrada.
- Línea vacía, JSON inválido, datos adicionales y tamaño mayor a 65536 bytes.
- Timeout y conexión rechazada sin detener el nodo.
- Prioridad de `hello`, `hello_ack` y `lsp` sobre `message`.
- TTL 0, TTL 1 local y TTL mayor a 1.
- Duplicados, expiración de caché y límite de 10000 entradas.
- Conservación de IP origen/destino y entrega local.
- Registro de eventos y continuidad cuando el archivo de log no puede escribirse.

## Definition of Done

- Las interfaces de Foundation se consumen sin duplicarlas.
- El transporte cumple framing y ciclo de conexión v1.
- Forwarding no conoce detalles internos de los algoritmos.
- TTL, deduplicación, colas y logs están documentados y verificados.
- El pull request incluye resultados y no invade LSR/health.

## Prompt de IA

Lee `docs/contributors/00-read-first.md`, este paquete, `Laboratorio3.md`, `openspec/config.yaml`, todas las specs y todos los documentos actuales de `docs/`. Verifica primero que Foundation esté integrado y usa solo sus interfaces aprobadas. Trabaja únicamente en transporte TCP por paquete, framing de una línea JSON, colas, TTL, deduplicación, forwarding y logs base. Conserva exactamente `proto`, `type`, `from`, `to`, `ttl`, `headers` y `payload`; `from`/`to` son IPs y nunca agregues `next_hop`. No implementes Dijkstra, Flooding, LSR, HELLO/ACK ni health checks. Modifica solo archivos permitidos; no crees `src/`, `tests/`, dependencias ni configuración ejecutable fuera de un cambio aprobado. Si Foundation no alcanza o una IA propone cambiar arquitectura/protocolo, detente y reporta. Ejecuta las verificaciones del paquete cuando estén autorizadas y reporta archivos, resultados y limitaciones.
