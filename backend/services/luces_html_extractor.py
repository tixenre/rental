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

import html as html_lib
import json
import re
import sys
from pathlib import Path
from typing import Any

# Importar el parser core desde tools/ (es código script-style ya probado).
# El seed lo usa idéntico — esto garantiza paridad de calidad.
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


# ── JSON-LD extraction (igual al seed) ──────────────────────────────────────

def _jsonld_props(html_content: str) -> dict[str, Any]:
    """Extrae {label: value} desde Product.additionalProperty del JSON-LD."""
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content, re.DOTALL,
    )
    for b in blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError:
            continue
        if not (isinstance(data, dict) and data.get("@type") == "Product"):
            continue
        ap = data.get("additionalProperty", {})
        props_list = ap.get("value", []) if isinstance(ap, dict) else (ap if isinstance(ap, list) else [])
        result: dict[str, Any] = {}
        for pv in props_list:
            if isinstance(pv, dict):
                name = pv.get("name")
                value = pv.get("value")
                if name:
                    if isinstance(value, list):
                        value = [
                            html_lib.unescape(x.replace(" ", " "))
                            if isinstance(x, str) else x
                            for x in value
                        ]
                    elif isinstance(value, str):
                        value = html_lib.unescape(value.replace(" ", " "))
                    result[name] = value
        return result
    return {}


def _jsonld_image(html_content: str) -> str | None:
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content, re.DOTALL,
    )
    for b in blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            img = data.get("image")
            if isinstance(img, list) and img:
                return img[0]
            if isinstance(img, str):
                return img
    return None


def _jsonld_url(html_content: str) -> str | None:
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content, re.DOTALL,
    )
    for b in blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            url = data.get("url")
            if isinstance(url, str):
                return url
    return None


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

    # 2) URL canónica del producto (preferir JSON-LD; fallback al comentario "saved from url")
    url = _jsonld_url(html_content)
    if not url:
        saved = re.search(r"saved from url=\(\d+\)(https%s://\S+)", html_content)
        if saved:
            url = saved.group(1).strip()

    # 3) Image URL
    image = _jsonld_image(html_content)

    # 4) Parser DOM + JSON-LD merge → secciones {sec: [{label, value}]}
    parser = BHSpecsParser()
    parser.feed(html_content)
    secciones = dict(parser.secciones)

    # Si tenemos JSON-LD, lo agregamos en una sección "Specs" — más rico que DOM
    jsonld_props = _jsonld_props(html_content)
    # Filtro de valores basura (mismo criterio que BHSpecsParser DOM)
    _GARBAGE_VALUES = {"1 x", "1x", ":", "—", "-", "N/A", "n/a", ""}
    def _is_garbage(v: str) -> bool:
        v = (v or "").strip()
        return v in _GARBAGE_VALUES or v.lower().startswith("not specified")

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

    # 6) Formato AutocompletarResult: specs como array [{spec_key, label, value}]
    # Label sale del registry (fuente única). Fallback: key.replace("_"," ").title().
    registry_labels: dict[str, str] = {}
    try:
        from services.specs import REGISTRY  # import local: evita ciclos
        cat_reg = REGISTRY.get("Iluminación")
        if cat_reg:
            registry_labels = {s.key: s.label for s in cat_reg.specs}
    except Exception:
        pass

    specs_array = []
    for key, value in specs_dict.items():
        label = registry_labels.get(key) or key.replace("_", " ").title()
        # Serializar valor: bools y listas → string compacto
        if isinstance(value, bool):
            val_str = "Sí" if value else "No"
        elif isinstance(value, list):
            val_str = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            if "min" in value and "max" in value:
                val_str = f"{value['min']}-{value['max']}K" if key == "temperatura_k" else f"{value['min']}-{value['max']}"
            else:
                val_str = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, (int, float)):
            unit = ""
            if key == "consumo_w": unit = " W"
            elif "lumens" in key: unit = " lm"
            elif "lux" in key: unit = " lux"
            val_str = f"{value}{unit}"
        else:
            val_str = str(value)
        specs_array.append({"spec_key": key, "label": label, "value": val_str})

    # Peso lo agregamos como "390 g" (más legible) si está
    if "peso" in specs_dict and isinstance(specs_dict["peso"], (int, float)):
        val = specs_dict["peso"]
        # Ya está agregado arriba como peso. Reemplazar para formatear.
        for s in specs_array:
            if s["label"] == "Peso":
                if val >= 1000:
                    s["value"] = f"{round(val/1000, 2)} kg"
                else:
                    s["value"] = f"{val} g"

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
