"""services/generic_html_extractor.py — Extractor agnóstico de categoría.

⏰ LEGACY (F1 del rediseño de ingesta): las primitivas de este módulo se
movieron a `services/specs_ingesta/parse/` y `queries/resolver.py` — este
archivo re-exporta los nombres que los tests importan por nombre
(`test_generic_extractor.py`, `test_spec_key_normalization.py`). Se poda
en F6 cuando esos tests se migren a `services.specs_ingesta` directo. Ver
docs/PLAN_SPECS_INGESTA.md e issue #1176.

Para categorías SIN parser bespoke (Modificadores, Cables, Audio, etc.),
extrae TODOS los pares {label: value} del HTML y los resuelve contra el
registry de specs vía aliases. Lo que no resuelve → "sin template" visible
en el form admin (cero descartes silenciosos).

Punto de entrada:
    extract_from_html_generic(html_content, categoria_hint=None) -> dict
"""

from __future__ import annotations

import re

from services.specs_ingesta.parse import jsonld as _jsonld_mod
from services.specs_ingesta.parse.jsonld import additional_properties_as_pairs as _jsonld_pairs
from services.specs_ingesta.parse.dom import extract_dom_pairs as _extract_from_dom
from services.specs_ingesta.parse.pares import extract_raw_pairs
from services.specs_ingesta.queries.resolver import normalize_label as _normalize_label, resolve_pairs

__all__ = [
    "_extract_from_jsonld",
    "_extract_from_dom",
    "extract_raw_pairs",
    "resolve_pairs",
    "extract_from_html_generic",
    "_normalize_label",
]


def _extract_from_jsonld(html_content: str) -> list[dict[str, str]]:
    """⏰ LEGACY shim — usar services.specs_ingesta.parse.jsonld directo en código nuevo."""
    return _jsonld_pairs(_jsonld_mod.jsonld_product(html_content))


# ── Helpers JSON-LD (imagen, URL, título) ─────────────────────────────────────

def _jsonld_image(html_content: str) -> str | None:
    return _jsonld_mod.image(_jsonld_mod.jsonld_product(html_content))


def _jsonld_url(html_content: str) -> str | None:
    return _jsonld_mod.url(_jsonld_mod.jsonld_product(html_content))


def _jsonld_brand_name(html_content: str) -> str:
    return _jsonld_mod.brand_name(_jsonld_mod.jsonld_product(html_content))


# ── Entrada principal ─────────────────────────────────────────────────────────

def extract_from_html_generic(
    html_content: str,
    categoria_hint: str | None = None,
) -> dict:
    """Extrae specs de un HTML sin parser bespoke.

    Flujo:
    1. Extrae pares crudos (JSON-LD + DOM tables).
    2. Resuelve cada label contra el registry de aliases.
    3. Matched → specs con spec_key + valor coercionado.
    4. Unmatched → specs con spec_key provisional (label normalizado),
       se muestran como "sin template" en el form admin.

    Compatible con el contrato AutocompletarResult.
    """
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else ""

    image = _jsonld_image(html_content)
    url = _jsonld_url(html_content) or ""
    marca = _jsonld_brand_name(html_content)
    if not marca:
        # Fallback heurístico: primera palabra del título
        marca = title.split()[0] if title else ""
    modelo = title

    raw_pairs = extract_raw_pairs(html_content)
    matched, unmatched = resolve_pairs(raw_pairs, categoria_hint)

    # Unmatched: generamos un spec_key provisional del label normalizado para
    # que el frontend pueda mostrar el badge "sin template" (no descartamos nada).
    specs: list[dict] = list(matched)
    for pair in unmatched:
        provisional_key = re.sub(r"[^a-z0-9]+", "_", pair["label"].lower()).strip("_") or "unknown"
        specs.append({
            "spec_key": provisional_key,
            "label": pair["label"],
            "value": pair["value"],
        })

    try:
        from services.nombre_builder import compute_keywords
        matched_specs_dict = {s["spec_key"]: s["value"] for s in matched}
        keywords: list[str] = compute_keywords(matched_specs_dict)
    except Exception:
        keywords = []

    return {
        "marca": marca,
        "modelo": modelo,
        "nombre_normalizado": f"{marca} {modelo}".strip(),
        "descripcion": "",
        "specs": specs,
        "keywords": keywords,
        "foto_url": image or "",
        "foto_candidates": [image] if image else [],
        "peso": None,
        "dimensiones": None,
        "montura": None,
        "formato": None,
        "resolucion": None,
        "alimentacion": None,
        "incluye": [],
        "conectividad": [],
        "compatible_con": [],
        "video_url": None,
        "precio_bh_usd": None,
        "categoria_sugerida": categoria_hint,
        "fuente_url": url,
        "fuente_titulo": title,
        "fuente_foto_url": image,
        "foto_motivo": "JSON-LD Product.image" if image else None,
        "enriquecido_fuente": "html-upload (generic extractor)",
        "bh_url": url,
        "extras": {},
        "fuente": "html-upload",
        "raw_secciones": {},
    }
