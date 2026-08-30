## Purpose

Define un sistema documental autocontenido que permita a cuatro integrantes trabajar en paralelo con cualquier IA, respetando las decisiones v1 y coordinando dependencias, límites, evidencia e integración sin requerir conocimiento de OpenSpec.

## ADDED Requirements

### Requirement: Fuentes obligatorias y reglas globales
El sistema documental SHALL indicar que todo contribuyente debe leer `Laboratorio3.md`, `openspec/config.yaml`, las specs principales de `openspec/specs/` y todos los documentos actuales de `docs/` antes de trabajar.

#### Scenario: Contribuyente inicia un paquete
- **WHEN** una persona recibe un handoff
- **THEN** puede identificar las fuentes obligatorias, reglas v1, límites de alcance y procedimiento ante una propuesta incompatible

### Requirement: Paquetes autocontenidos
El sistema SHALL proporcionar cuatro paquetes documentales, uno para foundation, uno para algoritmos, uno para transporte/forwarding y uno para LSR/health, cada uno con prerrequisitos, tareas exactas, archivos permitidos y prohibidos, pruebas futuras, Definition of Done y prompt reutilizable de IA.

#### Scenario: Paquete entregado a un integrante
- **WHEN** el integrante no conoce el proyecto ni OpenSpec
- **THEN** puede entender su responsabilidad, dependencias, evidencia esperada y condiciones de finalización leyendo únicamente el paquete y las fuentes obligatorias

### Requirement: Dependencias entre paquetes
Los handoffs SHALL declarar quién puede comenzar inmediatamente, qué paquete depende de merges previos y qué evidencia debe acompañar cada entrega.

#### Scenario: Integración ordenada
- **WHEN** se planifica el trabajo de los cuatro integrantes
- **THEN** foundation puede comenzar primero, algorithms puede avanzar sin sockets, transport/forwarding espera las interfaces de foundation y LSR/health espera foundation, algorithms y transport/forwarding

### Requirement: Control de alcance para IA
Los documentos SHALL ordenar a la IA no modificar decisiones v1, archivos prohibidos ni áreas fuera del paquete, y detenerse para reportar cualquier cambio de protocolo, arquitectura o alcance que parezca necesario.

#### Scenario: IA propone una modificación fuera de alcance
- **WHEN** una IA sugiere cambiar el sobre JSON, la arquitectura o un archivo prohibido
- **THEN** el contribuyente no aplica la sugerencia, la documenta y solicita decisión del equipo mediante revisión

### Requirement: Integración y revisión Git
El sistema SHALL documentar rama propia, ausencia de commits directos a la rama de integración, pull request, revisión, merge y pruebas posteriores a cada merge.

#### Scenario: Paquete listo para integrar
- **WHEN** un integrante termina su trabajo
- **THEN** entrega un pull request con checklist, evidencia y alcance revisable antes del merge

### Requirement: Documentación limitada a Markdown
Este cambio SHALL crear únicamente los siete archivos Markdown solicitados bajo `docs/contributors/` y SHALL excluir código, fuentes, tests ejecutables, dependencias y configuraciones ejecutables.

#### Scenario: Verificación del cambio
- **WHEN** se revisa el resultado del cambio
- **THEN** existen los siete documentos previstos y no existen `src/`, `tests/`, `requirements.txt`, `pyproject.toml` ni archivos de implementación creados por este cambio
