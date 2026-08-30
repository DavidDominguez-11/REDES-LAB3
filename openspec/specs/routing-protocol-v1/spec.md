# routing-protocol-v1 Specification

## Purpose

Define el contrato interoperable de mensajes que permite a nodos independientes comunicarse mediante TCP y procesar datos, control y estados de routing de forma verificable.

## Requirements

### Requirement: Sobre JSON compatible con la guía
El sistema SHALL intercambiar objetos JSON por TCP usando exactamente los campos principales `proto`, `type`, `from`, `to`, `ttl`, `headers` y `payload`, sin campos principales adicionales.

#### Scenario: Paquete válido
- **WHEN** un nodo recibe un objeto con los siete campos principales y tipos válidos
- **THEN** procesa el paquete según `proto` y `type`

#### Scenario: Sobre inválido
- **WHEN** falta un campo principal o su tipo es inválido
- **THEN** registra el error y descarta el paquete sin detener el nodo

### Requirement: Direcciones e identidad lógica
`from` y `to` SHALL contener IP origen y destino. Los IDs lógicos SHALL aparecer únicamente en configuración, `headers` o `payload`.

#### Scenario: Reenvío de mensaje
- **WHEN** un `message` atraviesa un nodo intermedio
- **THEN** conserva `from` y `to` originales y cambia solo el destino físico de la conexión interna

### Requirement: Estructuras por tipo
El sistema SHALL usar estructuras estándar para `message`, `lsp`, `hello` y `hello_ack`, incluyendo los metadatos definidos por el protocolo v1.

#### Scenario: LSP válido
- **WHEN** se recibe un LSP v1
- **THEN** `payload` contiene `origin_node`, `sequence`, `age_seconds` y `neighbors`

#### Scenario: Health check válido
- **WHEN** se recibe un `hello` válido de un vecino configurado
- **THEN** se responde con `hello_ack` incluyendo un `message_id` propio y `reply_to`

### Requirement: Framing y validación de conexión
Cada conexión SHALL procesar exactamente una línea JSON no vacía, respetando `max_line_bytes`, inicialmente `65536`.

#### Scenario: Datos adicionales
- **WHEN** una conexión envía más de una línea o datos después de la primera
- **THEN** registra un error de framing, descarta la conexión y no procesa líneas adicionales

#### Scenario: Línea inválida
- **WHEN** la línea no es JSON válida o supera el límite configurado
- **THEN** registra y descarta el contenido y cierra la conexión

### Requirement: TTL y deduplicación
Los paquetes reenviables SHALL incluir `message_id` en `headers`, aplicar deduplicación antes de entregar o reenviar y reducir TTL antes de cada reenvío.

#### Scenario: TTL agotado
- **WHEN** un paquete llega con `ttl <= 0`
- **THEN** se registra y descarta sin entrega ni reenvío

#### Scenario: Último salto
- **WHEN** un `message` llega con `ttl == 1` y `to` coincide con una IP local
- **THEN** se entrega localmente y no se reenvía

#### Scenario: Duplicado
- **WHEN** llega un `message` o `lsp` cuyo `message_id` está en la caché
- **THEN** se registra y descarta antes de procesarlo o reenviarlo

### Requirement: Protocolo compatible
El sistema SHALL aceptar únicamente `proto` v1 soportados por el modo activo y SHALL conservar `proto` durante el reenvío.

#### Scenario: Protocolo desconocido
- **WHEN** se recibe un paquete con `proto` no soportado
- **THEN** se registra y descarta sin reenviarlo
