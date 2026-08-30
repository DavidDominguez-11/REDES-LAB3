# Hoja de ruta futura de implementación

Este documento es una guía de planificación. No crea tareas aplicables al cambio actual ni autoriza crear código. Cada etapa deberá ejecutarse mediante un cambio OpenSpec aprobado, con pruebas proporcionales y evidencia.

1. Contrato de protocolo JSON v1.
2. Configuración e identidad lógica.
3. Transporte TCP por paquete.
4. Runtime, hilos y colas.
5. Forwarding, TTL y deduplicación.
6. Dijkstra independiente.
7. Flooding independiente.
8. Health checks HELLO/ACK.
9. Base y ciclo de vida de LSP.
10. Integración LSR.
11. CLI y operación.
12. Logs y observabilidad.
13. Pruebas unitarias y multi-proceso.
14. Pruebas multi-host e interoperabilidad.
15. Documentación de resultados y entrega académica.

La dependencia principal es secuencial hasta disponer de protocolo, configuración y transporte. Dijkstra y Flooding deben conservar interfaces independientes para que LSR pueda reutilizarlos.
