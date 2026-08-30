# Persona 1 — Foundation

## Objetivo

Preparar la base compartida para que los demás paquetes puedan trabajar con configuración, modelos, validación y punto de entrada coherentes.

## Dependencias y disponibilidad

- Puede comenzar inmediatamente.
- No depende de otro paquete implementado.
- Transport/forwarding debe esperar el merge de las interfaces de foundation.
- LSR/health debe esperar foundation, algorithms y transport/forwarding.

## Alcance futuro

- Lectura y validación del JSON compartido.
- Separación de ID lógico, IP, puerto, vecinos y costos.
- Modelos compartidos para nodo, vecino, paquete, rutas y configuración.
- Estructura mínima del paquete Python y entrada CLI prevista.
- Selección de `--node` y modo `dijkstra`, `flooding` o `lsr`.
- Sobrescrituras explícitas de host, puerto y nivel de log, con precedencia registrada.

## Tareas exactas futuras

1. Definir el modelo de configuración compartida y sus defaults.
2. Validar IDs, IPs, puertos, vecinos, costos y parámetros.
3. Definir modelos sin lógica de sockets para paquetes, vecinos y rutas.
4. Definir la forma de ejecución `python -m router --config config.json --node A --mode lsr`.
5. Documentar interfaces que consumirán los otros paquetes.
6. Mantener toda decisión v1 sin reinterpretación.

## Archivos permitidos y prohibidos

Permitidos en una futura entrega de este paquete, previa autorización de un cambio de implementación:

- `router/__init__.py`
- `router/__main__.py`
- `router/config.py`
- `router/models.py`
- `router/cli.py`
- documentación directamente relacionada con foundation.

Prohibidos para este paquete:

- sockets, listener, transporte o conexiones TCP;
- Dijkstra, Flooding, LSR, HELLO, LSP, forwarding o health checks;
- tests de otros paquetes;
- `src/`, `tests/`, `requirements.txt`, `pyproject.toml` y configuración ejecutable creada fuera del cambio aprobado.

## Pruebas futuras

- Configuración válida y topología pequeña.
- IDs duplicados, vecinos inexistentes, IP/puerto faltantes y costos inválidos.
- Selección de nodo y modo.
- Precedencia de argumentos CLI.
- Importación de modelos sin sockets.

## Definition of Done

- La configuración y los modelos tienen interfaces documentadas.
- La validación cubre todos los errores definidos en `configuration-v1.md`.
- La CLI prevista acepta los tres modos sin iniciar responsabilidades de otros paquetes.
- Las pruebas del paquete pasan y sus resultados acompañan el pull request.
- No se modificaron protocolo, arquitectura aprobada ni archivos fuera de alcance.

## Prompt de IA

Lee primero `docs/contributors/00-read-first.md`, este archivo, `Laboratorio3.md`, `openspec/config.yaml`, todas las specs de `openspec/specs/` y todos los documentos actuales de `docs/`. Trabaja únicamente en Foundation: configuración, modelos compartidos, validación y CLI base. No implementes sockets, algoritmos, forwarding, routing, HELLO, LSP, health checks ni logs de transporte. Respeta exactamente el sobre JSON v1, `from`/`to` como IPs y los costos externos. Modifica solo los archivos permitidos por este paquete; no crees `src/`, `tests/`, dependencias ni archivos de configuración ejecutables. Si propones cambiar arquitectura o protocolo, detente y repórtalo. Ejecuta únicamente las verificaciones del paquete cuando exista implementación aprobada y entrega un reporte de archivos, resultados y limitaciones.
