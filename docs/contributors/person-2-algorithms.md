# Persona 2 — Algorithms

## Objetivo

Preparar Dijkstra y Flooding como módulos puros, reutilizables por LSR y completamente independientes de sockets, hilos, colas y CLI.

## Dependencias y disponibilidad

- Puede comenzar inmediatamente en paralelo con Foundation.
- No requiere sockets ni merge previo para definir y probar la lógica pura.
- Debe coordinar los formatos de entrada/salida con Foundation antes del merge.
- LSR/health consume estos módulos y espera su merge aprobado.

## Interfaces requeridas

Las interfaces futuras deben trabajar con estructuras abstractas:

- Dijkstra recibe una topología por IDs lógicos y costos no negativos.
- Dijkstra produce por destino costo total, siguiente salto, camino y alcanzabilidad.
- Empates: siguiente salto lógico menor; si persiste, camino completo lexicográficamente menor.
- Flooding recibe mensaje, TTL, vecinos directos y vecino de entrada.
- Flooding devuelve decisiones de entrega o vecinos de reenvío sin abrir conexiones.

## Tareas exactas futuras

1. Definir la representación abstracta de topología y tabla de rutas.
2. Implementar Dijkstra estático sobre IDs lógicos.
3. Implementar desempate determinista.
4. Definir Flooding controlado sin transporte.
5. Aplicar exclusión del vecino de entrada, TTL y deduplicación mediante una abstracción recibida.
6. Documentar contratos para que LSR pueda reutilizar ambos módulos.

## Archivos permitidos y prohibidos

Permitidos en una futura entrega:

- `router/algorithms/__init__.py`
- `router/algorithms/dijkstra.py`
- `router/algorithms/flooding.py`
- `router/algorithms/types.py` si contiene solo estructuras algorítmicas.

Prohibidos:

- cualquier importación o apertura de sockets;
- listener, TCP, hilos, colas, CLI, logs o health checks;
- LSP o base de estados LSR;
- edición de archivos de Foundation sin coordinación;
- `src/`, `tests/`, dependencias o configuración ejecutable fuera de un cambio aprobado.

## Pruebas futuras

- Rutas óptimas y topologías desconectadas.
- Nodos aislados y costos inválidos.
- Empates deterministas.
- Flooding en topologías con ciclos.
- TTL límite, vecino de entrada y mensajes duplicados.
- Confirmación de que los módulos funcionan sin sockets.

## Definition of Done

- Dijkstra y Flooding tienen interfaces documentadas y módulos separados.
- Ningún módulo conoce transporte, runtime o archivos de configuración.
- Los casos normales, errores, ciclos, TTL y empates están cubiertos.
- Los resultados y limitaciones acompañan el pull request.
- El paquete no cambia decisiones v1 ni invade otros paquetes.

## Prompt de IA

Lee `docs/contributors/00-read-first.md`, este archivo, `Laboratorio3.md`, `openspec/config.yaml`, todas las specs principales y todos los documentos actuales de `docs/`. Trabaja únicamente en Dijkstra y Flooding puros. No uses ni implementes sockets, TCP, hilos, colas, CLI, logs, HELLO, LSP, health checks o LSR. Opera con IDs lógicos y costos abstractos; conserva la independencia requerida para que LSR reutilice los módulos. Modifica solo los archivos permitidos; no crees `src/`, `tests/`, dependencias ni configuración ejecutable. Si una decisión de interfaz, protocolo o arquitectura no está cubierta, detente y repórtala. Cuando exista un cambio de implementación aprobado, ejecuta las verificaciones del paquete y reporta archivos, resultados y limitaciones.
