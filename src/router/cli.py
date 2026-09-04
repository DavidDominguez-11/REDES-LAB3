"""CLI para levantar un nodo y operarlo de forma interactiva.

Uso:
    python -m router.cli --config config/local_test_5nodes/node_A.json
    python -m router.cli --config config/local_test_5nodes/node_A.json --mode flooding

Comandos dentro de la sesión interactiva:
    send <destino> <texto...>   Envía un mensaje de usuario
    neighbors                   Lista vecinos y su estado (activo/inactivo)
    routes                      Muestra la tabla de ruteo actual
    help                        Muestra esta ayuda
    quit / exit                 Detiene el nodo y sale
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import sys

from router.config.loader import VALID_MODES, ConfigError, load_node_config
from router.node import Node

HELP_TEXT = """Comandos disponibles:
  send <destino> <texto...>   Envía un mensaje de usuario al destino indicado
  neighbors                   Lista vecinos configurados y su estado
  routes                      Muestra la tabla de ruteo actual
  help                        Muestra esta ayuda
  quit | exit                 Detiene el nodo y sale
"""


def _print_neighbors(node: Node) -> None:
    for n in node.list_neighbors():
        estado = "activo" if n.is_up else "INACTIVO"
        rtt = f"{n.last_rtt_sec:.3f}s" if n.last_rtt_sec is not None else "N/D"
        name = node.addresses.display(n.node_id)
        print(f"  {name:>3}  {n.host}:{n.port}  costo={n.cost:g}  estado={estado}  rtt={rtt}")


def _print_routes(node: Node) -> None:
    routes = node.list_routes()
    if not routes:
        print("  (tabla de ruteo vacía; en modo flooding no aplica)")
        return
    for dest, entry in sorted(routes.items()):
        print(f"  {dest:>3}  next_hop={entry.next_hop:>3}  costo={entry.cost:g}")


def run_repl(node: Node) -> None:
    print(f"Nodo {node.node_id} iniciado ({node.config.mode}) como {node.address}")
    print("Escribe 'help' para ver los comandos disponibles.")
    while True:
        try:
            line = input(f"[{node.node_id}]> ").strip()
        except EOFError:
            break
        if not line:
            continue
        parts = line.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd in ("quit", "exit"):
            break
        elif cmd == "help":
            print(HELP_TEXT)
        elif cmd == "neighbors":
            _print_neighbors(node)
        elif cmd == "routes":
            _print_routes(node)
        elif cmd == "send":
            if len(parts) < 3:
                print("Uso: send <destino> <texto...>")
                continue
            destination, text = parts[1], parts[2]
            try:
                node.send_message(destination, text)
            except ValueError as exc:
                print(f"Error: {exc}")
        else:
            print(f"Comando desconocido: {cmd!r}. Escribe 'help'.")

    print(f"Deteniendo nodo {node.node_id}...")


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nodo de la red de enrutamiento CC3067 Lab 3")
    parser.add_argument("--config", required=True, help="Ruta al archivo de configuración JSON del nodo")
    parser.add_argument("--repo-root", default=".", help="Raíz del repositorio (para resolver topology_file)")
    parser.add_argument("--log-level", default=None, help="Override del nivel de log (por defecto usa el de la config)")
    parser.add_argument(
        "--mode",
        default=None,
        choices=sorted(VALID_MODES),
        help="Override del modo de la config: permite levantar la misma red en "
        "'flooding' o 'dijkstra' sin duplicar los archivos de configuración",
    )
    args = parser.parse_args(argv)

    try:
        cfg = load_node_config(args.config)
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 1

    if args.mode is not None and args.mode != cfg.mode:
        if args.mode == "dijkstra" and not cfg.topology_file:
            print(
                f"Error: --mode dijkstra necesita que {args.config} declare 'topology_file' "
                "con la topología estática",
                file=sys.stderr,
            )
            return 1
        cfg = dataclasses.replace(cfg, mode=args.mode)

    log_level = args.log_level or cfg.params.log_level
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")

    try:
        node = Node(cfg, repo_root=args.repo_root)
        node.start()
    except (ConfigError, OSError) as exc:
        print(f"Error al iniciar: {exc}", file=sys.stderr)
        return 1
    try:
        run_repl(node)
    except KeyboardInterrupt:
        print("\nDeteniendo nodo...")
    finally:
        node.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
