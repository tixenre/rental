#!/usr/bin/env python3
"""
tools/modificadores_parser.py — CLI de dataset para Modificadores de luz.

⏰ LEGACY-ADYACENTE (F3 del rediseño de ingesta): la lógica de mapeo
(map_modificador_specs y sus _parse_* propios) se movió a
backend/services/specs_ingesta/parsers/modificadores.py — es la fuente
única ahora, usada tanto en vivo (admin) como acá. Este archivo conserva
SOLO lo que sigue siendo suyo: el CLI + I/O de docs/modificadores*.json
(parse_html/main/load_json/save_json), que ningún código en vivo usa.

Softbox / spotlight / fresnel / difusión. La carpeta
~/Desktop/Paginas/Modificadores_Luz/ tiene HTMLs de B&H y de fabricante.

Uso:
    python3 tools/modificadores_parser.py ~/Desktop/Paginas/Modificadores_Luz/*.html
"""

import html as html_lib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent

RAW_PATH = ROOT / "docs" / "modificadores_raw.json"
CURADO_PATH = ROOT / "docs" / "modificadores.json"

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
from services.specs_ingesta.parsers.modificadores import map_modificador_specs  # noqa: E402

__all__ = [
    "BHSpecsParser", "_clean_title", "_extract_id", "_extract_brand", "_extract_modelo",
    "map_modificador_specs",
    "parse_html", "load_json", "save_json", "main",
]


def _extract_url_source(html: str) -> str:
    m = re.search(r'<meta\s+property="og:url"\s+content="([^"]+)"', html)
    if m:
        return html_lib.unescape(m.group(1))
    m = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', html)
    return html_lib.unescape(m.group(1)) if m else ""


def _extract_image_url(html: str) -> str:
    m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
    return html_lib.unescape(m.group(1)) if m else ""


def _extract_title(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html)
    return html_lib.unescape(m.group(1)).strip() if m else ""


def _is_bh_html(html: str, url_source: str) -> bool:
    """Heurística: ¿es B&H Photo (no godoxonline / eBay / fabricante)?
    Los HTMLs guardados de B&H tienen 'bhphotovideo.com' en og:image
    aunque a veces no en og:url. Y el title incluye 'B&amp;H'."""
    head = html[:10_000].lower()
    if "bhphotovideo.com" in head:
        return True
    if "bhphoto.com" in head:
        return True
    if "url_source" and "bhphotovideo.com" in url_source.lower():
        return True
    if "b&amp;h photo" in head or "b&h photo" in head:
        return True
    return False


# ─── Pipeline principal ───────────────────────────────────────────────


def parse_html(path: Path) -> dict | None:
    """Parsea un HTML B&H. Devuelve dict con marca/modelo/specs/secciones.
    Retorna None si NO es B&H (otros sitios → manejados por patches)."""
    html_text = path.read_text(encoding="utf-8", errors="ignore")
    url_source = _extract_url_source(html_text)
    if not _is_bh_html(html_text, url_source):
        return None

    raw_title = _extract_title(html_text)
    title = _clean_title(raw_title)
    parser = BHSpecsParser()
    parser.feed(html_text)
    secciones = parser.secciones

    return {
        "id": _extract_id(title),
        "marca": _extract_brand(title),
        "modelo": _extract_modelo(title),
        "url_source": url_source,
        "image_url": _extract_image_url(html_text),
        "status_bh": "OK",
        "fuente": f"B&H HTML guardado ({date.today().isoformat()})",
        "secciones": secciones,
    }


def load_json(path: Path, default: dict) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    return default


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main(html_paths: list[Path]) -> None:
    raw = load_json(RAW_PATH, {"products": []})
    curado = load_json(CURADO_PATH, {"products": {}})

    raw_existing = {p["id"] for p in raw["products"]}
    added_raw = 0
    added_curado = 0
    skipped = 0

    for p in html_paths:
        if not p.exists():
            print(f"  WARN: no existe: {p}")
            continue
        print(f"Procesando: {p.name}")
        result = parse_html(p)
        if result is None:
            print("  → skip (no es B&H — usar patches)")
            skipped += 1
            continue

        prod_id = result["id"]
        title = f"{result['marca']} {result['modelo']}"

        # Raw
        if prod_id in raw_existing:
            print(f"  → raw ya existe ({prod_id}), upsert")
            for i, existing in enumerate(raw["products"]):
                if existing["id"] == prod_id:
                    raw["products"][i] = result
                    break
        else:
            raw["products"].append(result)
            raw_existing.add(prod_id)
            added_raw += 1
            print(f"  + raw agregado ({prod_id})")

        # Curado
        specs = map_modificador_specs(result["secciones"], title=title)
        curado["products"][prod_id] = {
            "marca": result["marca"],
            "modelo": result["modelo"],
            "url_source": result.get("url_source", ""),
            "specs": specs,
            "ficha": result["secciones"],
        }
        added_curado += 1
        print(f"  + curado ({len(specs)} specs): {list(specs.keys())}")

    save_json(RAW_PATH, raw)
    save_json(CURADO_PATH, curado)

    print(f"\nListo. Raw nuevos: {added_raw} | Curado: {added_curado} | Skipped: {skipped}")
    print(f"  → {RAW_PATH.relative_to(ROOT)}")
    print(f"  → {CURADO_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tools/modificadores_parser.py <archivo.html> [archivo2.html ...]")
        sys.exit(1)
    paths = []
    for arg in sys.argv[1:]:
        if "*" in arg:
            paths.extend(Path(arg).parent.glob(Path(arg).name))
        else:
            paths.append(Path(arg))
    main(paths)
