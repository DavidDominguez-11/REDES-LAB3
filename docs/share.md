# Protocolo compartido vigente

La especificación vigente es [protocolo.md](protocolo.md), copia de
`PROTOCOLO.md` acordado para la red del laboratorio. Sustituye la referencia
anterior de este repositorio.

Para conectar implementaciones deben usar el mismo `proto`, direcciones
IPv4:puerto, `from` como originador, `msg_id` y `checksum` en headers,
HELLO/ECHO correlacionados por `msg_id` y `t0`, y LSPs con vecinos
`[{id, weight}]`. El puerto común por defecto es 5000 y el TTL inicial es 16.

Los comandos y la configuración para la prueba conjunta se explican en
[demo-guide.md](demo-guide.md). Los alias A–I solo facilitan el uso local;
los paquetes siempre identifican los nodos por su dirección.
