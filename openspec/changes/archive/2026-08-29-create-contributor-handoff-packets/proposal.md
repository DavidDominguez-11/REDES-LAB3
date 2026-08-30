## Why

El proyecto ya cuenta con decisiones v1, especificaciones y documentación técnica, pero cuatro integrantes necesitan poder trabajar en paralelo con distintas IAs sin conocer OpenSpec ni reinterpretar la arquitectura. Se necesita un paquete de handoff autocontenido para cada área, con límites claros, dependencias, evidencia esperada y reglas de colaboración.

## What Changes

- Crear documentación Markdown bajo `docs/contributors/` para orientar a cuatro responsables independientes.
- Crear una guía común de lectura, reglas innegociables, flujo Git y manejo de propuestas fuera de alcance.
- Crear paquetes para foundation, algoritmos, transporte/forwarding y LSR/health.
- Crear checklist de integración, revisión de pull requests, pruebas posteriores a merges e interoperabilidad.
- Crear prompts listos para entregar a una IA, con lectura obligatoria, límites, pruebas y reporte de resultados.
- Mantener intactas las decisiones del protocolo v1, la arquitectura aprobada y las especificaciones existentes.
- Mantener el cambio exclusivamente documental: no crear código, fuentes, tests ejecutables, dependencias ni configuración ejecutable.

## Capabilities

### New Capabilities

- `contributor-handoff-documentation`: Documentación autocontenida para distribuir el desarrollo futuro entre cuatro integrantes y coordinar su integración sin requerir conocimiento de OpenSpec.

### Modified Capabilities

- Ninguna. Las capacidades de routing existentes no cambian; solo se documentan para facilitar su futura implementación.

## Impact

- Añade únicamente archivos Markdown bajo `docs/contributors/`.
- La documentación referenciará `Laboratorio3.md`, `openspec/config.yaml`, las specs principales y los documentos actuales de `docs/`.
- No modifica el protocolo JSON v1, los costos, la configuración conceptual, los algoritmos, el transporte ni el comportamiento de LSR.
- No agrega dependencias ni altera el runtime previsto.

### Alcance

La documentación cubrirá el trabajo preparatorio y futuro de cuatro paquetes, sus dependencias y la integración. Los paquetes podrán implementarse posteriormente mediante cambios OpenSpec separados y aprobados.

### No alcance

Este cambio no implementa foundation, Dijkstra, Flooding, TCP, forwarding, TTL, deduplicación, logs, HELLO/ACK, LSP, LSR, CLI ni pruebas ejecutables. Tampoco crea `src/`, `tests/`, `requirements.txt`, `pyproject.toml` ni archivos de configuración ejecutables.

### Riesgos

- Una IA puede proponer cambios fuera del paquete o contrarios a v1; los handoffs deben ordenar detenerse y reportar la propuesta.
- Los paquetes pueden crear interfaces incompatibles si no se respetan las dependencias y el checklist de integración.
- La documentación puede quedar desactualizada si cambian las specs; cada paquete debe declarar sus fuentes y verificarse contra ellas.
- Cuatro ramas paralelas pueden producir conflictos; el flujo Git y la revisión centralizada deben ser obligatorios.

### Criterios de éxito y trazabilidad

- Existen exactamente los siete documentos solicitados bajo `docs/contributors/`.
- Cada paquete es autocontenido, identifica archivos permitidos/prohibidos, dependencias, pruebas futuras, Definition of Done y prompt de IA.
- La guía común exige leer las fuentes obligatorias y respetar el contrato v1.
- La integración define orden de merges, revisión, pruebas posteriores y resolución de conflictos.
- La documentación se puede verificar contra las secciones 3.1, 3.2 y 3.3 de `Laboratorio3.md` y las specs principales sin modificar ninguna decisión existente.
