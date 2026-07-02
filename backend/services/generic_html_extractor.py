"""services/generic_html_extractor.py — Extractor agnóstico de categoría.

⏰ LEGACY (F1/F4 del rediseño de ingesta): las primitivas de este módulo se
movieron a `services/specs_ingesta/parse/` y `queries/resolver.py`; el
orquestador (`extract_from_html_generic`, con el filtro de ruido de F4 —
descarta "Package Weight"/"Box Dimensions" que nunca son un spec del equipo)
vive en `services/specs_ingesta/queries/generic.py`. Este archivo re-exporta
los nombres que los tests importan por nombre (`test_generic_extractor.py`,
`test_spec_key_normalization.py`). Se poda en F6 cuando esos tests se migren
a `services.specs_ingesta` directo. Ver docs/PLAN_SPECS_INGESTA.md e issue
#1176.
"""

from __future__ import annotations

from services.specs_ingesta.parse import jsonld as _jsonld_mod
from services.specs_ingesta.parse.jsonld import additional_properties_as_pairs as _jsonld_pairs
from services.specs_ingesta.parse.dom import extract_dom_pairs as _extract_from_dom
from services.specs_ingesta.parse.pares import extract_raw_pairs
from services.specs_ingesta.queries.resolver import normalize_label as _normalize_label, resolve_pairs
from services.specs_ingesta.queries.generic import extract_from_html_generic

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
