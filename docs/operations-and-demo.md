# Operación y demostración previstas

Este documento describe la operación futura; los comandos no se consideran disponibles hasta aplicar los cambios de implementación correspondientes.

## Preparación

- Usar Python 3.11+.
- Compartir una configuración JSON por topología.
- Actualizar coordinadamente IPs y puertos de la red de clase.
- Verificar conectividad, firewall y puertos.
- Preparar logs por nodo.
- Mantener `Laboratorio3.md` sin modificaciones.

## Inicio previsto

```text
python -m router --config config.json --node A --mode lsr
```

Los modos previstos son `dijkstra`, `flooding` y `lsr`. Los argumentos explícitos podrán sobrescribir valores opcionales y esa decisión se registrará.

## Comandos locales previstos

```text
send <ip_destino> <id_destino> <mensaje>
routes
neighbors
status
quit
```

`send` originará el mensaje dentro del nodo, sin puerto de control adicional. Sin ruta, el resultado previsto será destino inalcanzable y no habrá reintento.

## Secuencia LSR

1. Distribuir y verificar la configuración común.
2. Iniciar nodos después de validar IPs y puertos.
3. Confirmar HELLO/ACK y vecinos activos.
4. Esperar LSP iniciales y convergencia.
5. Consultar rutas, vecinos y estado.
6. Enviar un mensaje y verificar ruta, saltos, entrega y logs.
7. Detener un proceso intermedio.
8. Verificar caída, nuevo LSP y recálculo.
9. Enviar otro mensaje y verificar la nueva ruta o descarte.
10. Reiniciar el proceso y verificar recuperación por HELLO.
11. Conservar configuración, comandos y logs para el reporte.

## Logs

Cada nodo tendrá archivo propio y consola configurable. Las entradas incluirán hora legible, ID local, nivel, evento, resultado y, cuando aplique, `type`, `proto`, `from`, `to`, TTL, `message_id` y siguiente salto.
