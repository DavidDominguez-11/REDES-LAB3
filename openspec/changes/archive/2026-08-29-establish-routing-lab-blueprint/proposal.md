## Why

El Laboratorio 3 requiere una simulación distribuida de nodos independientes que implementen Dijkstra, Flooding y Link-State Routing sobre una red local real. El proyecto necesita un contrato técnico común antes de implementar para controlar la interoperabilidad entre grupos, las IP dinámicas de clase, la convergencia de LSR y la evidencia exigida por la evaluación.

Este cambio establece el blueprint funcional y técnico de v1, alineado con `Laboratorio3.md`, para que la implementación posterior pueda dividirse en incrementos pequeños, verificables y compatibles.

## What Changes

- Define el sobre JSON v1 con exactamente `proto`, `type`, `from`, `to`, `ttl`, `headers` y `payload`.
- Define `from` y `to` como IP origen y destino; los IDs lógicos se mantienen en configuración o en `headers`/`payload`.
- Define nodos independientes en modos `dijkstra`, `flooding` y `lsr`.
- Define configuración JSON compartida para nodos, IPs, puertos, vecinos, costos y parámetros operativos.
- Define transporte TCP de una línea JSON por conexión, con hilos, colas y prioridades.
- Define forwarding, routing, TTL, deduplicación, mensajes de usuario best-effort y validación de framing.
- Define HELLO/ACK, detección de vecinos, recuperación y generación, propagación, expiración y refresco de LSP.
- Define topología LSR basada únicamente en enlaces anunciados mutuamente por vecinos activos.
- Define tablas de rutas basadas en IDs lógicos, traducción del siguiente salto a IP/puerto y desempate determinista.
- Define CLI, comandos locales, logs, pruebas unitarias con `unittest`, pruebas multi-proceso y pruebas manuales multi-host.
- Mantiene fuera de v1 UDP, conexiones persistentes, ACK/reintentos de usuario, seguridad avanzada, interfaz web y solución especial para reinicio de secuencias LSP.

## Capabilities

### New Capabilities

- `routing-protocol-v1`: Sobre JSON, tipos de mensajes, headers, payloads, TTL, deduplicación y compatibilidad.
- `node-runtime`: Procesos de nodo, CLI, configuración JSON, transporte TCP, hilos, colas y ciclo de vida.
- `routing-algorithms`: Dijkstra estático, Flooding controlado y Link-State Routing dinámico.
- `neighbor-health`: HELLO/ACK, estados activo/caído, recuperación y actualización de LSP.
- `observability-and-verification`: Logs, comandos operativos, pruebas automatizadas, pruebas de red e interoperabilidad.

### Modified Capabilities

- Ninguna; no existen especificaciones principales previas para estas capacidades.

## Impact

- Introduce la arquitectura y los contratos que guiarán el futuro paquete Python del router.
- Afectará la futura organización de módulos de protocolo, configuración, transporte, forwarding, routing, algoritmos, health checks y logging.
- Requiere documentación operativa, ejemplos de configuración y escenarios reproducibles de prueba.
- No modifica `Laboratorio3.md`, que permanece como fuente de requisitos del profesor.
- No agrega dependencias obligatorias fuera de Python 3.11+ y la biblioteca estándar; `pytest` queda opcional.

### Criterios de éxito y trazabilidad

- El diseño cubre los objetivos y servicios de las secciones 3.1, 3.2 y 3.3 de `Laboratorio3.md`.
- Los tres algoritmos pueden probarse por separado y LSR puede operar sobre varios nodos independientes.
- La interoperabilidad usa el sobre exacto de la guía y un protocolo v1 documentado.
- Cada funcionalidad planificada tiene pruebas y evidencia verificable asociada.
- Los escenarios incluyen convergencia, rutas óptimas, TTL, duplicados, caída, recuperación y ejecución en red local.

### Riesgos y decisiones de interoperabilidad

- Las IPs, firewalls y topologías de clase pueden cambiar; por ello toda dirección es configurable.
- El reinicio de un nodo puede reutilizar una secuencia LSP baja; v1 acepta resolverlo mediante expiración del LSP anterior.
- Otros grupos deberán acordar y respetar las estructuras internas de `headers` y `payload` del protocolo v1.
- `255.255.255.255` representa difusión lógica para LSP, pero nunca implica broadcast real de red.
