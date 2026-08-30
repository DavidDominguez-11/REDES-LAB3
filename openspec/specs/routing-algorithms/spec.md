# routing-algorithms Specification

## Purpose

Define el comportamiento observable de Dijkstra, Flooding y Link-State Routing como algoritmos independientes y combinables con el runtime común del nodo.

## Requirements

### Requirement: Dijkstra estático
El modo Dijkstra SHALL cargar una topología completa, operar con IDs lógicos y producir rutas con costo, siguiente salto, camino y alcanzabilidad.

#### Scenario: Ruta óptima
- **WHEN** existe más de un camino entre origen y destino
- **THEN** se selecciona el camino de menor costo total

#### Scenario: Empate determinista
- **WHEN** dos rutas tienen el mismo costo
- **THEN** se elige primero el siguiente salto lógico menor y después el camino lexicográficamente menor

### Requirement: Flooding controlado
El modo Flooding SHALL usar únicamente vecinos directos configurados, reenviar a vecinos distintos del enlace de entrada y aplicar TTL y deduplicación.

#### Scenario: Propagación
- **WHEN** llega un `message` nuevo y `ttl > 1`
- **THEN** se entrega si corresponde localmente o se reenvía a los vecinos permitidos con TTL reducido

#### Scenario: Paquete repetido
- **WHEN** un mensaje vuelve por otro camino con el mismo `message_id`
- **THEN** se descarta y no se vuelve a propagar

### Requirement: Originación y propagación LSP
El modo LSR SHALL originar LSP iniciales, por cambios de vecinos y periódicamente, usando vecinos activos y costos configurados.

#### Scenario: LSP inicial
- **WHEN** un nodo LSR abre su listener
- **THEN** origina un LSP con su `origin_node`, secuencia creciente y vecinos activos actuales

#### Scenario: LSP nuevo
- **WHEN** un nodo recibe un LSP con mayor secuencia del mismo originador
- **THEN** lo acepta, registra, actualiza su estado y lo propaga a vecinos activos excepto el de entrada

### Requirement: Topología y tabla LSR
LSR SHALL usar únicamente enlaces anunciados mutuamente por vecinos activos y SHALL reemplazar atómicamente su tabla de rutas tras cada actualización relevante.

#### Scenario: Enlace unilateral
- **WHEN** un LSP anuncia un enlace que no está confirmado en ambos extremos
- **THEN** se conserva para diagnóstico pero no se usa para calcular rutas

#### Scenario: Recalculo
- **WHEN** se acepta, reemplaza o expira un LSP
- **THEN** se reconstruye la topología utilizable y se recalculan las rutas completas

### Requirement: Enrutamiento por modo
Los tres modos SHALL usar el mismo sobre y forwarding, pero únicamente LSR SHALL depender de convergencia LSP.

#### Scenario: Mensaje sin ruta LSR
- **WHEN** un mensaje de usuario no tiene ruta alcanzable durante convergencia
- **THEN** se descarta, registra como destino inalcanzable y no se reintenta
