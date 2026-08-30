## Context

El proyecto ya tiene un blueprint archivado con decisiones v1, cinco specs principales y siete documentos operativos bajo `docs/`. Este cambio no altera esos contratos; crea una capa documental para distribuir la implementación futura entre cuatro integrantes que pueden usar IAs distintas y no necesariamente conocen OpenSpec.

## Goals / Non-Goals

**Goals:**

- Hacer cada paquete autocontenido, accionable y trazable a las fuentes aprobadas.
- Explicitar dependencias entre foundation, algorithms, transport/forwarding y LSR/health.
- Estandarizar prompts, límites, evidencia, Definition of Done y flujo Git.
- Mantener los handoffs sincronizados con las decisiones v1 sin duplicar autoridad técnica.

**Non-Goals:**

- Crear o modificar código, tests ejecutables, dependencias o configuración ejecutable.
- Cambiar las specs de routing, el protocolo JSON, la arquitectura o la hoja de ruta existente.
- Introducir OpenSpec como requisito para los contribuyentes o sus IAs.

## Decisions

### Siete documentos en `docs/contributors/`

Se crearán una guía común, cuatro paquetes por área, un checklist de integración y un archivo de prompts. Esta estructura permite entregar un archivo individual sin perder reglas comunes ni coordinación global.

Se consideró crear un documento único, pero se descarta porque cada integrante necesita un alcance independiente y fácil de compartir.

### Fuentes con autoridad explícita

Los handoffs tratarán `Laboratorio3.md` como guía del profesor, `openspec/config.yaml` como contexto del proyecto, `openspec/specs/` como contrato funcional y `docs/` como documentación operativa. En caso de contradicción, el contribuyente debe detenerse y reportar el conflicto; no reinterpretar v1.

### Dependencias de trabajo

Foundation es el primer paquete. Algorithms puede trabajar en paralelo porque sus módulos son puros. Transport/forwarding depende de los modelos e interfaces acordados por foundation. LSR/health depende de foundation, algorithms y transport/forwarding. La integración se realiza mediante pull requests y pruebas documentadas.

### Prompts defensivos

Cada prompt obliga a leer fuentes, limitar archivos, no aplicar decisiones nuevas, ejecutar las verificaciones del paquete y reportar cambios, pruebas y limitaciones. Las propuestas de alcance se documentan para revisión, no se absorben silenciosamente.

### Documentación futura, no implementación actual

Los documentos describirán tareas futuras de desarrollo y pruebas, pero `tasks.md` de este cambio solo planificará la redacción y verificación de Markdown. La existencia de comandos o archivos en los handoffs se marcará como prevista hasta que un cambio posterior los implemente.

## Risks / Trade-offs

- **Handoffs desactualizados** → verificar cada documento contra las fuentes antes de integrarlo.
- **Interfaces incompatibles entre paquetes** → usar dependencias explícitas, checklist de PR y pruebas después de cada merge.
- **IA modifica fuera de alcance** → incluir reglas de detención y prompts obligatorios.
- **Paralelismo excesivo** → permitir solo algorithms en paralelo temprano; mantener orden para los paquetes dependientes.
- **Duplicación de decisiones** → referenciar las specs y documentos fuente en lugar de crear contratos alternativos.

## Migration Plan

No hay migración de código. La futura adopción consiste en entregar `00-read-first.md`, asignar un paquete por integrante, trabajar en ramas propias y revisar los pull requests en el orden documentado. Si una fuente cambia, se revisan los siete handoffs antes de continuar.

## Open Questions

No hay preguntas que bloqueen este cambio documental. Los nombres finales de ramas, revisores y fechas de integración pueden completarse por el equipo sin cambiar el contrato v1.
