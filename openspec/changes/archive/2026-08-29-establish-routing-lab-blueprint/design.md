## Context

Este cambio define un sistema académico nuevo; no existe todavía una implementación que preservar. La guía `Laboratorio3.md` exige nodos independientes, comunicación por sockets, forwarding y routing concurrentes, y módulos reutilizables de Dijkstra, Flooding y LSR. La red de demostración puede cambiar de IP y medio físico, por lo que la configuración debe separar identidad lógica, dirección IP, puerto y costo.

El contrato externo es TCP con un objeto JSON por línea y el sobre exacto `proto`, `type`, `from`, `to`, `ttl`, `headers` y `payload`. La motivación y el alcance están en `proposal.md`; los contratos observables están en las cinco especificaciones delta.

## Goals / Non-Goals

**Goals:**

- Proporcionar un runtime de nodo común para los tres modos.
- Aislar protocolo, transporte, forwarding, routing, algoritmos, health checks y logs.
- Permitir pruebas deterministas en memoria, multi-proceso y multi-host.
- Hacer que LSR converja, recalcule rutas y se recupere de cambios de vecinos.
- Mantener el protocolo v1 interoperable y sin campos principales adicionales.

**Non-Goals:**

- Implementar protocolos reales como OSPF.
- Persistir estado entre reinicios o resolver especialmente el reinicio de secuencias LSP.
- Usar UDP, conexiones persistentes, broadcast real, ACK/reintentos de usuario, TLS o interfaz web.

## Decisions

### Separación de responsabilidades

El transporte solo entrega líneas JSON y reporta fallos. Forwarding valida, deduplica, aplica TTL, entrega localmente o solicita el siguiente salto. Routing consume eventos y publica estados completos. Dijkstra, Flooding y LSR reciben estructuras abstractas y no conocen sockets, hilos ni colas.

Se consideró mezclar forwarding y routing en un único controlador, pero se descarta porque dificultaría las pruebas puras y podría bloquear el tránsito de paquetes durante un recálculo.

### Identidad y rutas

La configuración mantiene el mapeo `logical_id -> IP, puerto, vecinos y costos`. Dijkstra y las tablas internas usan IDs lógicos. Para `message`, `from` y `to` conservan IP origen y destino final; el siguiente salto solo selecciona el vecino físico de la conexión. `to_node` es metadato auxiliar.

Se consideró enrutar directamente por IP, pero se descarta porque la guía requiere topología lógica y porque cambiarían las IPs de clase.

### Transporte y concurrencia

Cada envío abre una conexión TCP, transmite una línea JSON, espera completar el envío y cierra. El listener acepta una línea por conexión. Hilos y colas desacoplan recepción, routing y envío; una cola saliente prioriza control sobre usuario. La tabla publicada se reemplaza atómicamente por referencia completa.

Se consideraron conexiones persistentes y `asyncio`; quedan fuera de v1 para reducir complejidad operacional y dependencias conceptuales del laboratorio.

### Protocolo y control

`message`, `lsp`, `hello` y `hello_ack` usan las estructuras de v1. Los LSP usan difusión lógica `255.255.255.255`, pero cada copia es unicast TCP. La entrada física identifica el vecino de recepción; no se agrega un campo de siguiente salto.

Se consideró agregar `next_hop`, `version` u otros campos al sobre, pero se descarta para mantener compatibilidad literal con la guía; los metadatos extensibles permanecen en `headers` o `payload`.

### LSR y frescura

Cada originador mantiene `sequence` durante la ejecución, genera LSP iniciales, de cambio y de refresco. Los receptores usan `origin_node + sequence` para frescura, guardan el momento monotónico de aceptación y expiran por `age_seconds`. La topología utilizable exige anuncios mutuos de enlaces activos.

Se consideró usar el reloj remoto para la edad, pero se descarta por diferencias entre equipos; el tiempo transcurrido se mide localmente.

### Modos de algoritmo

`dijkstra` carga topología completa y calcula rutas estáticas; `flooding` conoce vecinos directos y controla TTL/duplicados; `lsr` construye la topología con LSP y ejecuta Dijkstra. Los tres reutilizan runtime, protocolo, CLI y observabilidad.

### Pruebas y observabilidad

La verificación avanza de unitarias con `unittest` a integración con procesos y TCP real en localhost, y finalmente a pruebas manuales multi-host. Cada escenario conserva configuración, comandos, resultados y logs. Los logs son legibles, por nodo y configurables; un error de escritura no debe detener el nodo.

## Risks / Trade-offs

- **Reinicio de secuencia LSP** → aceptar la limitación en v1 y depender de la expiración del estado anterior.
- **IP o puerto inválido en clase** → validar configuración y documentar una actualización coordinada del archivo compartido.
- **Costo de conexión por paquete** → usar colas y timeouts; dejar una abstracción de transporte reemplazable.
- **Convergencia lenta** → emitir LSP inicial y por cambios inmediatamente, además del refresco periódico.
- **Incompatibilidad entre grupos** → congelar el protocolo v1 y probar ejemplos de mensajes antes de la práctica.
- **Tormentas de flooding** → TTL, exclusión del vecino de entrada, UUID4 y caché acotada.
- **Carreras entre forwarding y routing** → colas separadas y reemplazo atómico de tablas.
- **Logs no escribibles** → conservar consola y continuar la operación.

## Migration Plan

No hay sistema existente que migrar. La ejecución futura deberá introducir los incrementos en el orden indicado por `tasks.md`: contrato y configuración, transporte/runtime, forwarding, algoritmos, health checks, LSR, observabilidad y verificación. Si un incremento falla, se podrá detener en el último cambio aprobado sin modificar la guía ni los contratos ya congelados.

## Open Questions

No quedan decisiones de arquitectura pendientes para v1. La elección de nombres concretos de módulos, rutas internas de archivos y detalles menores de presentación puede resolverse durante la implementación sin cambiar los contratos de las especificaciones.
