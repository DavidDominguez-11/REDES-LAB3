# Reporte Final - Laboratorio 3: Enrutamiento

**Curso:** CC3067 - Redes  
**Laboratorio:** Laboratorio 3  
**Tema:** Dijkstra, Flooding y Link State Routing  
**Repositorio:** `git@github.com:DavidDominguez-11/REDES-LAB3.git`  
**Integrantes:** David Dominguez, Javier Valladares, Ian Cumes, Nery Molina  
**Fecha:** 2026-09-04

## 1. Resumen

Este proyecto implementa un sistema de enrutamiento distribuido en Python
basado en sockets TCP y mensajes JSON por linea (NDJSON). El nodo puede
operar en tres modos: `dijkstra`, `flooding` y `lsr`. La implementacion
cumple con el protocolo compartido definido por el laboratorio y permite
interoperar con otras implementaciones siempre que respeten el mismo
formato de mensajes.

El diseno separa claramente el transporte, el formato de paquete, la
gestion de vecinos, la deduplicacion, el calculo de rutas y la logica de
forwarding. En `lsr`, los nodos difunden LSPs, construyen una LSDB local y
recalculan rutas con Dijkstra. En `flooding`, el reenvio se hace por todos
los vecinos activos excepto el emisor previo, con control por TTL y
deduplicacion. En `dijkstra`, la topologia se carga desde archivo y la
tabla de rutas se calcula una sola vez al iniciar.

## 2. Introduccion

La guia del laboratorio plantea la necesidad de implementar algoritmos de
enrutamiento que funcionen sobre nodos distribuidos, con comunicacion entre
procesos independientes y con capacidad de adaptarse a cambios de enlace,
caidas de vecinos y recuperacion de nodos.

Este proyecto responde a ese objetivo mediante una arquitectura modular y
orientada a interoperabilidad. La red se construye a partir de archivos de
configuracion JSON, lo que permite cambiar IPs, puertos, costos y topologia
sin modificar el codigo fuente. Adicionalmente, el mismo binario soporta los
tres modos exigidos por el laboratorio, lo que facilita pruebas comparativas
y demostraciones.

## 3. Objetivos

### 3.1 Objetivo general

Implementar un nodo de red capaz de operar con Dijkstra, Flooding y Link
State Routing, respetando el protocolo comun del laboratorio y soportando
convergencia, entrega de mensajes y adaptacion a cambios de topologia.

### 3.2 Objetivos especificos

- Definir un envelope comun para mensajes de control y datos.
- Implementar transporte TCP con framing NDJSON.
- Modelar vecinos, estados de enlace y sondeo de salud con HELLO/ECHO.
- Implementar deduplicacion temporal para evitar loops en flooding.
- Implementar Dijkstra sobre topologia estatica y sobre topologia
  reconstruida desde LSPs.
- Implementar LSR con difusion de estado de enlace, expiracion y
  recalculo dinamico de rutas.
- Proveer una CLI simple para operar cada nodo de forma interactiva.

## 4. Alcance funcional

El sistema implementado cubre los siguientes casos:

- Envio de mensajes de usuario entre nodos.
- Descubrimiento y monitoreo de vecinos directos.
- Reenvio de mensajes en flooding.
- Tabla estatica de rutas en modo dijkstra.
- Construccion dinamica de rutas en modo lsr.
- Manejo de nodos que aparecen tarde, se caen o se recuperan.
- Interoperabilidad con variantes razonables del payload de LSP.

No se incluyen aqui resultados cuantitativos ni evidencias de ejecucion,
porque ya fueron levantados en la evaluacion correspondiente y se entregan
por separado.

## 5. Especificacion del protocolo

La implementacion sigue el documento de referencia del laboratorio:
[docs/Laboratorio3.md](docs/Laboratorio3.md) y la especificacion tecnica
[docs/protocolo.md](docs/protocolo.md).

### 5.1 Envelope comun

Todos los paquetes comparten un envelope con los campos:

- `version`
- `proto`
- `type`
- `from`
- `to`
- `ttl`
- `headers`
- `payload`

La implementacion mantiene `msg_id` y `checksum` dentro de `headers`, sin
agregar un campo externo `id` al envelope.

### 5.2 Tipos de paquete

- `hello`: sondeo de vecino y anuncio de `listen_port`.
- `echo`: respuesta a `hello`, preservando `msg_id` y `t0`.
- `message`: mensaje de usuario.
- `info`: LSP usado por LSR.

### 5.3 Headers relevantes

- `msg_id`: identifica el paquete logico.
- `checksum`: CRC32 canonico del payload.
- `t0`: marca de tiempo usada para RTT.
- `via`: salto previo.
- `trace`: lista de nodos recorridos por mensajes.

### 5.4 Reglas de forwarding

- `hello` y `echo` no se reenvian.
- `message` en flooding se reenvia a todos los vecinos activos excepto el
  emisor previo.
- `message` en dijkstra/lsr se envia al `next_hop` calculado.
- `info` en `lsr` se difunde si aporta una secuencia mas nueva.
- TTL se decrementa por salto y un paquete con TTL no positivo se descarta.

## 6. Arquitectura general

El proyecto esta dividido en capas para aislar responsabilidades.

### 6.1 `protocol/`

Contiene la definicion del paquete, validacion, serializacion canonica y
constructores de paquetes comunes.

### 6.2 `transport/`

Implementa TCP persistente y framing NDJSON. Cada linea se limita a 65536
bytes. El receptor puede leer tanto conexiones entrantes como salientes,
lo que mejora la interoperabilidad con peers que contestan por el mismo
socket.

### 6.3 `config/`

Carga configuraciones de nodos y topologias desde JSON. Tambien resuelve
alias locales y direcciones `IP:puerto`.

### 6.4 `neighbors/`

Mantiene la tabla de vecinos, su costo y su estado. Incluye el health
checker basado en HELLO/ECHO y deteccion de fallos consecutivos.

### 6.5 `dedup/`

Contiene la caché temporal de `msg_id` para evitar reprocesamiento y loops
en flooding.

### 6.6 `algorithms/`

Incluye:

- `dijkstra.py`
- `flooding.py`
- `lsr.py`

### 6.7 `routing/`

Expone una interfaz uniforme para consultar rutas sin depender del modo.

### 6.8 `forwarding/`

Coordina la decision de entregar, reenviar o descartar paquetes.

### 6.9 `node.py`

Ensambla toda la aplicacion: servidor TCP, tablas de vecinos, routing,
forwarding, health check y mantenimiento LSR.

### 6.10 `cli.py`

Provee una consola interactiva con comandos para probar el nodo en tiempo
real.

## 7. Diseno e implementacion

### 7.1 Formato de paquete

La clase `Packet` centraliza la validacion del envelope. La serializacion del
checksum usa una representacion canonica del payload para que dos nodos que
generen el mismo contenido obtengan el mismo CRC32, aun si el orden de las
claves JSON difiere.

La implementacion permite tolerar:

- version ausente o distinta de `1`, con advertencia;
- checksum discrepante, con advertencia;
- variantes de payload LSP en formato texto JSON, mapa o lista de nodos.

### 7.2 Transporte

Se usa un parser NDJSON con buffer incremental. Esto permite procesar:

- mensajes partidos entre varios `recv()`;
- varias lineas en un solo `recv()`;
- lineas demasiado largas, que se descartan sin romper el proceso.

El canal TCP mantiene reconexion en enlaces salientes y asegura exclusión
mutua al enviar para evitar corrupcion de framing cuando varios hilos
comparten el mismo enlace.

### 7.3 Vecinos y salud del enlace

Cada vecino tiene:

- identificador logico;
- host y puerto;
- costo del enlace;
- estado activo/inactivo;
- contador de fallos consecutivos;
- RTT observado.

El health checker envía HELLO periodicamente, espera ECHO correlacionado por
`msg_id` y `t0`, y marca un vecino como caido tras exceder el numero maximo
de fallos. La recepcion de trafico de un vecino tambien cuenta como senal de
actividad.

### 7.4 Dijkstra

El algoritmo calcula la ruta mas corta sobre una topologia completa
representada como un grafo con costos no negativos. El resultado se expresa
como tabla de rutas con `destination`, `next_hop` y `cost`.

En modo `dijkstra`, la tabla se construye una sola vez al iniciar el nodo.
En modo `lsr`, el mismo algoritmo se reutiliza sobre la LSDB local
reconstruida dinamicamente.

### 7.5 Flooding

El flooding se implementa como una decision local sobre cada paquete
entrante. La logica:

- entrega local si el destino es el nodo actual o si el paquete es
  broadcast;
- reenvia a los vecinos activos salvo el emisor previo;
- usa deduplicacion para evitar loops;
- respeta TTL para limitar propagacion.

### 7.6 LSR

LSR construye una LSDB local a partir de LSPs originados por cada nodo. Cada
entrada se identifica por `(origin, seq)` y expira tras un tiempo de vida
fijo. Cuando llega un LSP mas nuevo:

- se actualiza la base de datos;
- se reconstruye la topologia;
- se recalculan las rutas;
- el LSP se vuelve a inundar por los vecinos activos.

El nodo origina su propio LSP al iniciar, periodicamente, y ante cambios de
estado o costo de vecinos. Tambien envia snapshots de la LSDB a vecinos que
aparecen despues, para acelerar convergencia.

## 8. Flujo operativo del nodo

1. Se carga la configuracion JSON.
2. Se normalizan direcciones y alias.
3. Se construyen tabla de vecinos, cache de dedup y motor de routing.
4. Se levanta el servidor TCP.
5. Se inicia el sondeo de vecinos.
6. En modo `lsr`, se origina el primer LSP y arranca el hilo de
   mantenimiento.
7. Los paquetes entrantes se parsean, validan y procesan por forwarding.
8. La CLI permite consultar vecinos, rutas y enviar mensajes.

## 9. Configuracion y despliegue

El repositorio incluye configuraciones listas para usar:

- `config/node_template.json`
- `config/local_test_5nodes/`
- `config/lab_9nodes_local/`
- `config/topologies/local_test_5nodes.json`
- `config/topologies/lab_9nodes.json`

La plantilla de ejemplo del laboratorio se renombro a
`config/node_template.json` para que su proposito sea mas claro. Esa misma
base de configuracion fue la que se utilizo en las pruebas reales de clase,
adaptando sus valores de red a la topologia y direcciones asignadas el dia de
la demostracion.

### 9.1 Estructura de `config/node_template.json`

Esta plantilla representa un nodo real de la red del laboratorio y sirve como
modelo para construir la configuracion final de cada equipo. Sus campos son:

- `node_id`: etiqueta local del nodo en la consola. Es un identificador
  humano, no la direccion de red.
- `listen.host`: direccion en la que el proceso escucha conexiones TCP. Se usa
  `0.0.0.0` cuando el nodo debe aceptar conexiones en todas las interfaces.
- `listen.port`: puerto local del nodo. Es el puerto donde el servidor TCP
  acepta conexiones entrantes.
- `advertised_host`: direccion que el nodo anuncia a sus vecinos. Debe ser una
  direccion alcanzable por los demas nodos; no necesariamente es `listen.host`.
- `network_port`: puerto por defecto para completar direcciones que no lo
  incluyan.
- `mode`: algoritmo activo en el nodo. Puede ser `lsr`, `flooding` o
  `dijkstra`.
- `neighbors`: lista de vecinos directos configurados.
  - `node_id`: identificador del vecino.
  - `host`: IP o nombre resolvible del vecino.
  - `port`: puerto del vecino.
  - `cost`: costo administrativo del enlace hacia ese vecino.
- `params`: parametros de operacion del nodo.
  - `initial_ttl`: TTL con el que se originan mensajes y LSPs.
  - `hello_interval_sec`: intervalo entre sondeos HELLO.
  - `hello_timeout_sec`: tiempo maximo de espera para un ECHO.
  - `hello_max_failures`: cantidad de fallos consecutivos permitidos antes de
    marcar un vecino como caido.
  - `dedup_cache_ttl_sec`: tiempo de vida de la cache de deduplicacion.
  - `lsp_refresh_interval_sec`: intervalo de reanuncio del LSP propio en LSR.
  - `log_level`: nivel de detalle de los logs.
- `addresses`: mapa opcional de alias locales hacia direcciones `IP:puerto`.
  Se usa para la consola y para resolver nombres cortos.
- `topology_file`: ruta a la topologia estatica. Solo es obligatoria en modo
  `dijkstra`.

En las pruebas de clase, esta plantilla fue ajustada con los datos reales de
red y con la topologia asignada al grupo, manteniendo el mismo esquema de
campos.

La configuracion separa:

- `listen.host` para el socket local;
- `advertised_host` para la direccion publica en el protocolo;
- `network_port` para completar direcciones sin puerto;
- `neighbors` para enlaces directos;
- `addresses` para alias de consola;
- `topology_file` para modo `dijkstra`.

## 10. Validacion realizada

Se realizaron pruebas unitarias e integracion durante el desarrollo para
verificar:

- serializacion y deserializacion del protocolo;
- CRC32 canonico;
- framing NDJSON;
- carga de configuracion;
- deduplicacion;
- flooding sin loops;
- Dijkstra sobre topologias de prueba;
- LSR con convergencia, expiracion y recuperacion;
- interoperabilidad con JSON externo;
- transporte TCP real en localhost;
- funcionamiento de nodos completos en topologias de 5 y 9 nodos.

Los resultados de esas pruebas no se incluyen aqui por no formar parte de
esta entrega redactada en este momento. El docente ya dispone de las
salidas correspondientes.

## 11. Discusion tecnica

La principal decision de diseno fue separar el protocolo de la logica de
enrutamiento. Eso evita mezclar parsing, transporte y algoritmos, y hace que
cada modulo sea reutilizable.

Otro punto importante fue mantener tolerancia de interoperabilidad sin
relajar la seguridad operativa. Por eso:

- checksum y version se registran, pero no bloquean el paquete;
- el identificador logico de LSP es `(origin, seq)`, no `msg_id`;
- el TTL sigue siendo una restriccion dura para evitar propagacion
  indefinida;
- la deduplicacion tiene expiracion para no retener informacion para siempre.

La arquitectura tambien evita asumir que el peer respondera por un socket
distinto al de entrada. Esto es importante en entornos heterogeneos y fue
considerado desde el diseno del transporte.

## 12. Limitaciones y supuestos

- El protocolo asume IPv4 `IP:puerto`.
- El algoritmo de flooding depende de deduplicacion para ser estable.
- `dijkstra` requiere una topologia completa conocida de antemano.
- `lsr` requiere periodicidad de refresco para que nodos que arranquen tarde
  lleguen a converger.
- La precision de RTT depende del reloj local y no se usa para calcular
  costos, solo para diagnostico.

## 13. Conclusiones

El proyecto cumple con la estructura funcional solicitada por el laboratorio
y ofrece una implementacion modular, interoperable y operable desde una CLI.
La separacion entre transporte, protocolo, vecinos, routing y forwarding
permite mantener cada pieza de forma independiente y reutilizar Dijkstra y
Flooding dentro de LSR sin duplicar logica.

Desde el punto de vista tecnico, el sistema queda preparado para pruebas de
demostracion con topologias cambiantes, caidas y recuperaciones de nodos, y
mensajeos multi-hop tanto en flooding como en enrutamiento por tabla.

## 14. Referencias

- [docs/Laboratorio3.md](docs/Laboratorio3.md)
- [docs/protocolo.md](docs/protocolo.md)
- [docs/arquitectura.md](docs/arquitectura.md)
- [docs/demo-guide.md](docs/demo-guide.md)
- [README.md](README.md)

## 15. Anexo: comandos de uso

### Levantar un nodo

```bash
python -m router.cli --config config/local_test_5nodes/node_A.json
```

### Ejecutar en flooding

```bash
python -m router.cli --config config/local_test_5nodes/node_A.json --mode flooding
```

### Ejecutar en dijkstra

```bash
python -m router.cli --config config/local_test_5nodes/node_A.json --mode dijkstra
```

### Consultar estado en la CLI

```text
neighbors
routes
send E mensaje de prueba
quit
```

## 16. Anexo: nota sobre resultados

Esta version del reporte no incluye tablas, graficas ni capturas de
resultados porque el usuario indico que esas evidencias ya fueron realizadas
y estan en poder del Goat JC.
