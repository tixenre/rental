#!/usr/bin/env bash
# tools/lentes_rebuild.sh — Reconstruye los datasets de lentes + accesorios.
#
# Uso: bash tools/lentes_rebuild.sh
# Pre: HTMLs guardados en $RAMBLA_HTMLS_DIR/Lentes/
#      (default: ~/Desktop/Paginas/Lentes — override con RAMBLA_HTMLS_DIR)
#
# Salida (2 datasets desde una sola pasada):
#   - docs/lentes.json      → categoría "Lentes"
#   - docs/accesorios.json  → categoría "Adaptadores y Filtros"

set -euo pipefail

cd "$(dirname "$0")/.."

LENTES_DIR="${RAMBLA_HTMLS_DIR:-$HOME/Desktop/Paginas}/Lentes"

echo "▸ Limpiando outputs anteriores"
rm -f docs/lentes_raw.json docs/lentes.json \
      docs/adaptadores_raw.json docs/adaptadores.json \
      docs/filtros_raw.json docs/filtros.json \
      docs/accesorios_raw.json docs/accesorios.json  # legacy, por si quedó

echo "▸ Parseando HTMLs de B&H (lentes + filtros + adaptadores)"
python3 tools/lentes_parser.py \
  "$LENTES_DIR/Sony FE 12-24mm f_2.8 GM Lens SEL1224GM B&H Photo Video.html" \
  "$LENTES_DIR/Sony FE 24-70mm f_2.8 GM II Lens (Sony E) SEL2470GM2 B&H Photo.html" \
  "$LENTES_DIR/Sony FE 70-200mm f_2.8 GM OSS II Lens SEL70200GM2 B&H Photo Video.html" \
  "$LENTES_DIR/Sigma 18-35mm f_1.8 DC HSM Art Lens for Canon EF 210-101 B&H.html" \
  "$LENTES_DIR/Sigma 24-70mm f_2.8 DG OS HSM Art Lens (Canon EF) 576954 B&H.html" \
  "$LENTES_DIR/Sigma 35mm f_1.4 DG HSM Art Lens for Canon EF 340-101 B&H Photo.html" \
  "$LENTES_DIR/Sigma 50mm f_1.4 DG HSM Art Lens for Canon EF 311101 B&H Photo.html" \
  "$LENTES_DIR/Canon EF 70-200mm f_2.8L USM Lens 2569A004 B&H Photo Video.html" \
  "$LENTES_DIR/Venus Optics Laowa 24mm f_14 Probe Lens for Canon EF VE2414C B&H.html" \
  "$LENTES_DIR/Tiffen 82mm Circular Polarizing Filter 82CP B&H Photo Video.html" \
  "$LENTES_DIR/Tiffen Black Pro-Mist Filter (82mm, Grade 1_4) 82BPM14 B&H Photo.html" \
  "$LENTES_DIR/Tiffen Black Pro-Mist Filter (82mm, Grade 1_8) 82BPM18 B&H Photo.html" \
  "$LENTES_DIR/Tiffen Variable ND Filter (82mm, 2 to 8-Stop) 82VND B&H Photo.html" \
  "$LENTES_DIR/Sigma MC-11 Mount Converter_Lens Adapter 89E965 B&H Photo Video.html" \
  "$LENTES_DIR/Canon Mount Adapter EF-EOS R 0.71x 4757C001 B&H Photo Video.html" \
  "$LENTES_DIR/Canon Drop-In Filter Mount Adapter EF-EOS R 3443C002 B&H Photo.html" \
  "$LENTES_DIR/Vello M42 Lens to Sony E-Mount Camera Lens Adapter LA-NEX-M42.html" \
  "$LENTES_DIR/Carl Zeiss Jena Pancolar 50mm f1.8 M42 Lens - RARE THORIUM _ eBay.html" \
  "$LENTES_DIR/MC Carl Zeiss Jena Flektogon lens 2.4_35 mm M42 Screw Mount Canon Sony adaptable _ eBay.html" \
  "$LENTES_DIR/[TOP MINT] Carl Zeiss Jena DDR MC S 135mm f3.5 Portrait Lens M42 from Japan _ eBay.html" \
  > /tmp/lentes_parser.log

echo "  → $(grep -c 'agregado' /tmp/lentes_parser.log) productos parseados desde B&H"
echo "  → $(grep -c 'skip (no es B&H' /tmp/lentes_parser.log) HTMLs eBay (los maneja patches)"

echo "▸ Aplicando parches manuales (Zeiss Pancolar / Flektogon / 135mm Portrait)"
python3 tools/lentes_patches.py

echo "▸ Normalizando marcas, modelos, IDs, extras"
python3 tools/lentes_normalizar.py

echo ""
echo "Datasets reconstruidos."
python3 -c "
import json
for path in ['docs/lentes.json', 'docs/adaptadores.json', 'docs/filtros.json']:
    with open(path) as f:
        d = json.load(f)
    print(f'  {path}: {len(d[\"products\"])} productos')
"
