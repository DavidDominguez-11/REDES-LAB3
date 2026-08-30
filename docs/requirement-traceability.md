# Trazabilidad de requisitos

Este documento relaciona la guía del profesor con el blueprint OpenSpec y la evidencia que deberá producir la implementación futura. La fuente normativa es `Laboratorio3.md`; esta matriz no reemplaza esa guía.

| Fuente en `Laboratorio3.md` | Requisito resumido | Capacidad OpenSpec | Evidencia futura |
|---|---|---|---|
| 2. Objetivos | Comprender y analizar algoritmos de routing | `routing-algorithms` | Documento técnico, tablas y análisis de resultados |
| 3 | Simular nodos independientes interconectados | `node-runtime` | Configuración, procesos y logs por nodo |
| 3.1 | Implementar Dijkstra | `routing-algorithms` | Casos de rutas óptimas, desconectadas y empates |
| 3.1 | Implementar Flooding con vecinos locales | `routing-algorithms` | Propagación controlada, TTL y deduplicación |
| 3.1 | Implementar LSR usando estados de enlace | `routing-algorithms` | LSP, convergencia, tablas y recálculo |
| 3.1 | Mantener Dijkstra y Flooding modulares para LSR | `node-runtime`, `routing-algorithms` | Pruebas de algoritmos sin sockets |
| 3.2 | Usar protocolo JSON interoperable | `routing-protocol-v1` | `docs/protocol-v1.md` y mensajes entre grupos |
| 3.2 | Comunicar nodos por sockets | `node-runtime` | Intercambio TCP por procesos independientes |
| 3.3 | Separar forwarding y routing concurrentes | `node-runtime` | Diseño de hilos, colas y logs de flujo |
| 3.3 | Descubrir vecinos con HELLO/PING | `neighbor-health` | HELLO/ACK y estados de vecinos |
| 3.3 | Reenviar datos o entregar localmente | `routing-protocol-v1`, `routing-algorithms` | Logs de entrega y reenvío |
| 3.3 | Intercambiar información de tablas/enlaces | `routing-algorithms` | LSP recibidos, aceptados y propagados |
| 3.3 | Adaptarse a nodos caídos y recuperados | `neighbor-health` | Escenario de detener/reiniciar procesos |
| Rúbrica: código | Código modular, legible y funcional | Todas las capacidades | Revisión, pruebas y documentación futura |
| Rúbrica: interconexión | Prueba general entre grupos | `observability-and-verification` | Prueba LSR multi-host e interoperabilidad |
| Entrega | Reporte, código y repositorio | `observability-and-verification` | Reporte PDF, repositorio y matriz de resultados |

## Criterios de cobertura

- Cada requisito funcional tendrá al menos un escenario verificable en las especificaciones delta.
- Cada implementación futura deberá asociar pruebas y logs con esta matriz.
- La prueba principal será LSR en una red local; Dijkstra y Flooding también deberán poder probarse por separado.
- Las IPs, puertos y topologías concretas se documentarán como datos de prueba, no como requisitos fijos.
