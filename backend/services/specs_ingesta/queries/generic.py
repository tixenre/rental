"""queries/generic.py — Extractor agnóstico de categoría (fallback cuando no
hay parser bespoke, o la detección no reconoció la categoría).

Movido de generic_html_extractor.py::extract_from_html_generic (F4 del
rediseño de ingesta) — la lógica de extracción (parse/pares.py,
queries/resolver.py) ya se había movido en F1; acá se mueve el ÚLTIMO
orquestador que faltaba, y se suma el filtro de ruido (maximizar el
genérico, B0 encontró 2 casos reales).

Ruido filtrado (labels de B&H que nunca son un spec del equipo, siempre de
shipping/packaging): "Package Weight", "Box Dimensions (LxWxH)". Llegan acá
como pares SIN MATCH (provisional key, ej. "package_weight") — el camino
genérico no pasa por las secciones data-selenium de BHSpecsParser (eso es
`parsers/base.py`, category-specific), usa `parse/pares.py` (JSON-LD +
tablas DOM genéricas, sin agrupar por sección) — así que el filtro es por
label normalizado, no por nombre de sección.

Gotcha (verificado, no resuelto acá): el caso "RED KOMODO Production Pack"
de B0 tenía ~30 specs de ruido MÁS ALLÁ de package_weight/box_dimensions —
son specs de los ACCESORIOS incluidos en el bundle (tarjeta SD, filtro,
kit de montaje), que la página de B&H mezcla en el mismo JSON-LD/DOM que
la cámara. Un filtro de labels conocidos no alcanza para esto — la causa
real es que la detección de categoría falla para ese título ("KOMODO 6K
Camera Production Pack" no matchea el regex de "cinema camera") y cae al
genérico en vez del parser de cámaras (que solo extrae specs conocidos de
cámara, no "todo lo que haya"). Se ataca en F5 (maximizar detección)."""

from __future__ import annotations

import re

from services.nombre_builder import compute_keywords
from services.specs_ingesta.parse import jsonld as _jsonld_mod
from services.specs_ingesta.parse.pares import extract_raw_pairs
from services.specs_ingesta.queries.resolver import normalize_label, resolve_pairs

_NOISE_LABELS = frozenset({
    normalize_label(lbl) for lbl in (
        "Package Weight",
        "Box Dimensions (LxWxH)",
        "Box Dimensions",
        "Shipping Weight",
    )
})


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
       se muestran como "sin template" en el form admin — SALVO que el
       label esté en `_NOISE_LABELS` (shipping/packaging, nunca un spec).

    Compatible con el contrato AutocompletarResult.
    """
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else ""

    product = _jsonld_mod.jsonld_product(html_content)
    image = _jsonld_mod.image(product)
    url = _jsonld_mod.url(product) or ""
    marca = _jsonld_mod.brand_name(product)
    if not marca:
        # Fallback heurístico: primera palabra del título
        marca = title.split()[0] if title else ""
    modelo = title

    raw_pairs = extract_raw_pairs(html_content)
    matched, unmatched = resolve_pairs(raw_pairs, categoria_hint)
    unmatched = [p for p in unmatched if normalize_label(p["label"]) not in _NOISE_LABELS]

    # Unmatched: generamos un spec_key provisional del label normalizado para
    # que el frontend pueda mostrar el badge "sin template" (no descartamos nada
    # salvo ruido conocido de shipping/packaging).
    specs: list[dict] = list(matched)
    for pair in unmatched:
        provisional_key = re.sub(r"[^a-z0-9]+", "_", pair["label"].lower()).strip("_") or "unknown"
        specs.append({
            "spec_key": provisional_key,
            "label": pair["label"],
            "value": pair["value"],
        })

    try:
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
        "unmatched": unmatched,  # #1203: mismo unmatched que ya arma specs con key provisional
    }
