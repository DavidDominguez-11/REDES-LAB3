# Arquitectura

## Módulos

- `protocol/`: envelope compartido, headers, CRC32 canónico y constructores.
- `transport/`: TCP persistente y NDJSON limitado a 65536 bytes por línea.
- `config/`: configuración, costos decimales y resolución de alias a IPv4:puerto.
- `neighbors/`: estado/costo de vecinos y health check HELLO/ECHO.
- `dedup/`: caché temporal de identificadores de mensajes.
- `algorithms/`: Dijkstra, reglas de flooding y LSDB con expiración.
- `routing/`: acceso uniforme al next-hop y tablas de rutas.
- `forwarding/`: entrega, reenvío, LSPs y sincronización de vecinos.
- `node.py`: ensambla los componentes y sus hilos.
- `cli.py`: comandos interactivos.

El contrato en el cable está en [protocolo.md](protocolo.md). La lógica
interna mantiene `Packet.id` como alias de `headers.msg_id`; no se
serializa un campo `id` en el envelope.

## Identidad y configuración

El nodo usa su dirección anunciada como identidad para routing y forwarding.
`node_id` es la etiqueta de consola. `addresses` permite resolver alias
de destinos remotos; los vecinos y el nodo propio se agregan automáticamente.
Este mapa no aporta aristas a LSR ni a flooding: la topología dinámica se
obtiene exclusivamente de los LSPs.

`listen.host` indica dónde escuchar. Si es `0.0.0.0`, se exige
`advertised_host` con la IP alcanzable por los demás nodos.
`network_port` (5000 por defecto) completa direcciones sin puerto.
En modo Dijkstra, los nombres de la topología estática también se resuelven
con el mapa de alias.

## Hilos y transporte

Cada nodo tiene un hilo de aceptación TCP, un lector por conexión entrante,
un lector por conexión saliente, un hilo de health check y, en LSR, un hilo
de mantenimiento. El hilo principal atiende la CLI.

Leer los enlaces salientes permite recibir ECHO, LSPs y mensajes de grupos
que contestan por el mismo socket. Nuestros ECHO se envían por el enlace
configurado al vecino. Ambas formas están admitidas por el protocolo.

El receptor usa `via` como salto anterior. Si falta, usa la identidad de
la conexión (aprendida de HELLO/ECHO o de un `via` anterior); también
puede identificar un vecino si es el único configurado con la IP remota.
No toma el puerto efímero TCP como puerto de escucha. Si no puede identificar
el enlace, acepta el mensaje y el flooding queda acotado por dedup y TTL.

Los envíos de un mismo enlace se serializan mediante un lock. La tabla de
vecinos, la caché de dedup, la LSDB y el estado de sondeo tienen locks propios.
Al detener el nodo se hace shutdown de los sockets para despertar los lectores.

## Mensajes y TTL

`from` conserva el originador en todos los saltos. Al reenviar se actualiza
`via`, se agrega la dirección local a `trace` y se decrementa TTL. Si el
resultado es cero, se descarta antes de enviarlo. Un paquete recibido con
TTL cero tampoco se entrega localmente.

En flooding, los mensajes se deduplican por `msg_id`. Si falta ese header,
se usa un hash estable de `(from, to, type, payload)`, sin incluir TTL.
En Dijkstra/LSR se consulta la tabla y se comprueba que el next-hop esté activo.
Los costos se conservan como números decimales y se rechazan pesos negativos
o no finitos.

## Health check

Cada HELLO lleva un UUID, `t0` del reloj del emisor y
`payload.listen_port`. ECHO devuelve el UUID y `t0` sin modificarlos.
Solo un ECHO que coincide con el sondeo pendiente y llega dentro del timeout
actualiza RTT. La verificación de timeouts se hace en cada ciclo de sondeo;
`hello_max_failures` controla cuántos fallos consecutivos provocan la caída.

Oír tráfico de un vecino directo también confirma actividad. La recuperación
reanuncia el LSP propio y sincroniza la LSDB. El RTT es informativo; los costos
proceden de configuración o de `Node.update_neighbor_cost`, que reanuncia
el LSP cuando cambia un costo.

## LSR: frescura, expiración y convergencia

La LSDB acepta únicamente secuencias mayores por origen. Esa es también la
deduplicación del flooding de LSPs: no se usa `msg_id` para decidir su frescura.
Se recibe tanto la lista canónica de vecinos como las variantes documentadas
(mapa, `links`, `node/cost`, payload JSON textual), pero siempre se emite
`neighbors: [{id, weight}]`.

Cada entrada guarda su hora local de recepción y expira tras 30 segundos
sin un LSP más nuevo. La expiración elimina las aristas salientes de ese origen
y recalcula las rutas. Los duplicados no extienden la vida de una entrada.
El mantenimiento comprueba vencimientos cada 250 ms como máximo y las consultas
de rutas también purgan entradas vencidas.

El nodo origina un LSP al arrancar, cada 10 segundos por defecto y ante cambios
de estado/costo de un vecino. Al primer HELLO y al recuperarse un vecino se
envía un snapshot de la LSDB. Cada snapshot conserva origen y secuencia,
actualiza `age_s` con el tiempo transcurrido y genera un nuevo `msg_id`.

Tras un reinicio, un nodo que recibe su propio LSP desde un snapshot continúa
por encima del contador observado. En los demás casos la expiración permite
aceptar de nuevo una secuencia baja. La heurística opcional de aceptar cualquier
salto hacia atrás mayor de 16 no está activada: un LSP atrasado también puede
tener esa diferencia, por lo que se conserva la regla estricta de frescura.
