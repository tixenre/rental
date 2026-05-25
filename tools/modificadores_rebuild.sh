#!/usr/bin/env bash
# tools/modificadores_rebuild.sh — Reconstruye el dataset de modificadores
# de luz (softbox / fresnel / spotlight / difusión).
#
# Uso: bash tools/modificadores_rebuild.sh
# Pre: HTMLs guardados en $RAMBLA_HTMLS_DIR/Modificadores_Luz/
#      (default: ~/Desktop/Paginas/Modificadores_Luz — override con RAMBLA_HTMLS_DIR)
#
# Salida:
#   - docs/modificadores.json
#   - docs/modificadores_raw.json
#
# Nota: 1 producto sin HTML B&H ("Reflector Plegable Godox 5 en 1") está
# guardado solo como HTML del fabricante (godoxonline.com). Por ahora se
# saltea; eventualmente puede agregarse via patches o creando un wrapper
# manual con specs curados a mano.

set -euo pipefail

cd "$(dirname "$0")/.."

PAGINAS="${RAMBLA_HTMLS_DIR:-$HOME/Desktop/Paginas}/Modificadores_Luz"

echo "▸ Limpiando outputs anteriores"
rm -f docs/modificadores_raw.json docs/modificadores.json

echo "▸ Parseando HTMLs de B&H"
python3 tools/modificadores_parser.py \
  "$PAGINAS/Angler Quick-Open Deep Parabolic Softbox V2 (48_) QO-DP48-V2 B&H.html" \
  "$PAGINAS/Aputure Quick Dome 60 AA07060383 B&H Photo Video.html" \
  "$PAGINAS/Aputure Quick Dome 90 AA07060382 B&H Photo Video.html" \
  "$PAGINAS/Godox Collapsible Lantern Softbox with Bowens Mount (33.5_).html" \
  "$PAGINAS/Nanlite Fresnel Lens for Forza 300 and 500 FL-20G B&H Photo Video.html" \
  "$PAGINAS/Reflector Plegable Ovalado Godox 5 en 1 150x200cm – GodoxOnline.com.html" \
  "$PAGINAS/amaran Spotlight SE 36° Lens Kit APF0046A32 B&H Photo Video.html" \
  > /tmp/modificadores_parser.log

echo "  → $(grep -c 'curado' /tmp/modificadores_parser.log) productos parseados"
echo "  → $(grep -c 'skip (no es B&H' /tmp/modificadores_parser.log) HTMLs no-B&H salteados"

echo ""
echo "Dataset reconstruido."
python3 -c "
import json
data = json.load(open('docs/modificadores.json'))
print(f'  docs/modificadores.json: {len(data[\"products\"])} productos')
for pid, p in data['products'].items():
    n_specs = len(p['specs'])
    print(f'    {pid:25s} ({n_specs} specs) — {p[\"marca\"]} {p[\"modelo\"][:50]}')
"
