#!/usr/bin/env bash
# tools/iluminacion_rebuild.sh — Reconstruye el dataset completo de luces.
#
# Uso: bash tools/iluminacion_rebuild.sh
# Pre: HTMLs guardados en ~/Desktop/Paginas/Luces/{Data Set,Inventario}/
#
# Pasos:
#   1. Limpia outputs
#   2. Corre parser sobre todos los HTMLs de B&H
#   3. Aplica parches manuales (ARRI 650 Plus, Mole 2000W, amaran 300c temp)
#   4. Normaliza marcas / modelos / IDs / extras

set -euo pipefail

cd "$(dirname "$0")/.."

PAGINAS="$HOME/Desktop/Paginas/Luces"
DATASET="$PAGINAS/Data Set"
INVENTARIO="$PAGINAS/Inventario"

echo "▸ Limpiando outputs anteriores"
rm -f docs/iluminacion_raw.json docs/iluminacion.json

echo "▸ Parseando HTMLs de B&H"
python3 tools/iluminacion_parser.py \
  "$DATASET/amaran F21x 2x1 Bi-Color LED Flexible Mat (V-Mount) AP20232A14.html" \
  "$DATASET/Godox RGB Mini Creative M1 On-Camera Video LED Light (Gray) M1.html" \
  "$DATASET/Nanlite FC500B Bi-Color LED Spotlight FC500B B&H Photo Video.html" \
  "$DATASET/amaran Ray 360c RGB LED Monolight MP00000191 B&H Photo Video.html" \
  "$DATASET/Aputure NOVA II 2x1 Tunable Color LED Light Panel AP0400040J B&H.html" \
  "$DATASET/Mole-Richardson JuniorLED 200W 8_ Fresnel with DMX 8941-50REV.html" \
  "$INVENTARIO/Godox TL60 RGB LED Tube Light (2.5') TL60 B&H Photo Video.html" \
  "$INVENTARIO/Aputure Accent B7c LED RGBWW Light APC0146A7B B&H Photo Video.html" \
  "$INVENTARIO/Godox VL150 LED Video Light VL150 B&H Photo Video.html" \
  "$INVENTARIO/Godox VL300II Daylight LED Monolight (320W) VL300II B&H Photo.html" \
  "$INVENTARIO/Nanlite Forza 500 Daylight LED Monolight 12-2026 B&H Photo Video.html" \
  "$INVENTARIO/Nanlite Forza 60 LED Monolight 12-2022 B&H Photo Video.html" \
  "$INVENTARIO/amaran 300c RGB LED Monolight (Gray) AP30011A99 B&H Photo Video.html" \
  "$INVENTARIO/amaran COB 200x S Bi-Color LED Monolight APM022XA99 B&H Photo.html" \
  "$INVENTARIO/Godox V100 Flash for Sony V100S B&H Photo Video.html" \
  > /tmp/parser.log

echo "  → $(grep -c 'agregado' /tmp/parser.log) productos parseados"

echo "▸ Aplicando parches manuales (ARRI 650 Plus, Mole 2000W, amaran 300c)"
python3 tools/iluminacion_patches.py

echo "▸ Normalizando marcas, modelos, IDs, extras"
python3 tools/iluminacion_normalizar.py

echo ""
echo "Dataset reconstruido."
python3 -c "
import json
with open('docs/iluminacion.json') as f:
    d = json.load(f)
print(f'  Total: {len(d[\"products\"])} productos')
"
