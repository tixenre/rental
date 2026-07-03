"""parse/jsonld.py — Parseo de JSON-LD (schema.org Product) de una página de producto.

Antes: el regex + json.loads del bloque JSON-LD estaba copy-pasteado en
generic_html_extractor.py, luces_html_extractor.py y equipo_html_extractor.py
(3 implementaciones idénticas, más 3-6 re-parseos del MISMO html dentro de un
solo request, uno por cada campo — imagen/url/marca/props). Acá se parsea
UNA vez (`jsonld_product`) y todo lo demás se deriva del dict ya parseado.
"""

from __future__ import annotations

import html as html_lib
import json
import re

_BLOCK_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)


def _unescape(v):
    if isinstance(v, str):
        return html_lib.unescape(v.replace("\xa0", " "))
    return v


def jsonld_product(html_content: str) -> dict:
    """Devuelve el primer bloque JSON-LD `@type: Product` como dict, o {} si no hay."""
    for block in _BLOCK_RE.findall(html_content):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            return data
    return {}


def image(product: dict) -> str | None:
    img = product.get("image")
    if isinstance(img, list) and img:
        return img[0]
    if isinstance(img, str):
        return img
    return None


def url(product: dict) -> str | None:
    u = product.get("url")
    return u if isinstance(u, str) else None


def brand_name(product: dict) -> str:
    brand = product.get("brand")
    if isinstance(brand, dict):
        return brand.get("name") or ""
    if isinstance(brand, str):
        return brand
    return ""


def additional_properties_as_pairs(product: dict) -> list[dict[str, str]]:
    """[{label, value}], valores siempre string, primera ocurrencia de cada label gana.

    Forma que consume `pares.py` (mezcla con los pares del DOM en una sola lista)."""
    ap = product.get("additionalProperty", {})
    props = ap.get("value", []) if isinstance(ap, dict) else (ap if isinstance(ap, list) else [])
    pairs: list[dict[str, str]] = []
    seen: set[str] = set()
    for pv in props:
        if not isinstance(pv, dict):
            continue
        name = pv.get("name")
        value = pv.get("value")
        if not name or name in seen:
            continue
        seen.add(name)
        if isinstance(value, list):
            val_str = ", ".join(str(_unescape(str(v))) for v in value if str(v).strip())
        elif value is not None:
            val_str = str(_unescape(str(value)))
        else:
            val_str = ""
        if val_str.strip():
            pairs.append({"label": name, "value": val_str.strip()})
    return pairs


def additional_properties_as_dict(product: dict) -> dict:
    """{label: value}, valores preservan su tipo original (list/str/etc).

    Forma que consumen los parsers bespoke (equipo/luces) para mergear con
    las `secciones` extraídas del DOM — a diferencia de la forma en pares,
    acá una lista de valores se necesita como lista real, no aplanada."""
    ap = product.get("additionalProperty", {})
    props = ap.get("value", []) if isinstance(ap, dict) else (ap if isinstance(ap, list) else [])
    result: dict = {}
    for pv in props:
        if not isinstance(pv, dict):
            continue
        name = pv.get("name")
        value = pv.get("value")
        if not name or name in result:
            continue
        if isinstance(value, list):
            value = [_unescape(x) for x in value]
        else:
            value = _unescape(value)
        result[name] = value
    return result
