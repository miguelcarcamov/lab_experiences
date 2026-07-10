#!/usr/bin/env python3
"""
Nodo P2P con scaffolding para la actividad del lab TIC.

La plomería (servidor TCP, protocolo, pedir fragmentos, ensamblar) ya está lista.
Los estudiantes completan select_next_piece().

Uso:
  python3 node.py serve --node-id pc01 --port 8800 --pieces ./mis_piezas
  python3 node.py fetch --manifest manifest.json --peers peers.txt --pieces ./mis_piezas --out salida.bin
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Protocolo (JSON, una línea por mensaje)
# ---------------------------------------------------------------------------
# PING          -> PONG {node_id, pieces}
# LIST_PIECES   -> HAVE_PIECES {node_id, pieces}
# REQUEST_PIECE {index} -> PIECE {index, data_b64, sha256} | ERROR


def enviar_mensaje(conn: socket.socket, msg: dict[str, Any]) -> None:
    conn.sendall((json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8"))


def recibir_mensaje(conn: socket.socket) -> dict[str, Any]:
    buf = b""
    while b"\n" not in buf:
        parte = conn.recv(65536)
        if not parte:
            raise ConnectionError("el peer cerró la conexión")
        buf += parte
    linea, _, _ = buf.partition(b"\n")
    return json.loads(linea.decode("utf-8"))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# EJERCICIO DEL ESTUDIANTE
# ---------------------------------------------------------------------------

def select_next_piece(
    peers_info: list[dict[str, Any]],
    my_pieces: set[int],
    total_pieces: int,
) -> tuple[dict[str, Any], int] | None:
    """
    Decide a qué peer pedir el siguiente fragmento.

    Parámetros
    ----------
    peers_info : lista de dicts con al menos:
        - host (str), port (int), node_id (str)
        - pieces (list[int]): índices que ese peer tiene
    my_pieces : conjunto de índices que este nodo ya posee
    total_pieces : cantidad total de fragmentos del archivo

    Retorna
    -------
    (peer, indice) si falta algún fragmento y hay un peer que lo tenga.
    None si ya se completó el archivo (todos los índices en my_pieces).

    Debe implementar una estrategia de selección (secuencial, rarest-first,
    aleatorio, round-robin entre peers, etc.) y documentarla en el reporte.
    """
    # TODO: implementar aquí
    raise NotImplementedError("Complete select_next_piece() antes de usar fetch")

    # --- Pista opcional (el docente puede mostrarla o no) ---
    # Estrategia secuencial trivial:
    # for indice in range(total_pieces):
    #     if indice in my_pieces:
    #         continue
    #     for peer in peers_info:
    #         if indice in peer.get("pieces", []):
    #             return peer, indice
    # return None


# ---------------------------------------------------------------------------
# Piezas locales
# ---------------------------------------------------------------------------

def cargar_piezas(directorio: Path) -> dict[int, bytes]:
    piezas: dict[int, bytes] = {}
    for patron in ("piece_*.bin", "chunk_*.bin"):
        for ruta in sorted(directorio.glob(patron)):
            numero = int(ruta.stem.split("_")[1])
            piezas[numero] = ruta.read_bytes()
    return piezas


def guardar_pieza(directorio: Path, indice: int, datos: bytes) -> None:
    directorio.mkdir(parents=True, exist_ok=True)
    (directorio / f"piece_{indice:03d}.bin").write_bytes(datos)


# ---------------------------------------------------------------------------
# Servidor (ya implementado)
# ---------------------------------------------------------------------------

class Estadisticas:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.mensajes_entrada = 0
        self.mensajes_salida = 0
        self.piezas_enviadas = 0
        self.errores = 0


STATS = Estadisticas()


def manejar_cliente(
    conn: socket.socket,
    node_id: str,
    piezas: dict[int, bytes],
) -> None:
    with STATS.lock:
        STATS.mensajes_entrada += 1
    try:
        req = recibir_mensaje(conn)
        tipo = req.get("type")

        if tipo == "PING":
            resp = {"type": "PONG", "node_id": node_id, "pieces": sorted(piezas.keys())}
        elif tipo == "LIST_PIECES" or tipo == "HAVE_PIECES":
            resp = {"type": "HAVE_PIECES", "node_id": node_id, "pieces": sorted(piezas.keys())}
        elif tipo == "REQUEST_PIECE":
            indice = int(req["index"])
            if indice not in piezas:
                resp = {"type": "ERROR", "error": "not_found", "index": indice}
                with STATS.lock:
                    STATS.errores += 1
            else:
                datos = piezas[indice]
                resp = {
                    "type": "PIECE",
                    "index": indice,
                    "sha256": sha256(datos),
                    "data_b64": base64.b64encode(datos).decode("ascii"),
                }
                with STATS.lock:
                    STATS.piezas_enviadas += 1
        else:
            resp = {"type": "ERROR", "error": "tipo_desconocido", "got": tipo}

        with STATS.lock:
            STATS.mensajes_salida += 1
        enviar_mensaje(conn, resp)
    except Exception as exc:  # actividad introductoria
        try:
            enviar_mensaje(conn, {"type": "ERROR", "error": "excepcion", "detail": str(exc)})
        except OSError:
            pass
    finally:
        conn.close()


def cmd_serve(args: argparse.Namespace) -> int:
    piezas = cargar_piezas(args.pieces)
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((args.bind, args.port))
    servidor.listen(32)
    print(
        f"[serve] nodo={args.node_id} puerto={args.port} "
        f"piezas_locales={sorted(piezas.keys())}",
        flush=True,
    )

    def reporter() -> None:
        while True:
            time.sleep(20)
            with STATS.lock:
                print(
                    f"[stats] in={STATS.mensajes_entrada} out={STATS.mensajes_salida} "
                    f"enviadas={STATS.piezas_enviadas} errores={STATS.errores}",
                    flush=True,
                )

    if args.stats:
        threading.Thread(target=reporter, daemon=True).start()

    try:
        while True:
            conn, addr = servidor.accept()
            threading.Thread(
                target=manejar_cliente,
                args=(conn, args.node_id, piezas),
                daemon=True,
            ).start()
    except KeyboardInterrupt:
        print("\n[serve] detenido.", flush=True)
        return 0


# ---------------------------------------------------------------------------
# Cliente (usa select_next_piece del estudiante)
# ---------------------------------------------------------------------------

def consultar_piezas(host: str, port: int, timeout: float = 3.0) -> dict[str, Any]:
    with socket.create_connection((host, port), timeout=timeout) as conn:
        enviar_mensaje(conn, {"type": "LIST_PIECES"})
        return recibir_mensaje(conn)


def pedir_pieza(host: str, port: int, indice: int, timeout: float = 3.0) -> bytes:
    with socket.create_connection((host, port), timeout=timeout) as conn:
        enviar_mensaje(conn, {"type": "REQUEST_PIECE", "index": indice})
        resp = recibir_mensaje(conn)
    if resp.get("type") != "PIECE":
        raise RuntimeError(f"respuesta inesperada: {resp}")
    datos = base64.b64decode(resp["data_b64"].encode("ascii"))
    if sha256(datos) != resp.get("sha256"):
        raise ValueError(f"hash incorrecto en pieza {indice}")
    return datos


def cargar_peers(ruta: Path) -> list[dict[str, Any]]:
    peers: list[dict[str, Any]] = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        partes = linea.split(":")
        if len(partes) < 2:
            continue
        peer: dict[str, Any] = {
            "host": partes[0],
            "port": int(partes[1]),
            "node_id": partes[2] if len(partes) > 2 else partes[0],
            "pieces": [],
        }
        peers.append(peer)
    return peers


def actualizar_peers_info(peers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vivos: list[dict[str, Any]] = []
    for peer in peers:
        try:
            resp = consultar_piezas(peer["host"], peer["port"])
            peer = dict(peer)
            peer["pieces"] = resp.get("pieces", [])
            peer["node_id"] = resp.get("node_id", peer["node_id"])
            vivos.append(peer)
        except OSError as exc:
            print(f"[fetch] peer caído o inalcanzable {peer['host']}:{peer['port']} ({exc})", flush=True)
    return vivos


def cmd_fetch(args: argparse.Namespace) -> int:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    total = int(manifest["total_pieces"])
    hash_esperado = manifest["sha256"]

    piezas_locales = cargar_piezas(args.pieces)
    my_pieces: set[int] = set(piezas_locales.keys())
    peers = cargar_peers(args.peers)

    mensajes = 0
    t0 = time.perf_counter()

    while len(my_pieces) < total:
        peers_info = actualizar_peers_info(peers)
        mensajes += len(peers)

        eleccion = select_next_piece(peers_info, my_pieces, total)
        if eleccion is None:
            if len(my_pieces) >= total:
                break
            print("Error: select_next_piece devolvió None pero faltan piezas.", file=sys.stderr)
            return 1

        peer, indice = eleccion
        if indice in my_pieces:
            print(f"[fetch] advertencia: pieza {indice} ya local; revise su estrategia.", flush=True)
            continue

        try:
            datos = pedir_pieza(peer["host"], peer["port"], indice)
            mensajes += 1
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"[fetch] fallo al pedir pieza {indice} a {peer['node_id']}: {exc}", flush=True)
            continue

        guardar_pieza(args.pieces, indice, datos)
        piezas_locales[indice] = datos
        my_pieces.add(indice)
        print(f"[fetch] pieza {indice} desde {peer['node_id']} ({peer['host']})", flush=True)

    ensamblado = b"".join(piezas_locales[i] for i in range(total))
    if sha256(ensamblado) != hash_esperado:
        print("Error: hash del archivo ensamblado no coincide con manifest.", file=sys.stderr)
        return 1

    args.out.write_bytes(ensamblado)
    elapsed = time.perf_counter() - t0
    print(
        f"\n[fetch] OK -> {args.out} ({len(ensamblado)} bytes) | "
        f"tiempo={elapsed:.2f}s | mensajes~={mensajes}",
        flush=True,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Nodo P2P (scaffolding actividad)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve", help="Servir piezas locales")
    p_serve.add_argument("--node-id", required=True)
    p_serve.add_argument("--bind", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8800)
    p_serve.add_argument("--pieces", type=Path, required=True)
    p_serve.add_argument("--stats", action="store_true", help="Imprimir estadísticas periódicas")
    p_serve.set_defaults(func=cmd_serve)

    p_fetch = sub.add_parser("fetch", help="Reconstruir archivo (usa select_next_piece)")
    p_fetch.add_argument("--manifest", type=Path, required=True)
    p_fetch.add_argument("--peers", type=Path, required=True)
    p_fetch.add_argument("--pieces", type=Path, required=True, help="Directorio de piezas locales")
    p_fetch.add_argument("--out", type=Path, required=True)
    p_fetch.set_defaults(func=cmd_fetch)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
