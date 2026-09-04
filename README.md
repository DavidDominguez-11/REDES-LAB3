# CC3067 - Laboratorio 3 - Enrutamiento (Dijkstra / Flooding / LSR)

Implementación compatible con el protocolo compartido de la clase en
[`docs/protocolo.md`](docs/protocolo.md). Cada nodo es un proceso independiente que se
comunica por sockets TCP, capaz de operar en tres modos de enrutamiento:

- **Dijkstra**: topología estática (conocida por configuración).
- **Flooding**: cada nodo solo conoce a sus vecinos directos.
- **Link State Routing (LSR)**: usa Flooding para distribuir el estado de
  enlaces (LSP) y Dijkstra para calcular las rutas óptimas.

Ver también:
- [`docs/protocolo.md`](docs/protocolo.md) — protocolo compartido vigente.
- [`docs/arquitectura.md`](docs/arquitectura.md) — arquitectura de hilos, forwarding/routing.
- [`docs/demo-guide.md`](docs/demo-guide.md) — guía paso a paso para la demo en clase.

## Requisitos

- Python 3.10 o superior (se probó con 3.12).
- Sin dependencias externas para correr los nodos (solo librería estándar).
- `pytest` para las pruebas (única dependencia, ver `requirements.txt`).

## Instalación

```bash
python3 -m venv .venv

# Linux/macOS
source .venv/bin/activate
# Windows (PowerShell)
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt

# El paquete vive en src/, así que hay que agregarlo al PYTHONPATH
# para poder ejecutar `python -m router.cli` (pytest ya lo hace solo,
# ver pytest.ini). En Linux/macOS:
export PYTHONPATH=src
# En Windows (PowerShell):
# $env:PYTHONPATH = "src"
```

## Ejecutar un nodo

Cada nodo se levanta con un archivo de configuración JSON (ver
`config/example_node.json` y `config/local_test_5nodes/` para ejemplos).

```bash
python -m router.cli --config config/local_test_5nodes/node_A.json
```

Esto abre una sesión interactiva:

```
Nodo A iniciado (lsr) en 127.0.0.1:6000
Escribe 'help' para ver los comandos disponibles.
[A]> neighbors
[A]> routes
[A]> send E hola desde A
[A]> quit
```

Comandos disponibles: `send <destino> <texto...>`, `neighbors`, `routes`,
`help`, `quit`/`exit`.

### Levantar la red de prueba local de 5 nodos

La topología de prueba (`config/topologies/local_test_5nodes.json`, nodos
A–E) tiene ruta óptima A→E vía C (costo 7) y ruta alterna A→C→B→D→E (costo
11) si el enlace C–E cae. En 5 terminales distintas, dentro del `venv`:

```bash
python -m router.cli --config config/local_test_5nodes/node_A.json
python -m router.cli --config config/local_test_5nodes/node_B.json
python -m router.cli --config config/local_test_5nodes/node_C.json
python -m router.cli --config config/local_test_5nodes/node_D.json
python -m router.cli --config config/local_test_5nodes/node_E.json
```

Guía completa de demostración (orden de arranque, verificación de
convergencia, envío de mensajes, simulación de caída/recuperación) en
[`docs/demo-guide.md`](docs/demo-guide.md).

### Ensayar la topología de la guía (9 nodos)

`config/lab_9nodes_local/` levanta en localhost la topología de la Imagen 1 de
la guía del laboratorio (nodos A–I). Sirve para ensayar con la topología real
antes de la demo; el día de la prueba hay que cambiar `host`/`port` de cada
vecino por las IPs que anuncie cada grupo.

```bash
python -m router.cli --config config/lab_9nodes_local/node_A.json
# ...y así con node_B.json .. node_I.json en otras terminales
```

La red converge en un par de segundos. La ruta A→H es `A-I-D-F-H`, costo 12.

### Ejecutar en modo `dijkstra` o `flooding` de forma independiente

El mismo binario soporta los 3 modos. El modo sale del campo `mode` del JSON
de configuración del nodo (`"dijkstra" | "flooding" | "lsr"`), y se puede
sobreescribir con `--mode` sin duplicar los archivos de configuración:

```bash
# La misma red de 5 nodos, levantada en flooding puro
python -m router.cli --config config/local_test_5nodes/node_A.json --mode flooding

# ...o en dijkstra puro (topología estática)
python -m router.cli --config config/local_test_5nodes/node_A.json --mode dijkstra
```

En modo `dijkstra` la config debe incluir `topology_file` apuntando a un
archivo de topología estática (ver `config/topologies/local_test_5nodes.json`);
las configs de `config/local_test_5nodes/` ya lo traen. En modo `flooding` no
hay tabla de ruteo: `routes` sale vacío y el mensaje llega a destino
reenviado por todos los vecinos, acotado por TTL y deduplicación.

## Parámetros de configuración (`params`)

| Parámetro | Default | Para qué sirve |
|---|---|---|
| `initial_ttl` | `16` | TTL con el que se originan los paquetes. |
| `hello_interval_sec` | `2.0` | Cada cuánto se sondea a cada vecino con `hello`. |
| `hello_timeout_sec` | `1.0` | Espera máxima del `echo` antes de contar un fallo. Debe ser **menor** que `hello_interval_sec`. |
| `hello_max_failures` | `3` | Fallos consecutivos antes de marcar un vecino como caído. |
| `dedup_cache_ttl_sec` | `30.0` | Cuánto vive un `msg_id` en la caché de deduplicación. |
| `lsp_refresh_interval_sec` | `10.0` | Cada cuánto reanuncia un nodo `lsr` su propio LSP. |
| `log_level` | `"INFO"` | Nivel de log del nodo. |

`lsp_refresh_interval_sec` es lo que hace que la red converja sin importar el
orden en que se levanten los nodos: el flooding solo reenvía un LSP en el
instante en que llega, así que un nodo que arranca tarde nunca vería los LSP
difundidos antes de existir. Ver
[`docs/arquitectura.md`](docs/arquitectura.md), sección "LSR: frescura, expiración y convergencia". Es un parámetro local: no cambia el formato del protocolo, pero
para la prueba conjunta conviene que todos los grupos usen valores parecidos
(igual que los de health check; ver el [protocolo compartido](docs/protocolo.md)).

## Pruebas

```bash
# Todas las pruebas (unitarias + integración, incluyendo interoperabilidad con JSON externo)
python -m pytest tests/ -v

# Solo unitarias (no abren sockets reales)
python -m pytest tests/unit -v

# Solo integración (levantan nodos/hilos/sockets reales en localhost)
python -m pytest tests/integration -v
```

Todas las pruebas de integración corren en `localhost` con puertos
efímeros asignados dinámicamente; **no requieren la red del aula**.

## Estructura del repositorio

```
config/
  example_node.json                 Plantilla de config de nodo (sin datos reales de red)
  topologies/local_test_5nodes.json Topología estática de prueba (5 nodos)
  topologies/lab_9nodes.json        Topología de la Imagen 1 de la guía (9 nodos A-I)
  local_test_5nodes/node_{A..E}.json Config de cada nodo para la red de prueba local
  lab_9nodes_local/node_{A..I}.json  La topología de la guía, para ensayarla en localhost
docs/
  protocolo.md                      Especificación del protocolo (versión, framing, tipos, ejemplos)
  arquitectura.md                   Arquitectura de hilos, forwarding vs routing
  demo-guide.md                     Guía paso a paso para la demo de clase
src/router/
  protocol/    Paquete v1: definición, validación, (de)serialización, constructores por tipo
  transport/   Framing NDJSON + TCP (servidor y conexiones salientes reconectables)
  config/      Modelos y carga de configuración de nodo / topología
  neighbors/   Tabla de vecinos + health check (HELLO/ECHO, detección de caída/recuperación)
  dedup/       Caché de deduplicación de paquetes por id
  algorithms/  dijkstra.py, flooding.py, lsr.py — independientes y reutilizables entre sí
  routing/     Fachada RoutingEngine (unifica dijkstra estático / lsr dinámico / sin tabla en flooding)
  forwarding/  Motor de forwarding: conecta transporte + dedup + routing + flooding
  node.py      Orquestador: junta todo, hilos de servidor/health-check
  cli.py       CLI interactiva
tests/
  unit/         Pruebas puramente lógicas (protocolo, dedup, dijkstra, flooding, lsr, health check...)
  integration/  Nodos reales en localhost: convergencia, ruta óptima, caída/recuperación, flooding sin loops
```

## Configurar la red del aula

`config/example_node.json` es una plantilla LAN. Sustituye
`advertised_host` por tu IP real y `neighbors[].host/port/cost` por los
datos acordados. `listen.host: "0.0.0.0"` escucha en todas las interfaces,
mientras `advertised_host` es la IP que viaja en el protocolo. El puerto
común se configura con `network_port` (5000 por defecto).

`node_id` y `addresses` son alias para la consola. Los archivos locales
ya incluyen el mapa A–E/A–I y conservan sus puertos separados para ejecutar
varios nodos en una misma máquina. Puedes escribir `send E hola` o
`send 10.0.0.7:5000 hola`; sin alias, usa la dirección. Una IP sin puerto
usa `network_port`. Al llevar una configuración local al aula, actualiza
también los alias remotos de `addresses` o elimínalos y usa IP:puerto.

## Formato compartido y verificación

- Envelope de ocho campos; `msg_id` y CRC32 en headers, sin `id` externo.
- `from` conserva el origen; `via` identifica el salto previo y `trace` la ruta.
- HELLO/ECHO devuelven el mismo `msg_id` y `t0`; payload con `listen_port`.
- LSPs con `age_s` y `neighbors: [{id, weight}]`; costos decimales.
- TTL inicial 16; líneas limitadas a 65536 bytes; lectura de respuestas
  tanto en conexiones entrantes como salientes.
- LSDB con expiración a 30 s y refresco por defecto cada 10 s.
- Checksum discrepante o versión distinta/ausente: se advierte y se procesa.

Las pruebas incluyen los dos vectores CRC32 del documento, expiración de
LSPs, límites de framing, forwarding multihop, recuperación y un vecino
simulado que construye JSON sin usar las clases de este proyecto y responde
por el mismo socket. La conexión con los equipos reales de otros grupos
sigue pendiente de la prueba en clase.

La regla principal de secuencias es estricta. Los reinicios se recuperan
mediante snapshots del contador propio y expiración; la heurística opcional
de saltos hacia atrás no se usa. Más detalle en
[arquitectura.md](docs/arquitectura.md).
