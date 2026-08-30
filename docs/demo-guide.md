# Guía de demostración para clase

Esta guía asume la red de prueba local de 5 nodos
(`config/local_test_5nodes/`). El día de la prueba conjunta, sustituir estos
archivos por la configuración real (IPs asignadas, topología acordada con
los demás grupos) siguiendo el mismo formato.

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
[E] << mensaje de C: hola desde A, esto viaja por la ruta óptima
```

(Se ve `de C`, no `de A`, porque `from` se actualiza en cada salto —
representa al último reenviador directo. El origen real y la ruta completa
quedan registrados en `headers[].hops` del paquete, visible en los logs si
se sube el nivel de log a `DEBUG`.)

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

## 6. Modo flooding independiente (opcional, para mostrar que no depende de LSR)

Crear (o pedir al ayudante) configuraciones equivalentes con `"mode":
"flooding"` en vez de `"lsr"`, y repetir el paso 3: el mensaje debe llegar a
destino igualmente, reenviado por todos los nodos intermedios (no solo por
la ruta óptima), y detenerse sin reenvíos indefinidos gracias al TTL y la
deduplicación.

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
