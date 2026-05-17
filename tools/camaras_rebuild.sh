#!/usr/bin/env bash
# tools/camaras_rebuild.sh — Reconstruye el dataset completo de cámaras.
#
# Uso: bash tools/camaras_rebuild.sh
# Pre: HTMLs guardados en ~/Desktop/Paginas/Camaras/

set -euo pipefail

cd "$(dirname "$0")/.."

CAMARAS_DIR="$HOME/Desktop/Paginas/Camaras"

echo "▸ Limpiando outputs anteriores"
rm -f docs/camaras_raw.json docs/camaras.json

echo "▸ Parseando HTMLs de B&H"
python3 tools/camaras_parser.py \
  "$CAMARAS_DIR/Sony FX3A Full-Frame Cinema Camera ILME-FX3A B&H Photo Video.html" \
  "$CAMARAS_DIR/Sony a7V Mirrorless Camera ILCE-7M5_B a75 Camera B&H Photo.html" \
  "$CAMARAS_DIR/Sony ZVE1 Mirrorless Camera (ZV-E1 Camera Body Black) B&H Photo Video.html" \
  "$CAMARAS_DIR/Used Canon EOS C200 Cinema Camera (EF-Mount) 2215C002 B&H Photo.html" \
  "$CAMARAS_DIR/RED KOMODO-X DIGITAL CINEMA KOMODO-X 6K Digital Cinema Camera 710-0356.html" \
  "$CAMARAS_DIR/GoPro HERO12 Black CHDHX-121-TH B&H Photo Video.html" \
  > /tmp/camaras_parser.log

echo "  → $(grep -c 'agregado' /tmp/camaras_parser.log) cámaras parseadas"

echo "▸ Aplicando parches manuales"
python3 tools/camaras_patches.py

echo "▸ Normalizando marcas, modelos, IDs"
python3 tools/camaras_normalizar.py

echo ""
echo "Dataset reconstruido."
python3 -c "
import json
with open('docs/camaras.json') as f:
    d = json.load(f)
print(f'  Total: {len(d[\"products\"])} cámaras')
"
