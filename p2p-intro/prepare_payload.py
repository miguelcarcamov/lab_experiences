#!/usr/bin/env python3
"""
Trocea un archivo y genera manifest.json + carpetas de piezas por nodo.
Lo usa cada grupo de estudiantes al inicio de la actividad.

Uso:
  python3 prepare_payload.py --gen-demo
  python3 prepare_payload.py --input demo.bin --chunk-size 4096 --nodes 4
  python3 prepare_payload.py --input demo.bin --assign plan.csv

plan.csv (opcional): una línea por nodo
  pc01,0,2,5
  pc02,1,3
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import secrets
import sys
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_file(data: bytes, chunk_size: int) -> list[bytes]:
    chunks: list[bytes] = []
    for i in range(0, len(data), chunk_size):
        chunks.append(data[i : i + chunk_size])
    return chunks


def write_manifest(out_dir: Path, filename: str, chunk_size: int, chunks: list[bytes]) -> dict:
    manifest = {
        "filename": filename,
        "chunk_size": chunk_size,
        "total_chunks": len(chunks),
        "sha256": sha256_bytes(b"".join(chunks)),
        "chunks": [
            {"index": i, "size": len(c), "sha256": sha256_bytes(c)}
            for i, c in enumerate(chunks)
        ],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def default_assignment(total_chunks: int, n_nodes: int) -> dict[str, list[int]]:
    nodes = [f"node{i+1:02d}" for i in range(n_nodes)]
    assign: dict[str, list[int]] = {n: [] for n in nodes}
    for idx in range(total_chunks):
        assign[nodes[idx % n_nodes]].append(idx)
    return assign


def load_assignment(path: Path) -> dict[str, list[int]]:
    assign: dict[str, list[int]] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            node = row[0].strip()
            indices = [int(x) for x in row[1:] if x.strip() != ""]
            assign[node] = indices
    return assign


def main() -> int:
    parser = argparse.ArgumentParser(description="Preparar payload troceado para actividad P2P")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("payload"))
    parser.add_argument("--chunk-size", type=int, default=4096)
    parser.add_argument("--nodes", type=int, default=6, help="Si no usa --assign")
    parser.add_argument("--assign", type=Path, help="CSV node,idx,idx,...")
    args = parser.parse_args()

    data = args.input.read_bytes()
    chunks = split_file(data, args.chunk_size)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    all_chunks_dir = args.out_dir / "all_chunks"
    all_chunks_dir.mkdir(exist_ok=True)
    for i, chunk in enumerate(chunks):
        (all_chunks_dir / f"chunk_{i:03d}.bin").write_bytes(chunk)

    manifest = write_manifest(args.out_dir, args.input.name, args.chunk_size, chunks)

    if args.assign:
        assignment = load_assignment(args.assign)
    else:
        assignment = default_assignment(len(chunks), args.nodes)

    for node, indices in assignment.items():
        node_dir = args.out_dir / "nodes" / node
        node_dir.mkdir(parents=True, exist_ok=True)
        for idx in indices:
            src = all_chunks_dir / f"chunk_{idx:03d}.bin"
            dst = node_dir / f"chunk_{idx:03d}.bin"
            dst.write_bytes(src.read_bytes())

    # demo.bin de referencia para verificación docente
    (args.out_dir / "demo_reference.bin").write_bytes(data)

    print(f"Chunks: {len(chunks)} | SHA256: {manifest['sha256']}")
    print(f"Salida: {args.out_dir}")
    print("Asignación:")
    for node, indices in assignment.items():
        print(f"  {node}: {indices}")
    print("\nCopie cada carpeta nodes/<id>/ al nodo correspondiente como ./chunks/")
    return 0


def make_demo_file(path: Path, size: int = 48 * 1024) -> None:
    path.write_bytes(secrets.token_bytes(size))


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--gen-demo":
        out = Path("demo.bin")
        make_demo_file(out)
        print(f"Generado {out} ({out.stat().st_size} bytes)")
        raise SystemExit(0)
    raise SystemExit(main())
