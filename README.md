# CC3067 - Laboratorio 3 - Enrutamiento (Dijkstra / Flooding / LSR)

Implementación de una red de nodos, cada uno un proceso independiente que se
comunica por sockets TCP, capaz de operar en tres modos de enrutamiento:

- **Dijkstra**: topología estática (conocida por configuración).
- **Flooding**: cada nodo solo conoce a sus vecinos directos.
- **Link State Routing (LSR)**: usa Flooding para distribuir el estado de
  enlaces (LSP) y Dijkstra para calcular las rutas óptimas.

Ver también:
- [`docs/protocolo.md`](docs/protocolo.md) — especificación del protocolo JSON.
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

### Ejecutar en modo `dijkstra` o `flooding` de forma independiente

El mismo binario soporta los 3 modos; el modo se define en el `mode` del
JSON de configuración del nodo (`"dijkstra" | "flooding" | "lsr"`). En modo
`dijkstra` la config debe incluir `topology_file` apuntando a un archivo de
topología estática (ver `config/topologies/local_test_5nodes.json`).

## Pruebas

```bash
# Todas las pruebas (unitarias + integración, ~80 pruebas, corre en segundos)
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
  local_test_5nodes/node_{A..E}.json Config de cada nodo para la red de prueba local
docs/
  protocolo.md                      Especificación del protocolo (versión, framing, tipos, ejemplos)
  arquitectura.md                   Arquitectura de hilos, forwarding vs routing
  demo-guide.md                     Guía paso a paso para la demo de clase
src/router/
  protocol/    Paquete v1: definición, validación, (de)serialización, constructores por tipo
  transport/   Framing NDJSON + TCP (servidor y conexiones salientes reconectables)
  config/      Modelos y carga de configuración de nodo / topología
  neighbors/   Tabla de vecinos + health check (HELLO/ECHO, detección de caída/recuperación)
  dedup/       Caché de deduplicación de paquetes por msg_id
  algorithms/  dijkstra.py, flooding.py, lsr.py — independientes y reutilizables entre sí
  routing/     Fachada RoutingEngine (unifica dijkstra estático / lsr dinámico / sin tabla en flooding)
  forwarding/  Motor de forwarding: conecta transporte + dedup + routing + flooding
  node.py      Orquestador: junta todo, hilos de servidor/health-check
  cli.py       CLI interactiva
tests/
  unit/         Pruebas puramente lógicas (protocolo, dedup, dijkstra, flooding, lsr, health check...)
  integration/  Nodos reales en localhost: convergencia, ruta óptima, caída/recuperación, flooding sin loops
```

## Notas para la red del aula

- El formato de cable usa direcciones `IP:puerto`; `from` conserva el origen
  absoluto y `via` identifica el salto anterior al reenviar.
- `to: "*"` es la difusión lógica definida para los LSP `info`.
- **Topología real del salón**: la topología usada aquí (`local_test_5nodes`)
  es de prueba local. La imagen de topología incluida en la guía del
  laboratorio llegó truncada (el `base64` del SVG se corta a mitad de
  archivo) y no fue posible recuperar los pesos/aristas reales; hay que
  sustituir `config/topologies/local_test_5nodes.json` (o crear un archivo
  nuevo) con la topología e IPs que se asignen en clase.
- **Interoperabilidad**: el protocolo está documentado en
  [`docs/protocolo.md`](docs/protocolo.md); la validación contra otros grupos
  depende de la prueba conjunta.
- **Recuperación de enlaces individuales vs. nodo completo**: las pruebas de
  caída/recuperación simulan la caída de un **nodo completo** (se detiene su
  proceso), no de un enlace específico entre dos nodos activos. El
  mecanismo de health check (HELLO/ECHO con timeout) es el mismo en ambos
  casos, pero solo el escenario de nodo completo está cubierto por pruebas
  automatizadas.
- **CLI sin persistencia de historial de mensajes**: la CLI imprime los
  mensajes entrantes por stdout pero no los guarda; suficiente para la
  demo, no pensado como cliente de chat persistente.
