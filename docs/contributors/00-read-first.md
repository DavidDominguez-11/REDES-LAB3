# Read first: reglas para contribuyentes

## Proyecto

CC3067 Laboratorio 3 es una simulación distribuida de nodos independientes que intercambian mensajes por TCP usando JSON por línea. Debe soportar Dijkstra, Flooding y Link-State Routing (LSR); la evaluación principal será LSR en una red local de clase.

## Fuentes obligatorias

Antes de modificar cualquier archivo, leer completamente:

1. `Laboratorio3.md` — guía y fuente de requisitos del profesor.
2. `openspec/config.yaml` — contexto, restricciones y reglas del proyecto.
3. Todas las specs bajo `openspec/specs/`.
4. Todos los documentos actuales bajo `docs/`.
5. Este directorio `docs/contributors/` y el paquete asignado.

Si hay contradicción, la guía y las specs aprobadas tienen prioridad. No inventar una solución ni cambiar una decisión v1 por iniciativa propia.

## Reglas globales innegociables

- Python 3.11+ y dependencias mínimas.
- El sobre JSON principal contiene exactamente `proto`, `type`, `from`, `to`, `ttl`, `headers` y `payload`.
- `from` y `to` son IP origen y destino; los IDs lógicos van en configuración, headers o payload.
- TCP procesa un JSON por línea y v1 abre una conexión por paquete.
- Los costos son fijos y externos; HELLO verifica disponibilidad, no cambia costos.
- Dijkstra, Flooding y LSR permanecen modulares; los algoritmos puros no conocen sockets.
- Forwarding y routing permanecen separados y concurrentes con hilos y colas.
- No añadir ACK/reintentos a mensajes de usuario, conexiones persistentes, UDP ni broadcast real en v1.
- `255.255.255.255` es difusión lógica para LSP; físicamente cada copia es TCP unicast.

## Flujo Git obligatorio

1. Crear una rama propia para el paquete asignado.
2. No hacer commits directos a la rama de integración ni a `main`.
3. Mantener el cambio limitado a los archivos permitidos por el paquete.
4. Ejecutar las verificaciones previstas y conservar sus resultados.
5. Abrir un pull request con resumen, archivos modificados, pruebas y limitaciones.
6. Esperar revisión de otro integrante.
7. Corregir observaciones en la misma rama.
8. Hacer merge únicamente después de aprobar el checklist y las pruebas posteriores.

## Si una IA propone algo fuera de alcance

No aplicar la propuesta. Registrar qué se propuso, por qué parece necesario y qué archivos afectaría. Consultar al equipo mediante el pull request o una decisión documentada. En particular, detenerse si la IA propone cambiar el protocolo, agregar campos principales, alterar la arquitectura, introducir dependencias o editar archivos prohibidos.
