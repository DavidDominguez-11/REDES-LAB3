# Checklist de integración

## Orden exacto

```text
Foundation ───────┐
                  ├─► Transport/Forwarding ──┐
Algorithms ───────┘                          ├─► LSR/Health ──► integración final
```

1. Foundation se integra primero.
2. Algorithms puede avanzar en paralelo, pero se integra validando sus interfaces.
3. Transport/Forwarding se integra después de Foundation.
4. LSR/Health se integra después de Foundation, Algorithms y Transport/Forwarding.
5. La integración final se valida sobre localhost, multi-host e interoperabilidad.

## Checklist de cada pull request

- [ ] La rama corresponde a un solo paquete.
- [ ] Se leyeron las fuentes obligatorias.
- [ ] El PR enumera archivos modificados y archivos fuera de alcance no modificados.
- [ ] Las interfaces consumidas coinciden con la documentación aprobada.
- [ ] Se respetan `proto`, `type`, `from`, `to`, `ttl`, `headers` y `payload`.
- [ ] `from`/`to` siguen siendo IPs y no existe `next_hop` en el JSON.
- [ ] Se adjuntan pruebas y resultados proporcionales al paquete.
- [ ] Se adjuntan logs o evidencia cuando corresponde.
- [ ] Se documentan limitaciones y propuestas no aplicadas.
- [ ] Otro integrante revisó el PR.

## Verificación posterior a cada merge

1. Revisar el diff y confirmar que no aparezcan archivos prohibidos.
2. Ejecutar las verificaciones del paquete integrado.
3. Ejecutar las verificaciones de los paquetes anteriores.
4. Registrar resultado, fecha, configuración y limitaciones.
5. Solo después habilitar el paquete dependiente.

## Pruebas finales

### Localhost

- Varios procesos independientes.
- Dijkstra, Flooding y LSR por separado.
- HELLO/ACK, LSP, convergencia, rutas, TTL, duplicados, caída y recuperación.

### Multi-host

- Misma configuración lógica con IPs y puertos coordinados.
- Prueba por Wi-Fi mediante access point y por cable cuando sea posible.
- Firewall, conectividad y logs de cada equipo.

### Interoperabilidad

- Ambos lados usan protocolo v1.
- Se verifican sobre, tipos, headers, payloads, IPs, TTL, LSP y rutas.
- Se prueba un mensaje LSR de extremo a extremo.

## Conflictos

Si un conflicto toca protocolo, arquitectura, costos, topología lógica o límites de paquete:

1. No resolverlo eligiendo silenciosamente una versión.
2. Comparar con `Laboratorio3.md`, `openspec/specs/` y `docs/`.
3. Mantener la decisión v1 aprobada.
4. Escalar la discrepancia al equipo y documentarla en el PR.
5. Rehacer el cambio solo después de una decisión explícita.
