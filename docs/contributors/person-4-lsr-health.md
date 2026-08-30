# Persona 4 — LSR and Health

## Objetivo

Preparar HELLO/ACK, estados de vecinos, originación y flooding de LSP, expiración, base de estados y convergencia LSR sobre los paquetes ya integrados.

## Dependencias

- Debe esperar merges aprobados de Foundation, Algorithms y Transport/Forwarding.
- Puede diseñar escenarios y revisar contratos antes, pero no implementar contra interfaces inestables.
- Es el último paquete funcional antes de la integración final.

## Alcance futuro

- HELLO inmediato y periódico; `hello_ack` solo ante HELLO válido.
- Estados activo/caído con `hello_interval_seconds = 3` y `missed_hello_limit = 3` inicialmente.
- LSP inicial, por cambio de vecino y refresco cada 10 segundos.
- `origin_node`, `sequence`, `age_seconds = 30`, `neighbors` y UUID4.
- Frescura por `origin_node + sequence`.
- Edad con tiempo monotónico local.
- Flooding LSP a vecinos activos excepto entrada, con `to = "255.255.255.255"` y TCP unicast físico.
- Topología utilizable solo con anuncios mutuamente activos.
- Integración con Dijkstra y reemplazo atómico de tabla.

## Límites

- No modificar el sobre v1 ni inventar solución para reinicio de secuencia.
- No cambiar costos por latencia.
- No implementar un transporte alternativo ni conexiones persistentes.
- No modificar algoritmos puros ni modelos de Foundation sin coordinación.

## Archivos permitidos y prohibidos

Permitidos después de integrar las tres dependencias:

- `router/health.py`
- `router/lsp.py`
- `router/lsr.py`
- `router/routing_state.py`
- documentación y pruebas futuras del paquete en ubicaciones aprobadas.

Prohibidos:

- cambios a `router/algorithms/`, modelos de Foundation o transporte base salvo interfaces coordinadas;
- campos principales adicionales, broadcast real, ACK de usuario o reintentos;
- `src/`, dependencias o configuración ejecutable no aprobada.

## Pruebas futuras

- HELLO/ACK válido, emisor no configurado y TTL 1.
- Tres intervalos sin respuesta producen caída.
- Respuesta posterior produce recuperación.
- Costos no cambian por latencia.
- LSP nuevo, antiguo, repetido, expirado y con TTL agotado.
- Enlaces unilaterales diagnósticos pero no utilizables.
- Convergencia, ruta óptima, caída, recálculo y recuperación.
- Reinicio con sequence bajo aceptado solo después de expiración del LSP anterior.

## Definition of Done

- Health checks y LSP usan las estructuras exactas de `protocol-v1.md`.
- La base de estados y topología distinguen estado diagnóstico de enlace utilizable.
- LSR reutiliza Dijkstra y el transporte sin acoplarlos entre sí.
- Los escenarios de convergencia, caída y recuperación tienen evidencia.
- El pull request declara las tres dependencias integradas y no cambia v1.

## Prompt de IA

Lee `docs/contributors/00-read-first.md`, este paquete, `Laboratorio3.md`, `openspec/config.yaml`, todas las specs principales y todos los documentos actuales de `docs/`. No comiences hasta confirmar merges de Foundation, Algorithms y Transport/Forwarding. Trabaja únicamente en HELLO/ACK, vecinos, LSP, expiración, flooding de LSP y convergencia LSR. Respeta `to = "255.255.255.255"` solo como difusión lógica, TCP unicast físico, `from` como IP originadora y el sobre exacto v1. Usa costos fijos y tiempo monotónico local; no inventes una solución para reinicio de secuencia. Modifica solo archivos permitidos; no crees `src/`, `tests/`, dependencias ni configuración ejecutable fuera de un cambio aprobado. Si una interfaz falta o se propone cambiar protocolo/arquitectura, detente y reporta. Ejecuta verificaciones futuras autorizadas y entrega resultados, logs, archivos y limitaciones.
