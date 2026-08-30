# Estrategia de pruebas v1

Las pruebas futuras deberán producir evidencia reproducible y mantenerse alineadas con `requirement-traceability.md`. Las pruebas automatizadas usarán `unittest`; `pytest` es opcional y no obligatorio.

## Nivel 1: unitario

Se cubrirán sobre JSON, validación, TTL, deduplicación, configuración, Dijkstra, Flooding, frescura LSP, expiración, topología y tabla LSR sin depender de sockets.

## Nivel 2: integración local

Varios procesos independientes usarán sockets TCP reales en localhost. Se verificarán framing, HELLO/ACK, LSP, convergencia, entrega, reenvío, prioridad de colas, duplicados, TTL, comandos y logs.

## Nivel 3: red e interoperabilidad

Se probarán varios equipos por Wi-Fi mediante access point y, cuando sea posible, por cable. Cada escenario conservará configuración, IPs, puertos, comandos previstos, topología, ruta esperada, resultado observado, logs y limitaciones.

## Escenarios mínimos

| Escenario | Resultado esperado |
|---|---|
| Ruta óptima | LSR selecciona el menor costo |
| Empate | Se aplica desempate determinista |
| Convergencia | Se reciben estados LSP válidos |
| Mensaje local | Se entrega sin reenvío |
| TTL agotado | Se descarta y registra |
| Duplicado | Se descarta y no se propaga |
| LSP antiguo | Se rechaza |
| Enlace unilateral | Se diagnostica, no se usa |
| Nodo detenido | Se marca caído después del límite |
| Nodo reiniciado | Se marca activo y actualiza LSR |
| IP/puerto cambiado | La topología opera con configuración actualizada |
| Otro grupo | Intercambio compatible con v1 |

La evidencia debe mostrar comportamiento y logs verificables, no solo la ejecución de un comando.
