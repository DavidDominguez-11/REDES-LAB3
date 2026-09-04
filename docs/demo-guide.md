# Guía de demostración para clase

Esta guía asume la red de prueba local de 5 nodos
(`config/local_test_5nodes/`). El día de la prueba conjunta, sustituir estos
archivos por la configuración real (IPs asignadas, topología acordada con
los demás grupos) siguiendo el mismo formato. El contrato vigente es
[protocolo.md](protocolo.md). Todos los nodos deben usar el mismo modo.

## 0. Preparación

```bash
python3 -m venv .venv
source .venv/bin/activate   # o .venv\Scripts\Activate.ps1 en Windows
pip install -r requirements.txt
export PYTHONPATH=src        # necesario para `python -m router.cli` (Windows: $env:PYTHONPATH = "src")
python -m pytest tests/ -q   # confirmar que todo pasa antes de la demo
```

## 1. Orden de inicio de nodos

No hay un orden estrictamente obligatorio (cada nodo intenta conectar a sus
vecinos y reintenta si no están listos aún), pero para una demo ordenada:

```bash
# Terminal 1
python -m router.cli --config config/local_test_5nodes/node_A.json
# Terminal 2
python -m router.cli --config config/local_test_5nodes/node_B.json
# Terminal 3
python -m router.cli --config config/local_test_5nodes/node_C.json
# Terminal 4
python -m router.cli --config config/local_test_5nodes/node_D.json
# Terminal 5
python -m router.cli --config config/local_test_5nodes/node_E.json
```

Cada nodo, al iniciar en modo `lsr`, anuncia su propio LSP a los pocos
milisegundos de arrancar. La convergencia completa de los 5 nodos toma
típicamente menos de 1 segundo en localhost.

## 2. Verificación de vecinos y convergencia

En cualquier terminal:

```
[A]> neighbors
    B  127.0.0.1:6001  costo=4  estado=activo  rtt=0.001s
    C  127.0.0.1:6002  costo=1  estado=activo  rtt=0.001s

[A]> routes
    B  next_hop=  C  costo=3
    C  next_hop=  C  costo=1
    D  next_hop=  C  costo=8
    E  next_hop=  C  costo=7
```

La ruta óptima esperada de A a E es vía C, costo 7 (A→C→E). Verificar que
todas las terminales muestran una tabla de ruteo consistente (rutas
simétricas, sin ciclos).

## 3. Envío de un mensaje

```
[A]> send E hola desde A, esto viaja por la ruta óptima
```

En la terminal de E debería aparecer:

```
[E] << mensaje de A (127.0.0.1:6000): hola desde A, esto viaja por la ruta óptima
```

El origen A se conserva en `from`. El salto anterior C viaja en `via` y
la traza en `trace`: ambos usan IP:puerto, aunque la consola muestre alias.

## 4. Simulación de caída de un vecino

Detener el nodo C (Ctrl+D o `quit` en su terminal, o cerrar el proceso).

En la terminal de A, tras unos segundos (según `hello_interval_sec` /
`hello_timeout_sec` / `hello_max_failures` configurados — con los valores
por defecto de `node_A.json`, del orden de 3-4 segundos):

```
[A]> routes
    ...
    E  next_hop=  B  costo=12
```

La ruta cambia a A→B→D→E (costo 12), evitando el nodo caído.

## 5. Recuperación

Volver a iniciar el nodo C con la misma configuración:

```bash
python -m router.cli --config config/local_test_5nodes/node_C.json
```

Tras el primer intercambio exitoso de HELLO/ECHO entre C y sus vecinos
(unos segundos), la ruta A→E debería volver a ser vía C, costo 7.

## 6. Modos flooding y dijkstra independientes

La guía del laboratorio pide poder levantar la red en `flooding` o en
`dijkstra` como algoritmo de la red, no solo como piezas internas de LSR. No
hace falta duplicar configuraciones: `--mode` sobreescribe el `mode` del JSON.

```bash
# En las 5 terminales, con el mismo config de cada nodo
python -m router.cli --config config/local_test_5nodes/node_A.json --mode flooding
```

Repetir el paso 3: el mensaje llega a destino igualmente, reenviado por todos
los nodos intermedios (no solo por la ruta óptima), y se detiene sin reenvíos
indefinidos gracias al TTL y la deduplicación. `routes` sale vacío, porque en
flooding no hay tabla de ruteo.

```bash
python -m router.cli --config config/local_test_5nodes/node_A.json --mode dijkstra
```

En `dijkstra` la tabla se calcula una sola vez al arrancar desde
`config/topologies/local_test_5nodes.json`, así que `routes` muestra las
mismas rutas que LSR ya convergido (A→E vía C, costo 7) pero **no** reacciona
a la caída de un nodo: es el contraste útil para el reporte.

## Conexión con otros grupos

Parte de `config/example_node.json`: coloca tu IP en `advertised_host`,
mantén `listen.host: "0.0.0.0"` y actualiza las IPs, puertos y costos de
los vecinos. El puerto común por defecto es 5000. Los alias `addresses`
son opcionales; actualízalos si quieres enviar usando nombres.

```text
[A]> send 10.0.0.7:5000 hola desde mi grupo
```

La versión y CRC32 discrepantes se registran sin bloquear el tráfico.
Un paquete malformado o una línea mayor de 65536 bytes se descartan.
Revisa el log si no llega un mensaje: puede faltar una ruta, un enlace
estar caído o haberse agotado TTL. No hay ACK ni ERROR en el protocolo.

## Notas para el reporte

- Registrar el costo y ruta observados en cada paso (2, 3, 4, 5) como
  evidencia de convergencia y de adaptación a caída/recuperación.
- Si se corre con log level `DEBUG`
  (`--log-level DEBUG`), los logs por nodo muestran cada decisión de
  entrega/reenvío/descarte, útiles como evidencia adicional para la sección
  de "Resultados" del reporte.
- No se han llenado resultados de la prueba conjunta con otros grupos en
  esta guía porque aún no se ha realizado; esa sección del reporte debe
  completarse después de la demo real en clase.
