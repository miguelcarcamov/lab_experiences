#!/usr/bin/env python3
"""
Descubrimiento simple de nodos P2P (calentamiento, 0--10 min).

Envía PING por TCP a cada entrada de seeds.txt y lista los peers que responden.
No tiene TODO: está listo para usar mientras node.py serve corre en cada máquina.

Uso:
  python3 discover.py --node-id pc01 --seeds-file seeds.txt
  python3 discover.py --node-id pc01 --seeds 192.168.1.10:8800,192.168.1.11:8800
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path

PUERTO_DEFAULT = 8800
TIMEOUT = 2.0


def parsear_seed(texto: str) -> tuple[str, int]:
    """Acepta host, host:puerto o host:puerto:node_id (mismo formato que seeds.txt)."""
    texto = texto.strip()
    partes = texto.split(":")
    if len(partes) >= 2:
        return partes[0].strip(), int(partes[1])
    return texto, PUERTO_DEFAULT


def cargar_seeds(archivo: Path | None, inline: str | None) -> list[tuple[str, int]]:
    seeds: list[tuple[str, int]] = []
    if inline:
        for parte in inline.split(","):
            parte = parte.strip()
            if parte:
                seeds.append(parsear_seed(parte))
    if archivo:
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#"):
                seeds.append(parsear_seed(linea))
    # eliminar duplicados preservando orden
    vistos: set[tuple[str, int]] = set()
    unicos: list[tuple[str, int]] = []
    for s in seeds:
        if s not in vistos:
            vistos.add(s)
            unicos.append(s)
    return unicos


def ping_peer(host: str, port: int, timeout: float) -> dict | None:
    try:
        with socket.create_connection((host, port), timeout=timeout) as conn:
            conn.sendall(b'{"type":"PING"}\n')
            buf = b""
            while b"\n" not in buf:
                parte = conn.recv(4096)
                if not parte:
                    return None
                buf += parte
            linea, _, _ = buf.partition(b"\n")
            return json.loads(linea.decode("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Descubrimiento TCP de nodos P2P")
    parser.add_argument("--node-id", required=True, help="ID de este nodo (para el reporte)")
    parser.add_argument("--seeds", help="Lista host:puerto separada por comas")
    parser.add_argument("--seeds-file", type=Path, help="Archivo con un seed por línea")
    parser.add_argument("--timeout", type=float, default=TIMEOUT)
    args = parser.parse_args()

    seeds = cargar_seeds(args.seeds_file, args.seeds)
    if not seeds:
        print("Error: indique --seeds o --seeds-file.", file=sys.stderr)
        return 1

    print(f"=== Descubrimiento desde '{args.node_id}' ===\n")
    print(f"{'Host:puerto':<22} {'Nodo':<12} {'Piezas locales'}")
    print("-" * 55)

    alcanzables = 0
    for host, port in seeds:
        resp = ping_peer(host, port, args.timeout)
        if resp and resp.get("type") == "PONG":
            piezas = resp.get("pieces", [])
            print(f"{host}:{port:<14} {resp.get('node_id', '?'):<12} {piezas}")
            alcanzables += 1
            print(f"  arista para dibujar: {args.node_id} --- {resp.get('node_id', host)}")
        else:
            print(f"{host}:{port:<14} {'(sin respuesta)':<12} -")

    print(f"\nPeers alcanzables: {alcanzables} / {len(seeds)}")
    if alcanzables < 2:
        print("Aviso: se esperan al menos 2 peers; revise que node.py serve esté activo.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
