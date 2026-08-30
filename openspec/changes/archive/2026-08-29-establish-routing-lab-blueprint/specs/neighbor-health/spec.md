## Purpose

Define el descubrimiento, monitoreo, caída y recuperación de vecinos directos sin alterar los costos configurados.

## ADDED Requirements

### Requirement: HELLO periódico
Cada vecino configurado SHALL recibir `hello` inmediato después de abrir el listener y periódicamente según `hello_interval_seconds`.

#### Scenario: HELLO válido
- **WHEN** un vecino directo recibe un `hello` compatible con `ttl == 1`
- **THEN** responde con `hello_ack` sin reenviar el paquete

### Requirement: Seguimiento de actividad
El nodo SHALL registrar la última respuesta válida de cada vecino y marcarlo caído después de `missed_hello_limit` intervalos sin respuesta.

#### Scenario: Vecino caído
- **WHEN** se supera el límite de respuestas HELLO perdidas
- **THEN** el vecino cambia a caído, se registra el evento y se origina un LSP actualizado en modo LSR

### Requirement: Recuperación
El nodo SHALL marcar activo a un vecino caído al recibir un `hello_ack` válido y SHALL actualizar LSR inmediatamente.

#### Scenario: Vecino recuperado
- **WHEN** llega un `hello_ack` válido después de una caída
- **THEN** el vecino cambia a activo, se registra y se origina un nuevo LSP en modo LSR

### Requirement: Costos estables
HELLO SHALL verificar disponibilidad, pero no SHALL modificar el costo fijo configurado.

#### Scenario: Latencia variable
- **WHEN** cambia el tiempo de respuesta de un vecino
- **THEN** su costo de routing permanece igual al configurado
