#!/usr/bin/env python3
"""
tools/camaras_patches.py — Parches manuales para cámaras que el parser no
puede procesar correctamente (HTMLs incompletos, sites no-B&H, etc.).

Por ahora vacío — las 6 cámaras del inventario inicial vienen de B&H y se
parsean OK. Cuando aparezca un edge case (cámara de manufacturer site, HTML
con bot-detection challenge, etc.), agregar parches acá.

Mismo patrón que tools/iluminacion_patches.py.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
CURADO_PATH = ROOT / "docs" / "camaras.json"
RAW_PATH = ROOT / "docs" / "camaras_raw.json"


def apply_patches():
    """Aplica overrides manuales. Hoy: ninguno necesario."""
    with open(CURADO_PATH) as f:
        curado = json.load(f)
    with open(RAW_PATH) as f:
        raw = json.load(f)

    # Acá van los overrides cuando hagan falta. Ej:
    # curado["products"]["arri_alexa_mini_lf"] = {...datos manuales...}

    with open(CURADO_PATH, "w") as f:
        json.dump(curado, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(RAW_PATH, "w") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print("  (Sin parches manuales — todas las cámaras vienen de B&H y parsean OK)")


if __name__ == "__main__":
    apply_patches()
