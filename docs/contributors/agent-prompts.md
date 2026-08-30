# Prompts para agentes de IA

Cada prompt debe copiarse junto con el archivo de handoff correspondiente. La IA no necesita conocer OpenSpec para ejecutar el trabajo futuro, pero debe respetar las fuentes y límites indicados.

## Prompt 1 — Foundation

```text
Actúa como responsable de Foundation del proyecto CC3067 Laboratorio 3. Lee completamente Laboratorio3.md, openspec/config.yaml, todas las specs principales, todos los documentos actuales de docs/ y docs/contributors/00-read-first.md y person-1-foundation.md. Trabaja solo en configuración JSON compartida, modelos, validación y CLI base. Respeta Python 3.11+, IDs lógicos separados de IP/puerto, costos externos y el sobre exacto proto/type/from/to/ttl/headers/payload. No implementes sockets, transporte, forwarding, Dijkstra, Flooding, LSR, HELLO, LSP, health checks ni logs de transporte. Modifica solo los archivos permitidos por el handoff. No crees src/, tests/, requirements.txt, pyproject.toml, dependencias ni configuración ejecutable fuera del alcance aprobado. Si una decisión no está definida o propones cambiar protocolo/arquitectura, detente y reporta. Cuando exista autorización de implementación, ejecuta las verificaciones indicadas y entrega archivos modificados, resultados y limitaciones.
```

## Prompt 2 — Algorithms

```text
Actúa como responsable de Algorithms del proyecto CC3067 Laboratorio 3. Lee completamente Laboratorio3.md, openspec/config.yaml, todas las specs principales, todos los documentos actuales de docs/ y docs/contributors/00-read-first.md y person-2-algorithms.md. Trabaja solo en Dijkstra y Flooding como módulos puros, usando IDs lógicos, costos abstractos, TTL y deduplicación mediante interfaces, sin sockets. Conserva el desempate determinista y la reutilización por LSR. No implementes TCP, listener, hilos, colas, CLI, logs, HELLO, LSP, health checks ni runtime. Modifica solo archivos permitidos. No crees src/, tests/, dependencias ni configuración ejecutable fuera del alcance aprobado. Si falta una interfaz o se propone cambiar arquitectura/protocolo, detente y reporta. Con autorización de implementación, ejecuta verificaciones de rutas, empates, ciclos, TTL, duplicados e independencia de sockets; entrega archivos, resultados y limitaciones.
```

## Prompt 3 — Transport/Forwarding

```text
Actúa como responsable de Transport/Forwarding del proyecto CC3067 Laboratorio 3. Lee completamente Laboratorio3.md, openspec/config.yaml, todas las specs principales, todos los documentos actuales de docs/ y docs/contributors/00-read-first.md y person-3-transport-forwarding.md. Confirma primero que Foundation esté integrado. Trabaja solo en listener TCP por paquete, una línea JSON, timeouts, colas, prioridad, validación, TTL, deduplicación, forwarding y logs base. Conserva exactamente los siete campos principales; from y to son IPs, y no existe next_hop en JSON. No implementes algoritmos, LSP, HELLO/ACK, health checks ni LSR. Modifica solo archivos permitidos. No crees src/, tests/, dependencias ni configuración ejecutable fuera del alcance aprobado. Si una interfaz no existe o una propuesta cambia v1, detente y reporta. Con autorización, verifica framing, errores, TTL, duplicados, entrega, reenvío, prioridad y logs; entrega archivos, resultados y limitaciones.
```

## Prompt 4 — LSR/Health

```text
Actúa como responsable de LSR/Health del proyecto CC3067 Laboratorio 3. Lee completamente Laboratorio3.md, openspec/config.yaml, todas las specs principales, todos los documentos actuales de docs/ y docs/contributors/00-read-first.md y person-4-lsr-health.md. Confirma primero que Foundation, Algorithms y Transport/Forwarding estén integrados y revisados. Trabaja solo en HELLO/ACK, vecinos, LSP, frescura, expiración monotónica, flooding de LSP, topología mutuamente anunciada y convergencia LSR. Respeta costos fijos, sequence por ejecución, age_seconds, UUID4, ttl y to=255.255.255.255 como difusión lógica con TCP unicast físico. No agregues campos principales ni inventes solución para reinicio de sequence. Modifica solo archivos permitidos. No crees src/, tests/, dependencias ni configuración ejecutable fuera del alcance aprobado. Si falta una dependencia o una propuesta cambia protocolo/arquitectura, detente y reporta. Con autorización, verifica HELLO/ACK, caída, recuperación, LSP nuevos/antiguos/expirados, convergencia y recálculo; entrega archivos, resultados, logs y limitaciones.
```
