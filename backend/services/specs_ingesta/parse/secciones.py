"""parse/secciones.py — Mergea el additionalProperty del JSON-LD (autoritativo)
dentro del shape `secciones` (dict[str, list[{label,value}]]) que producen
los parsers bespoke de B&H (`parsers/base.py::BHSpecsParser`).

Antes (F4): este merge estaba copy-pasteado 4 veces con criterio DISTINTO
cada vez — equipo_html_extractor.py (3 copias idénticas: JSON-LD siempre
primero) y luces_html_extractor.py (1 copia: dedupe, solo agrega lo que el
DOM no tenía).

Gotcha (probado, no supuesto — ver docs/PLAN_SPECS_INGESTA.md F4): el
criterio de LUCES (dedupe) se probó primero acá por "más seguro", pero
contra las 54 páginas reales perdía datos en 111 casos — JSON-LD suele
traer el valor COMPLETO (ej. "Manual\\nPush Auto\\nAuto", un array
serializado) mientras el DOM trae uno más corto/resumido para el MISMO
label (ej. solo "Manual"); si el label ya existía en DOM, el dedupe
descartaba la versión rica de JSON-LD y `_find_value` (primer match)
terminaba devolviendo la más pobre. Gana el criterio de EQUIPO (probado
correcto, y más simple): JSON-LD siempre se antepone primero — como
`_find_value` devuelve el PRIMER match, JSON-LD gana por orden de
iteración cuando el label se repite en ambas fuentes."""

from __future__ import annotations

from .garbage import is_garbage
from . import jsonld as _jsonld_mod


def merge_jsonld_into_secciones(secciones: dict, product: dict) -> dict:
    """secciones (de BHSpecsParser) + product (de jsonld.jsonld_product) →
    secciones con una sección "Specs (JSON-LD)" antepuesta PRIMERO — JSON-LD
    es la fuente más rica/autoritativa, y como `_find_value` devuelve el
    primer match, ponerla primero le da precedencia sin tener que resolver
    conflictos explícitamente."""
    props = _jsonld_mod.additional_properties_as_dict(product)
    if not props:
        return secciones

    items = []
    for name, value in props.items():
        if isinstance(value, list):
            clean = [str(v) for v in value if not is_garbage(str(v))]
            if clean:
                items.append({"label": name, "value": "\n".join(clean)})
        elif value and not is_garbage(str(value)):
            items.append({"label": name, "value": str(value)})

    if not items:
        return secciones
    return {"Specs (JSON-LD)": items, **secciones}
