# Arquitectura

## Módulos y responsabilidades

```
protocol/     Definición del paquete v1, validación, (de)serialización, constructores por tipo.
transport/    Framing NDJSON + sockets TCP (servidor de escucha, conexiones salientes reconectables).
config/       Modelos de configuración y carga desde JSON (nodo, topología estática).
neighbors/    Tabla de vecinos (estado activo/inactivo, costo) + health check HELLO/ECHO.
dedup/        Caché de deduplicación de paquetes por id, con expiración.
algorithms/   dijkstra.py, flooding.py, lsr.py: lógica pura de cada algoritmo, sin sockets.
routing/      RoutingEngine: fachada que unifica el acceso a next-hop según el modo.
forwarding/   ForwardingEngine: conecta transporte + dedup + routing + flooding.
node.py       Orquestador: junta todos los módulos y arranca los hilos.
cli.py        Interfaz de línea de comandos interactiva.
```

`algorithms/dijkstra.py` y `algorithms/flooding.py` son módulos
independientes e importables por separado — se puede levantar un nodo en
modo `flooding` puro o `dijkstra` puro sin pasar por LSR. `algorithms/lsr.py`
los reutiliza (no reimplementa TTL, dedup, ni el cálculo de rutas): usa
`flooding.py` para distribuir los LSP y `dijkstra.py` para calcular rutas
sobre la topología reconstruida a partir de esos LSP.

## Hilos por nodo

Cada proceso de nodo (`Node`, ver `src/router/node.py`) levanta:

1. **Hilo de aceptación** (`TcpServer._accept_loop`): acepta conexiones TCP
   entrantes de los vecinos.
2. **Un hilo de forwarding por conexión entrante** (`TcpServer._client_loop`):
   lee líneas NDJSON de esa conexión y llama a
   `ForwardingEngine.handle_packet` por cada paquete parseado. Aquí se
   resuelve: entregar localmente, reenviar (flooding o next-hop),
   responder a un `hello`, o aplicar un LSP entrante.
3. **Hilo de health check / mantenimiento de rutas** (`HealthChecker`):
   cada `hello_interval_sec`, envía un `hello` a cada vecino configurado
   (esté activo o no, para poder detectar recuperación) y revisa si algún
   `hello` pendiente superó `hello_timeout_sec` sin `echo` de respuesta.
   Tras `hello_max_failures` fallos consecutivos, marca el vecino inactivo
   y dispara `ForwardingEngine.announce_own_lsp()` (en modo `lsr`), que
   recalcula el LSP propio (excluyendo al vecino caído) y lo difunde. Si
   luego llega un `echo` de un vecino marcado inactivo, se marca activo de
   nuevo y también se reanuncia el LSP propio.
4. **Hilo principal**: corre la CLI interactiva (`cli.py`), que llama a
   métodos de `Node` (`send_message`, `list_neighbors`, `list_routes`).

Todos los hilos comparten, de forma thread-safe (con locks internos),
`NeighborTable`, `DedupCache` y `RoutingEngine`.

Esta separación cumple el requisito de la guía de correr *forwarding* y
*routing* en paralelo/asíncrono: el forwarding es reactivo (un hilo por
conexión, dispara con cada paquete entrante) y el routing/mantenimiento es
proactivo (el hilo de health check, que también es quien dispara los
recálculos y reanuncios de LSP en LSR).

## Flujo de un mensaje de usuario en modo `lsr`

1. La CLI (o `Node.send_message`) llama a
   `ForwardingEngine.send_user_message(destino, texto)`.
2. Se construye un paquete `type: message` con TTL inicial de config.
3. Se consulta `RoutingEngine.next_hop(destino)` (tabla calculada por
   Dijkstra sobre la topología reconstruida vía LSPs).
4. Se envía al vecino correspondiente al next-hop.
5. Cada nodo intermedio repite: si no es el destino, decrementa TTL,
   actualiza `from`, anexa su `node_id` a la traza de saltos, consulta su
   propio next-hop y reenvía.
6. El nodo destino, al ver `to == node_id`, entrega el mensaje (por
   defecto, lo imprime) y no lo reenvía más.

## Flujo de un LSP en modo `lsr`

1. Al iniciar (o al detectar un cambio de vecino), el nodo genera su LSP
   (`origin = node_id`, `seq` incremental propio, `neighbors` = vecinos
   **activos** con su costo configurado).
2. Se aplica localmente a la LSDB propia (para que el nodo se incluya a sí
   mismo en el grafo que usa Dijkstra) y se difunde por *flooding* a los
   vecinos activos.
3. Cada nodo que recibe un `info`: si el `seq` es más nuevo que el último
   conocido de ese `origin`, lo aplica (actualiza su LSDB, recalcula su
   tabla de ruteo con Dijkstra) y lo reenvía a todos sus vecinos activos
   excepto por quien le llegó. Si el `seq` es viejo o repetido, se descarta
   sin reenviar ni recalcular.
