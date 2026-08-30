# Protocolo de la red (v1)

## Framing sobre TCP

Cada nodo mantiene conexiones TCP persistentes con sus vecinos configurados
(reconectables si se caen). Cada paquete se serializa como **una línea JSON
compacta terminada en `\n`** (NDJSON: newline-delimited JSON). Un socket
puede llevar múltiples paquetes en secuencia; el receptor bufferea bytes
hasta encontrar `\n` y ahí parsea (ver `src/router/transport/ndjson.py`).

Un paquete nunca contiene `\n` dentro de su JSON (se serializa sin
pretty-print). Si una línea recibida no es JSON válido o le faltan campos
requeridos, se descarta y se loguea; **no se cae el nodo ni se cierra la
conexión** por un paquete malformado aislado.

## Envoltura base

```json
{
  "version": 1,
  "id": "8f14e45f-ceea-4f1b-9f7e-3c0a6a2d1a4c",
  "proto": "lsr",
  "type": "hello",
  "from": "A",
  "to": "B",
  "ttl": 5,
  "headers": [],
  "payload": {}
}
```

| Campo | Obligatorio | Descripción |
|---|---|---|
| `version` | No (default `1`) | Versión del protocolo. Si falta, se asume `1` para no romper interoperabilidad con grupos que no lo incluyan. |
| `id` | Sí | UUID único del paquete, generado por quien lo origina. **No cambia** al reenviarse; es la clave de deduplicación. |
| `proto` | Sí | `"dijkstra"` \| `"flooding"` \| `"lsr"` |
| `type` | Sí | `"hello"` \| `"echo"` \| `"message"` \| `"info"` |
| `from` | Sí | Ver nota sobre semántica de `from`/`to` abajo. |
| `to` | Sí | Destino final, o `"*"` como convención de broadcast lógico (usada por los LSP). |
| `ttl` | Sí | Entero, decrementado en cada salto. Al llegar a un nodo con `ttl <= 0`, el paquete se descarta. |
| `headers` | No (default `[]`) | Lista extensible. Se usa `{"hops": [...]}` como traza opcional de saltos. |
| `payload` | Sí | Contenido, forma depende de `type` (ver ejemplos abajo). |

### Nota importante sobre `from` / `to`

**Esta implementación usa `from` como el emisor del salto actual** (se
actualiza en cada retransmisión al `node_id` de quien reenvía), no como el
origen absoluto del mensaje. Esto es lo que permite a cada nodo saber a qué
vecino no debe reenviar de vuelta un paquete de flooding, sin necesitar
información adicional fuera de la envoltura. El origen absoluto de un LSP se
preserva aparte, en `payload.origin` (ver más abajo), y el origen de un
mensaje de usuario queda registrado en `headers[].hops[0]` si se usa la
traza de saltos.

`from`/`to` son strings opacos para el resto del sistema — no se asume
ningún formato específico. En las pruebas locales se usan IDs lógicos de
nodo (`"A"`, `"B"`, ...). **El formato final (IP:puerto vs ID lógico) para
la interconexión en clase queda pendiente de coordinación con los demás
grupos** — cambiarlo solo afecta la capa de configuración/mapeo de vecinos,
no la lógica de los algoritmos.

## Tipos de paquete

### `hello` — sondeo de vecino / health check

```json
{"version":1,"id":"a1b2...01","proto":"lsr","type":"hello","from":"A","to":"B","ttl":1,"headers":[],"payload":{"seq":42,"sent_at":1756500000.123}}
```

- `ttl: 1`: nunca se reenvía, solo va a un vecino directo.
- `payload.seq`: contador incremental del emisor, para descartar ecos
  fuera de orden o tardíos.
- `payload.sent_at`: timestamp de envío (epoch float).

### `echo` — respuesta al `hello`

```json
{"version":1,"id":"a1b2...02","proto":"lsr","type":"echo","from":"B","to":"A","ttl":1,"headers":[],"payload":{"seq":42,"sent_at":1756500000.123,"echoed_at":1756500000.126}}
```

- Copia `seq` y `sent_at` del `hello` original, agrega `echoed_at`.
- Quien recibe el `echo` calcula RTT = `now() - sent_at` para monitoreo. El
  RTT **no** se usa para modificar costos de ruta automáticamente, solo
  para observabilidad/diagnóstico.

### `message` — dato de usuario

```json
{"version":1,"id":"b2c3...03","proto":"lsr","type":"message","from":"A","to":"D","ttl":5,"headers":[{"hops":["A"]}],"payload":"Hola, este es un mensaje de prueba"}
```

- `payload` es **texto plano directo** (no un objeto anidado).
- Si `to == node_id` del receptor: se entrega/imprime, no se reenvía más.
- Si no: se decrementa TTL, se actualiza `from` al `node_id` de quien
  reenvía, se anexa el `node_id` a `headers[].hops` (si existe ese header,
  o se crea) y se envía al siguiente salto (según el modo: next-hop de la
  tabla de ruteo en `dijkstra`/`lsr`, o todos los vecinos menos el emisor
  en `flooding`).

### `info` — LSP (Link State Packet), usado por LSR

```json
{"version":1,"id":"c3d4...04","proto":"lsr","type":"info","from":"A","to":"*","ttl":5,"headers":[],"payload":{"origin":"A","seq":7,"neighbors":{"B":4,"C":1}}}
```

- `payload.origin`: nodo que originó este LSP (constante, no cambia al
  reenviarse, a diferencia de `from`).
- `payload.seq`: número de secuencia de `origin`. Un LSP con `seq` menor o
  igual al último visto de ese `origin` **se descarta sin aplicar, sin
  reenviar y sin disparar recálculo** — así se evita procesar/propagar LSPs
  viejos o repetidos indefinidamente.
- `payload.neighbors`: mapa vecino → costo, solo de vecinos **activos** en
  el momento en que `origin` generó el LSP.
- `to: "*"`: convención de broadcast lógico. **Pendiente de confirmar con
  los demás grupos** si aceptan este valor u otra convención.

## Deduplicación

Cada nodo mantiene una caché de `id`s de paquetes ya procesados (usada para
`message` en modo flooding e `info`/LSP). Un `id` repetido se descarta sin
reprocesar ni reenviar. Las entradas expiran tras un intervalo configurable
(`dedup_cache_ttl_sec`) para no crecer sin límite.
Implementación: `src/router/dedup/cache.py`.

## TTL

Obligatorio en todo paquete. Se decrementa en cada nodo que reenvía. Un
paquete que llega con `ttl <= 0` se descarta sin importar el tipo (evita
loops residuales incluso si fallara la deduplicación).

## Reglas por modo

| Modo | Origen de la topología | Reenvío |
|---|---|---|
| `dijkstra` | Config estática (`topology_file`), calculada **una sola vez** al iniciar el nodo | Next-hop de la tabla precalculada |
| `flooding` | No se conoce topología; solo vecinos directos de la config | A todos los vecinos activos excepto quien lo envió, con TTL + dedup |
| `lsr` | Reconstruida dinámicamente a partir de los LSP recibidos (vía flooding) | LSPs se distribuyen por flooding; mensajes de usuario van por next-hop de Dijkstra sobre la topología reconstruida |

## Compatibilidad

Cualquier cambio a este documento que afecte la interoperabilidad con otros
grupos (formato de `from`/`to`, convención `to: "*"`, campos nuevos en
`headers`) debe coordinarse antes de la prueba conjunta y documentarse como
v1.1, v2, etc., sin romper compatibilidad hacia atrás de forma silenciosa.
