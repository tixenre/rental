"""
services/luces_html_extractor.py — Extrae specs normalizados de un HTML B&H.

Usa el MISMO pipeline que el seed (tools/iluminacion_parser.py +
tools/iluminacion_normalizar.py) para que la calidad sea idéntica a
la del dataset curado.

Punto de entrada principal:
    extract_from_html(html_content: str) -> dict

Devuelve estructura compatible con AutocompletarResult del endpoint
existente (marca, modelo, foto_url, bh_url, specs: [{label, value}]).

El parser que usa lee:
  - JSON-LD structured data (Product.additionalProperty.value) — fuente rica
  - DOM data-selenium attributes — fallback
  - Title del <head> — para marca/modelo
"""

import re
import sys
from pathlib import Path

from services.specs_ingesta.parse import jsonld as _jsonld
from services.specs_ingesta.parse.garbage import is_garbage as _is_garbage
from services.specs_ingesta.parse.serialize import specs_dict_to_array

# Importar el parser core desde tools/ (es código script-style ya probado).
# El seed lo usa idéntico — esto garantiza paridad de calidad.
# ⏰ LEGACY (F3 del rediseño de ingesta): este sys.path.insert se elimina cuando
# los parsers se mudan a services/specs_ingesta/parsers/. Ver issue #1176.
_TOOLS_DIR = Path(__file__).parent.parent.parent / "tools"
sys.path.insert(0, str(_TOOLS_DIR))

# Funciones del parser/normalizador que reusamos
from iluminacion_parser import (  # noqa: E402  type: ignore
    BHSpecsParser,
    _clean_title,
    _extract_brand,
    _extract_modelo,
    map_luz_specs,
    map_luz_extras,
)
from iluminacion_normalizar import (  # noqa: E402  type: ignore
    canon_brand,
    canon_modelo,
    clean_extras,
)


# ── Extractor principal ─────────────────────────────────────────────────────

def extract_from_html(html_content: str) -> dict:
    """
    Parsea un HTML guardado de B&H (u otro site con misma estructura) y
    devuelve specs normalizados.

    Output:
        {
          "marca":      "Aputure",
          "modelo":     "NOVA II 2x1",
          "foto_url":   "https://...",
          "bh_url":     "https://...",
          "specs":      [{"label": "Potencia", "value": "1000W"}, ...],
          "extras":     {tipo: "Panel", cooling: "Fan", ...},
          "fuente":     "html-upload",
        }

    Si no se puede parsear (HTML inválido / sin specs reconocibles), devuelve
    al menos marca/modelo desde <title> y arrays vacíos.
    """
    # 1) Title del <head> para marca/modelo
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    title = _clean_title(title_m.group(1).strip()) if title_m else ""

    marca = canon_brand(_extract_brand(title))
    modelo = canon_modelo(_extract_modelo(title))

    # 2) Parsear el JSON-LD UNA vez (antes: 3 pasadas separadas por url/imagen/props)
    product = _jsonld.jsonld_product(html_content)

    # URL canónica del producto (preferir JSON-LD; fallback al comentario "saved from url")
    url = _jsonld.url(product)
    if not url:
        saved = re.search(r"saved from url=\(\d+\)(https%s://\S+)", html_content)
        if saved:
            url = saved.group(1).strip()

    # 3) Image URL
    image = _jsonld.image(product)

    # 4) Parser DOM + JSON-LD merge → secciones {sec: [{label, value}]}
    parser = BHSpecsParser()
    parser.feed(html_content)
    secciones = dict(parser.secciones)

    # Si tenemos JSON-LD, lo agregamos en una sección "Specs" — más rico que DOM
    jsonld_props = _jsonld.additional_properties_as_dict(product)

    if jsonld_props:
        jsonld_items = []
        for name, value in jsonld_props.items():
            if isinstance(value, list):
                for v in value:
                    if not _is_garbage(str(v)):
                        jsonld_items.append({"label": name, "value": str(v)})
            elif not _is_garbage(str(value)):
                jsonld_items.append({"label": name, "value": str(value)})
        # Lo agregamos como sección si no había nada, o lo mergeamos
        if not secciones:
            secciones = {"Specs": jsonld_items}
        else:
            # Mergear: agregar labels que no estén ya
            existing_labels = {it["label"] for items in secciones.values() if isinstance(items, list) for it in items}
            extra_items = [it for it in jsonld_items if it["label"] not in existing_labels]
            if extra_items:
                secciones.setdefault("Specs (JSON-LD)", []).extend(extra_items)

    # 5) Mapper → specs normalizados
    specs_dict = map_luz_specs(secciones, title=modelo)
    extras_dict = clean_extras(map_luz_extras(secciones, title=modelo))

    # 6) Formato AutocompletarResult: specs como array [{spec_key, label, value}].
    # Serialización delegada en specs_ingesta (fuente única de display, vía
    # spec_render) — antes esta función tenía sus propios sufijos de unidad
    # hardcodeados (K/lux) que no usaban el `unidad` que el registry declara.
    specs_array = specs_dict_to_array(specs_dict, "Iluminación")

    # Ficha extendida: extraer campos compatibles con AutocompletarResult
    peso_raw = specs_dict.get("peso")
    peso_str: str | None = None
    if isinstance(peso_raw, (int, float)):
        peso_str = f"{round(peso_raw/1000, 2)} kg" if peso_raw >= 1000 else f"{int(peso_raw)} g"
    elif isinstance(peso_raw, str) and peso_raw.strip():
        # _parse_peso devuelve "N g" siempre — si >1000, convertir a kg para legibilidad
        m_g = re.match(r"(\d+(?:\.\d+)?)\s*g\s*$", peso_raw)
        if m_g:
            grams = float(m_g.group(1))
            peso_str = f"{round(grams/1000, 2)} kg" if grams >= 1000 else f"{int(grams)} g"
        else:
            peso_str = peso_raw
    dimensiones_str = extras_dict.get("dimensiones")
    if isinstance(dimensiones_str, dict):
        dimensiones_str = dimensiones_str.get("metric") or None
    alimentacion_str = None
    if isinstance(specs_dict.get("alimentacion"), list):
        alimentacion_str = ", ".join(specs_dict["alimentacion"])

    incluye = extras_dict.get("included_accessories") or []
    if not isinstance(incluye, list):
        incluye = [str(incluye)]

    return {
        # Campos canónicos AutocompletarResult
        "marca": marca,
        "modelo": modelo,
        "nombre_normalizado": f"{marca} {modelo}".strip(),
        "descripcion": "",
        "specs": specs_array,
        "keywords": [],
        "foto_url": image or "",
        "foto_candidates": [image] if image else [],
        # Ficha extendida
        "peso": peso_str,
        "dimensiones": dimensiones_str,
        "montura": None,  # no aplica a luces
        "formato": None,
        "resolucion": None,
        "alimentacion": alimentacion_str,
        "incluye": incluye,
        "conectividad": [],
        "compatible_con": [],
        "video_url": None,
        "precio_bh_usd": None,
        "categoria_sugerida": None,
        # Trazabilidad
        "fuente_url": url or "",
        "fuente_titulo": title,
        "fuente_foto_url": image,
        "foto_motivo": "JSON-LD Product.image" if image else None,
        "enriquecido_fuente": "html-upload (iluminacion_parser)",
        # Específicos del HTML extractor (no en AutocompletarResult original pero útiles)
        "bh_url": url or "",
        "extras": extras_dict,
        "fuente": "html-upload",
        "raw_secciones": secciones,
    }
