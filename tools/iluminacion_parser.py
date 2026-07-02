#!/usr/bin/env python3
"""
tools/iluminacion_parser.py — CLI de dataset para Iluminación.

⏰ LEGACY-ADYACENTE (F3 del rediseño de ingesta): la lógica de mapeo
(BHSpecsParser, map_luz_specs, map_luz_extras, y helpers) se movió a
backend/services/specs_ingesta/parsers/{base,iluminacion}.py — es la fuente
única ahora, usada tanto en vivo (admin) como acá. Este archivo conserva
SOLO lo que sigue siendo suyo: el CLI + I/O de docs/iluminacion*.json
(parse_html/main/load_*/save_*), que ningún código en vivo usa.

Uso:
    python tools/iluminacion_parser.py ~/Desktop/paginas/*.html
    python tools/iluminacion_parser.py ~/Desktop/paginas/amaran*.html

Qué hace:
  1. Parsea los HTMLs (guardados con Cmd+S desde B&H /specs) y extrae los pares
     label/value usando los atributos data-selenium del DOM.
  2. Guarda el raw (secciones B&H originales) en docs/iluminacion_raw.json.
  3. Mapea a los spec_keys del proyecto (Iluminación) y guarda el curado en
     docs/iluminacion.json.

Idempotente: si un producto (por id) ya existe en el JSON no lo pisa.
Si se quiere re-procesar un producto, borrar su entrada primero.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

# ── Rutas de output ──────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
RELEVAMIENTO_PATH = ROOT / "docs" / "iluminacion_raw.json"
CURADO_PATH = ROOT / "docs" / "iluminacion.json"

# Import de la lógica de mapeo real (backend/services/specs_ingesta/parsers/) —
# único lugar donde vive. Ver docs/PLAN_SPECS_INGESTA.md.
_BACKEND_DIR = ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from services.specs_ingesta.parsers.base import (  # noqa: E402
    BHSpecsParser,
    _clean_title,
    _extract_id,
    _extract_brand,
    _extract_modelo,
)
from services.specs_ingesta.parsers.iluminacion import (  # noqa: E402
    _extract_subtipo,
    _parse_potencia,
    _parse_lumens,
    _parse_lux_at_1m,
    _parse_temperatura,
    map_luz_specs,
    map_luz_extras,
)

# _parse_potencia/_parse_lumens/_parse_lux_at_1m/_parse_temperatura/
# map_luz_extras no los llama nada de este archivo directo — quedan
# re-exportados para backend/tests/test_luz_extraccion_6b.py (los importa
# por nombre) y como helper de debugging (map_luz_extras).
__all__ = [
    "BHSpecsParser", "_clean_title", "_extract_id", "_extract_brand", "_extract_modelo",
    "_extract_subtipo", "_parse_potencia", "_parse_lumens", "_parse_lux_at_1m", "_parse_temperatura",
    "map_luz_specs", "map_luz_extras",
    "parse_html", "load_relevamiento", "save_relevamiento", "load_curado", "save_curado", "main",
]


def parse_html(path: Path) -> dict:
    """Parsea un .html de B&H y devuelve el dict raw del producto."""
    content = path.read_text(encoding="utf-8", errors="replace")

    # Extraer título con regex (más robusto que acumular en el parser)
    title_m = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else path.stem
    title = _clean_title(title)

    parser = BHSpecsParser()
    parser.feed(content)

    prod_id = _extract_id(title)
    brand = _extract_brand(title)
    modelo = _extract_modelo(title)
    subtipo = _extract_subtipo(parser.secciones)

    return {
        "id": prod_id,
        "categoria_raiz": "Iluminación",
        "subtipo": subtipo,
        "marca": brand,
        "modelo": modelo,
        "url_source": parser.url or "",
        "status_bh": "Desconocido",
        "fuente": f"html guardado manual ({date.today().isoformat()})",
        "secciones": parser.secciones,
    }


# ── Persistencia ─────────────────────────────────────────────────────────────

_RELEVAMIENTO_META = {
    "version": "1.0",
    "descripcion": (
        "Dataset crudo de specs reales de B&H Photo capturadas por html guardado manual. "
        "Cada producto guarda: categoría, marca, modelo, secciones de B&H, y pares "
        "(label, value) tal cual aparecen. Se usa para análisis del catálogo normalizado."
    ),
    "metodo_captura": "HTML guardado manualmente (Cmd+S → Webpage Complete) desde B&H /specs",
    "uso": (
        "Cuando haya 5-10 productos por categoría, sintetizar para refinar catálogo: "
        "detectar specs nuevas, calibrar enum_options, identificar compuestos que "
        "necesitan parser o tabla."
    ),
    "convencion": {
        "secciones": (
            "B&H usa estas secciones por categoría: Key Specs / Light Fixture / "
            "Connectivity / Power & I/O / Mounting / General / Packaging Info"
        ),
        "values_compuestos": (
            "Cuando un value tiene formato 'X / Y (descripcion)', se preserva tal cual."
        ),
        "categoria_inferida": "Inferida del Item Type + nombre del producto",
    },
}


def load_relevamiento() -> dict:
    if RELEVAMIENTO_PATH.exists():
        return json.loads(RELEVAMIENTO_PATH.read_text(encoding="utf-8"))
    return {"_meta": _RELEVAMIENTO_META, "products": [], "_analisis_pendiente": []}


def save_relevamiento(data: dict):
    RELEVAMIENTO_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_curado() -> dict:
    if CURADO_PATH.exists():
        return json.loads(CURADO_PATH.read_text(encoding="utf-8"))
    return {"_meta": {"descripcion": "Specs curadas mapeadas a spec_keys del proyecto."}, "products": {}}


def save_curado(data: dict):
    CURADO_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ── Main ─────────────────────────────────────────────────────────────────────


def main(html_paths: list[Path]):
    relevamiento = load_relevamiento()
    curado = load_curado()

    existing_ids = {p["id"] for p in relevamiento["products"]}

    added_raw = 0
    added_curado = 0
    skipped = 0

    for path in html_paths:
        if not path.exists():
            print(f"  WARN: no existe: {path}")
            continue

        print(f"Procesando: {path.name}")
        raw = parse_html(path)
        prod_id = raw["id"]

        # Raw: append si no existe
        if prod_id in existing_ids:
            print(f"  → raw ya existe ({prod_id}), skip")
            skipped += 1
        else:
            relevamiento["products"].append(raw)
            existing_ids.add(prod_id)
            added_raw += 1
            print(f"  + raw agregado ({prod_id})")

        # Curado: siempre regenerar (para reflectar el mapper actualizado).
        # `extras` removido del output: no se persistía a DB. La función
        # `map_luz_extras` queda en el módulo como helper de debugging.
        specs = map_luz_specs(raw["secciones"], title=raw["modelo"])
        curado["products"][prod_id] = {
            "marca": raw["marca"],
            "modelo": raw["modelo"],
            "url_source": raw.get("url_source", ""),
            "specs": specs,
            "ficha": raw["secciones"],  # secciones B&H completas (referencia)
        }
        added_curado += 1
        print(f"  + curado: {specs}")

    save_relevamiento(relevamiento)
    save_curado(curado)

    print(f"\nListo. Raw nuevos: {added_raw} | Curado: {added_curado} | Skipped: {skipped}")
    print(f"  → {RELEVAMIENTO_PATH.relative_to(ROOT)}")
    print(f"  → {CURADO_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tools/iluminacion_parser.py <archivo.html> [archivo2.html ...]")
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        paths.extend(Path(arg).parent.glob(Path(arg).name) if "*" in arg else [Path(arg)])

    main(paths)
