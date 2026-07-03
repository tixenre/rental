"""parse/pares.py — Extrae TODOS los pares {label, value} de un HTML de producto.

Fuente primaria: JSON-LD additionalProperty. Fuente secundaria: tablas/dl del
DOM (complementa lo que JSON-LD no tiene). Primera aparición de cada label
gana. Movido verbatim de generic_html_extractor.py::extract_raw_pairs — es
el core canónico que `equipo`/`luces` no usaban, cada uno con su propio
merge JSON-LD+DOM inline (eso se consolida en F4, no acá)."""

from __future__ import annotations

from . import dom, jsonld


def extract_raw_pairs(html_content: str) -> list[dict[str, str]]:
    """Extrae TODOS los pares {label, value} del HTML.

    Fuente primaria: JSON-LD additionalProperty.
    Fuente secundaria: tablas y dl del DOM (complementa lo que JSON-LD no tiene).
    Primera aparición de cada label gana.
    """
    product = jsonld.jsonld_product(html_content)
    primary = jsonld.additional_properties_as_pairs(product)
    seen = {p["label"] for p in primary}

    secondary = [p for p in dom.extract_dom_pairs(html_content) if p["label"] not in seen]

    return primary + secondary
