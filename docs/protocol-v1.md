# Contrato de protocolo JSON v1

## Transporte y sobre

El protocolo v1 usa TCP y exactamente un objeto JSON por línea. Cada conexión procesa una sola línea no vacía, con un tamaño máximo inicial de `65536` bytes.

El sobre obligatorio es exactamente:

```json
{
  "proto": "lsr",
  "type": "message",
  "from": "192.168.1.35",
  "to": "192.168.1.44",
  "ttl": 5,
  "headers": [
    {"message_id": "550e8400-e29b-41d4-a716-446655440000", "from_node": "A", "to_node": "D"}
  ],
  "payload": "Hola"
}
```

No se agregan campos al nivel principal. `from` y `to` son IP origen y destino final. El siguiente salto lógico se traduce internamente a IP y puerto y nunca reemplaza esos campos.

## Tipos y contenidos

### `message`

```json
{
  "proto": "lsr",
  "type": "message",
  "from": "192.168.1.35",
  "to": "192.168.1.44",
  "ttl": 5,
  "headers": [{"message_id": "uuid4", "from_node": "A", "to_node": "D"}],
  "payload": "Hola"
}
```

### `lsp`

```json
{
  "proto": "lsr",
  "type": "lsp",
  "from": "192.168.1.35",
  "to": "255.255.255.255",
  "ttl": 8,
  "headers": [{"message_id": "uuid4"}],
  "payload": {
    "origin_node": "A",
    "sequence": 4,
    "age_seconds": 30,
    "neighbors": [{"node_id": "B", "cost": 2}]
  }
}
```

`255.255.255.255` es difusión lógica documentada. Cada copia se envía por TCP unicast a un vecino directo activo; no se usa broadcast real.

### `hello`

```json
{
  "proto": "lsr",
  "type": "hello",
  "from": "192.168.1.35",
  "to": "192.168.1.36",
  "ttl": 1,
  "headers": [{"message_id": "uuid4", "from_node": "A"}],
  "payload": {}
}
```

### `hello_ack`

```json
{
  "proto": "lsr",
  "type": "hello_ack",
  "from": "192.168.1.36",
  "to": "192.168.1.35",
  "ttl": 1,
  "headers": [{"message_id": "uuid4", "reply_to": "uuid4", "from_node": "B"}],
  "payload": {}
}
```

## TTL, deduplicación y LSP

- `message` y `lsp` incluyen `message_id` y participan en deduplicación.
- La deduplicación ocurre antes de entregar o reenviar.
- Un paquete se reenvía solo si `ttl > 1`; antes se reduce en uno.
- Con `ttl == 1`, un `message` puede entregarse localmente, pero nunca se reenvía.
- Con `ttl <= 0`, se descarta y registra.
- `hello` y `hello_ack` usan `ttl = 1`, no se reenvían y no entran en la caché persistente.
- La caché guarda tiempo monotónico local, expira inicialmente a los 60 segundos y tiene máximo inicial de 10000 entradas.
- La frescura LSP usa `origin_node + sequence`; la edad se controla localmente sin depender del reloj remoto.

## Compatibilidad

`proto` puede ser `dijkstra`, `flooding` o `lsr`. No cambia durante el reenvío. Un nodo procesa únicamente protocolos compatibles con su modo; valores desconocidos o incompatibles se registran y descartan.
