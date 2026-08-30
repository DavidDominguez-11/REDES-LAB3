## 1. Preparación y fuentes

- [x] 1.1 Revisar `Laboratorio3.md`, `openspec/config.yaml`, todas las specs principales y todos los documentos actuales de `docs/`; verificar que las decisiones v1 y sus límites queden identificados como fuentes obligatorias.
- [x] 1.2 Crear únicamente el directorio documental `docs/contributors/`; verificar que el cambio no cree `src/`, `tests/`, dependencias, archivos de configuración ejecutables ni código.

## 2. Guía común

- [x] 2.1 Crear `docs/contributors/00-read-first.md` con explicación del proyecto, reglas innegociables, fuentes obligatorias, flujo Git, revisión por pull request y procedimiento ante propuestas fuera de alcance; verificar que sea comprensible sin conocer OpenSpec.

## 3. Paquetes de contribución

- [x] 3.1 Crear `docs/contributors/person-1-foundation.md` con foundation, configuración, modelos compartidos, estructura mínima, validación y CLI base; incluir prerrequisitos, tareas futuras, archivos permitidos/prohibidos, pruebas futuras, Definition of Done y prompt de IA; verificar consistencia con `node-runtime` y `configuration-v1`.
- [x] 3.2 Crear `docs/contributors/person-2-algorithms.md` con Dijkstra y Flooding puros y sin sockets; incluir interfaces requeridas, tareas futuras, pruebas futuras, archivos permitidos/prohibidos, Definition of Done y prompt de IA; verificar consistencia con `routing-algorithms` y la independencia de los algoritmos.
- [x] 3.3 Crear `docs/contributors/person-3-transport-forwarding.md` con listener TCP, framing JSON, colas, TTL, deduplicación, forwarding y logs base; declarar dependencia de foundation, límites, pruebas futuras, Definition of Done y prompt de IA; verificar consistencia con `routing-protocol-v1`, `node-runtime` y `architecture-v1`.
- [x] 3.4 Crear `docs/contributors/person-4-lsr-health.md` con HELLO/ACK, vecinos, LSP, base de estado, expiración, flooding de LSP y convergencia LSR; declarar dependencia de foundation, algorithms y transport/forwarding, límites, pruebas futuras, Definition of Done y prompt de IA; verificar consistencia con `routing-algorithms`, `neighbor-health` y `routing-protocol-v1`.

## 4. Integración y prompts

- [x] 4.1 Crear `docs/contributors/integration-checklist.md` con orden exacto de integración, checklist de pull request por paquete, verificación posterior a cada merge, pruebas localhost/multi-host/interoperabilidad y resolución de conflictos sin alterar v1; verificar que identifique qué paquete puede comenzar y cuáles esperan merges previos.
- [x] 4.2 Crear `docs/contributors/agent-prompts.md` con un prompt copiable para cada paquete; verificar que cada prompt obligue a leer fuentes, respetar alcance, no modificar archivos prohibidos, ejecutar las verificaciones futuras y reportar cambios, resultados y limitaciones.

## 5. Revisión documental final

- [x] 5.1 Revisar que cada paquete sea autocontenido y contenga dependencias, archivos permitidos/prohibidos, pruebas futuras, Definition of Done y prompt; verificar cobertura de los cuatro responsables.
- [x] 5.2 Cruzar los siete documentos contra `Laboratorio3.md`, `openspec/config.yaml`, `openspec/specs/` y `docs/`; verificar que no cambien el sobre JSON, `from`/`to`, TTL, transporte, costos, modos, LSP, health checks ni otras decisiones v1.
- [x] 5.3 Verificar que los handoffs describan implementación futura sin presentarla como existente y que no requieran conocer OpenSpec para usarse; registrar cualquier inconsistencia para revisión antes del merge.
- [x] 5.4 Verificar que solo existan los siete archivos Markdown solicitados bajo `docs/contributors/`, sin código, fuentes, tests ejecutables, dependencias ni configuración ejecutable; entregar el inventario documental como evidencia.
- [x] 5.5 Ejecutar `openspec validate --strict` y verificar que el cambio de planificación y documentación sea válido.
