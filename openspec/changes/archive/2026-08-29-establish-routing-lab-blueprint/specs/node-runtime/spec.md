## Purpose

Define el comportamiento operativo de un nodo configurable, concurrente y ejecutable de forma independiente en una red local con transporte TCP.

## ADDED Requirements

### Requirement: Configuración externa validada
El nodo SHALL cargar un único archivo JSON compartido por topología y validar IDs, IPs, puertos, vecinos, costos y parámetros antes de abrir el listener.

#### Scenario: Configuración válida
- **WHEN** el archivo contiene el nodo seleccionado y una topología coherente
- **THEN** el nodo abre su listener y comienza su operación

#### Scenario: Configuración inválida
- **WHEN** existen IDs duplicados, vecinos inexistentes, costos inválidos o campos de red faltantes
- **THEN** el nodo informa el error y no abre el listener

### Requirement: Modos independientes
El nodo SHALL ejecutarse en modo `dijkstra`, `flooding` o `lsr` mediante CLI, seleccionando su sección con `--node`.

#### Scenario: Inicio por CLI
- **WHEN** se ejecuta `python -m router --config config.json --node A --mode lsr`
- **THEN** se inicia el nodo A en modo LSR después de validar la configuración

### Requirement: Transporte TCP por paquete
Cada envío a un vecino SHALL abrir una conexión TCP, transmitir exactamente un JSON terminado en salto de línea, esperar el fin del envío y cerrar la conexión.

#### Scenario: Envío exitoso
- **WHEN** una cola saliente entrega un paquete a un vecino alcanzable
- **THEN** el transporte abre una conexión, transmite una línea y la cierra

#### Scenario: Falla de transporte
- **WHEN** ocurre timeout, rechazo o error de conexión
- **THEN** se registra el fallo y el proceso del nodo continúa ejecutándose

### Requirement: Concurrencia y colas
El nodo SHALL mantener colas de entrada, eventos de routing y salida priorizada, sin permitir que una operación lenta bloquee forwarding o routing.

#### Scenario: Prioridad de control
- **WHEN** hay envíos de control y de usuario pendientes
- **THEN** se procesan primero `hello`, `hello_ack` y `lsp`, conservando orden dentro de cada prioridad

### Requirement: Comandos locales
El nodo SHALL aceptar `send`, `routes`, `neighbors`, `status` y `quit` desde stdin sin crear un puerto de control adicional.

#### Scenario: Originar mensaje
- **WHEN** se ejecuta `send <ip_destino> <id_destino> <mensaje>`
- **THEN** se construye un `message`, se entrega al forwarding local y se informa el resultado

#### Scenario: Apagado
- **WHEN** se ejecuta `quit`
- **THEN** se cierran ordenadamente listener, hilos y colas sin anunciar explícitamente la caída
