# observability-and-verification Specification

## Purpose

Define la observabilidad, los comandos de diagnóstico y la evidencia necesaria para demostrar comportamiento correcto en pruebas locales y en la red de clase.

## Requirements

### Requirement: Logs por nodo
Cada nodo SHALL escribir un log propio y mostrar eventos relevantes en consola con hora legible, ID local, nivel, evento y resultado.

#### Scenario: Forwarding registrado
- **WHEN** un paquete se recibe, reenvía, entrega o descarta
- **THEN** el log incluye, cuando aplica, `type`, `proto`, `from`, `to`, TTL, `message_id` y siguiente salto

### Requirement: Eventos de routing observables
El sistema SHALL registrar cambios de vecinos, LSP aceptados, rechazados y expirados, recálculos, rutas seleccionadas y errores.

#### Scenario: Cambio de vecino
- **WHEN** un vecino cambia entre activo y caído
- **THEN** el evento y el resultado de la actualización de routing quedan registrados

### Requirement: Pruebas automatizadas
El proyecto SHALL incluir pruebas `unittest` para protocolo, configuración, TTL, deduplicación, Dijkstra, Flooding y lógica LSR pura, además de integración multi-proceso con TCP real en localhost.

#### Scenario: Integración local
- **WHEN** se levantan varios procesos con una topología de prueba
- **THEN** se verifican descubrimiento, envío, rutas, duplicados, TTL y convergencia mediante resultados y logs

### Requirement: Prueba de red e interoperabilidad
El proyecto SHALL documentar escenarios manuales con varias computadoras, incluyendo configuración, comandos, resultado esperado, resultado observado y logs.

#### Scenario: Prueba entre grupos
- **WHEN** nodos LSR v1 de distintos equipos se conectan por Wi-Fi o cable
- **THEN** intercambian mensajes compatibles y se puede verificar la ruta mediante logs

### Requirement: Fallo de observabilidad
Un error al escribir un archivo de log SHALL registrarse o mostrarse si es posible, pero no SHALL detener la ejecución del nodo.

#### Scenario: Archivo no escribible
- **WHEN** el destino del log no puede escribirse
- **THEN** el nodo continúa operando y conserva la observabilidad disponible en consola
