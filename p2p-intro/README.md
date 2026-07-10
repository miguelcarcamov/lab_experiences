# P2P intro — Lab TIC DIINF

Enunciado: [`activity_1.pdf`](activity_1.pdf).

Repositorio canónico: [github.com/miguelcarcamov/lab_experiences](https://github.com/miguelcarcamov/lab_experiences)

## Fork (cada grupo)

1. Fork en GitHub → `https://github.com/<tu-usuario>/lab_experiences`
2. `git clone git@github.com:<tu-usuario>/lab_experiences.git`
3. `cd lab_experiences/p2p-intro`
4. Implementar `select_next_piece()` en `node.py` y commitear en `master`.

## Preparar el archivo (grupo)

```bash
python3 prepare_payload.py --gen-demo
python3 prepare_payload.py --input demo.bin --chunk-size 4096 --nodes 4
```

Copiar `payload/nodes/nodeXX/` → `./piezas/` en cada PC. Crear `seeds.txt` y `peers.txt` con IPs del grupo.

## Ejecutar

```bash
python3 node.py serve --node-id pc01 --port 8800 --pieces ./piezas
python3 discover.py --node-id pc01 --seeds-file seeds.txt
python3 node.py fetch --manifest manifest.json --peers peers.txt \
  --pieces ./piezas --out recuperado.bin
```

Ver [`seeds.example.txt`](seeds.example.txt) y [`peers.example.txt`](peers.example.txt).
