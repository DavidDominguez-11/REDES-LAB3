# Arquitectura v1

## Nodo

```text
stdin / comandos locales
          │
   ┌──────▼──────┐
   │ Estado nodo │
   └───┬────┬────┘
       │    │
┌──────▼─┐ ┌▼─────────┐
│Forward │ │ Routing  │
│TTL,    │ │ vecinos, │
│entrega │ │ LSP,     │
│y relay │ │ rutas    │
└───┬────┘ └────┬─────┘
    │            │
    └─────┬──────┘
          ▼
   cola de salida
   control > usuario
          │
          ▼
 TCP: una conexión por paquete
```

Forwarding y routing son responsabilidades separadas. Los algoritmos no conocen sockets, hilos ni colas.

## Transporte y concurrencia

- Un listener TCP recibe una sola línea JSON por conexión.
- Cada envío abre una conexión, transmite un JSON terminado en salto de línea y la cierra.
- Una cola de entrada entrega paquetes a forwarding.
- Una cola de eventos entrega LSP, expiraciones y cambios de vecinos a routing.
- La cola de salida prioriza `hello`, `hello_ack` y `lsp` sobre `message`.
- Se conserva el orden relativo dentro de cada prioridad.
- Los timeouts y fallos de conexión se registran y no detienen el nodo.

## Estado de routing

Routing crea una tabla completa nueva y reemplaza la referencia atómicamente. Cada entrada contiene destino lógico, costo, siguiente salto lógico, camino y estado alcanzable. Forwarding convierte el siguiente salto en IP y puerto mediante la configuración local.

## Algoritmos

- **Dijkstra:** topología completa y rutas estáticas cargadas desde configuración.
- **Flooding:** solo vecinos directos, TTL, deduplicación y exclusión del vecino de entrada.
- **LSR:** HELLO/ACK, LSP iniciales, de cambio y de refresco; base de estados; enlaces mutuamente anunciados; Dijkstra para calcular rutas.

Un LSP expira por tiempo monotónico local. La caída o recuperación de un vecino origina inmediatamente un nuevo LSP; también existe refresco periódico.

## Identidad y protocolo

`from` y `to` son IPs del originador y destino final. Los IDs lógicos se usan en topología y tablas, y aparecen en `headers` o `payload` cuando el mensaje lo requiere. Para LSP, `to` es `255.255.255.255` como difusión lógica, nunca broadcast real.
