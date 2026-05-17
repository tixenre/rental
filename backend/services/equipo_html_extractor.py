"""
services/equipo_html_extractor.py — Dispatcher de extractores HTML por categoría.

Reemplaza al LLM-based autocompletar para equipos: cuando el admin sube un
HTML B&H (o se obtiene rawHtml de Firecrawl), este módulo:

  1. Detecta la categoría del HTML (Cámaras / Lentes / Adaptadores / Filtros /
     Iluminación) por título + JSON-LD.
  2. Llama al parser determinístico correspondiente (mismo código que el seed).
  3. Genera keywords canónicas vía `nombre_builder.compute_keywords()`.
  4. Devuelve estructura `AutocompletarResult` con specs canónicos.

Calidad idéntica al dataset del seed. Sin LLM.

Entrada principal:
    extract_from_html(html_content, categoria_hint=None) -> dict
"""

import html as html_lib
import json
import re
import sys
from pathlib import Path
from typing import Any

# Importar parsers core desde tools/ (mismo código que el seed)
_TOOLS_DIR = Path(__file__).parent.parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

# Importar compute_keywords del nombre_builder
_BACKEND_DIR = Path(__file__).parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
from services.nombre_builder import compute_keywords  # noqa: E402  type: ignore


# ── Detección de categoría ──────────────────────────────────────────────

def _detect_categoria(html_content: str, title: str = "") -> str:
    """Detecta la categoría del HTML basado en título + JSON-LD + heurística.

    Devuelve: "Cámaras" | "Lentes" | "Adaptadores" | "Filtros" | "Iluminación"
              | "Desconocido"
    """
    t = (title or "").lower()
    body_excerpt = html_content[:50_000].lower()  # primeros 50KB

    # Adaptadores: mention explícita
    if re.search(r"\b(lens\s+mount\s+adapter|mount\s+converter|speedbooster|lens\s+adapter)\b", t):
        return "Adaptadores"
    if "lens mount adapter" in body_excerpt[:5000]:
        return "Adaptadores"

    # Filtros
    if re.search(r"\b(filter|polariz|pro-?mist|nd\s+filter|variable\s+nd)\b", t):
        return "Filtros"

    # Cámaras (incluye action cams)
    if re.search(r"\b(cinema\s+camera|mirrorless|dslr|action\s+camera|action\s+cam\b|camera\s+body|camcorder|gopro|insta360)\b", t):
        return "Cámaras"

    # Lentes (después de adaptadores/filtros para evitar falsos positivos)
    if re.search(r"\b(lens|lente)\b", t) and not re.search(r"\b(adapter|filter|hood|cap)\b", t):
        return "Lentes"

    # Iluminación: amplio (LED, light, monolight, flash, tube, panel, fresnel)
    if re.search(r"\b(led|light|monolight|spotlight|flash|tube\s+light|fresnel|softbox|panel)\b", t):
        return "Iluminación"

    return "Desconocido"


# ── JSON-LD helpers (compartidos) ───────────────────────────────────────

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
                if name and name not in result:  # primera ocurrencia gana
                    if isinstance(value, list):
                        value = [
                            html_lib.unescape(x.replace(" ", " "))
                            if isinstance(x, str) else x
                            for x in value
                        ]
                    elif isinstance(value, str):
                        value = html_lib.unescape(value.replace(" ", " "))
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


# ── Adapter común: convierte specs dict → array [{label, value}] ────────

# Labels canónicos por spec_key (en español, lo que se muestra en el form)
_SPEC_LABELS: dict[str, str] = {
    # Cámaras
    "tipo": "Tipo",
    "lens_mount": "Lens mount",
    "formato": "Formato",
    "resolucion_max": "Resolución máxima",
    "fps_max": "FPS máx",
    "megapixels": "Megapixels",
    "codecs": "Codecs",
    "iso_nativo": "ISO nativo",
    "iso_extendido": "ISO extendido",
    "rango_dinamico_stops": "Rango dinámico",
    "estabilizacion": "Estabilización óptica",
    "autofocus": "Autofocus",
    "fast_slow_motion": "Fast/Slow motion",
    "lens_communication": "Comunicación electrónica lente",
    "gps": "GPS",
    "ip_streaming": "IP Streaming",
    "netflix_approved": "Netflix approved",
    "continuous_shooting_fps": "Ráfaga (stills)",
    "max_aperture": "Apertura máxima (fixed-lens)",
    "sensor_crop": "Sensor crop (35mm eq.)",
    "recording_limit_min": "Límite de grabación",
    "peso_g": "Peso",
    # Lentes
    "distancia_focal": "Distancia focal",
    "apertura": "Apertura",
    "diametro_filtro": "Diámetro de filtro",
    "linea": "Línea",
    "angulo_vision": "Ángulo de visión",
    "distancia_minima_m": "Distancia mínima de foco",
    "magnificacion": "Magnificación",
    "hojas_diafragma": "Hojas de diafragma",
    "construccion_optica": "Construcción óptica",
    "dimensiones": "Dimensiones",
    # Adaptadores
    "lens_mount_out": "Lens mount — lado lente",
    "electronica": "Comunicación electrónica",
    "incluye_iris": "Iris incluido",
    # Filtros
    "densidad": "Densidad ND",
    "material": "Material",
    "grade": "Grado",
    # Iluminación
    "potencia_w": "Potencia",
    "lumens": "Lúmenes",
    "lumens_at_5600k": "Lúmenes (5600K)",
    "lumens_at_3200k": "Lúmenes (3200K)",
    "cri": "CRI",
    "tlci": "TLCI",
    "r9": "R9",
    "temperatura_k": "Temperatura color",
    "color_modes": "Modos de color",
    "bicolor": "Bicolor",
    "rgb": "RGB",
    "dimming": "Dimmer",
    "control_inalambrico": "Control inalámbrico",
    "alimentacion": "Alimentación",
    "montaje": "Montaje",
}


def _specs_dict_to_array(specs_dict: dict) -> list[dict]:
    """Convierte {spec_key: value} → [{label, value}] para el form admin."""
    out = []
    for key, value in specs_dict.items():
        label = _SPEC_LABELS.get(key, key)
        if isinstance(value, bool):
            val_str = "Sí" if value else "No"
        elif isinstance(value, list):
            # Rangos de focal/apertura
            if key in ("distancia_focal", "apertura", "angulo_vision"):
                if len(value) >= 2 and value[0] != value[-1]:
                    val_str = f"{value[0]}-{value[-1]}"
                elif value:
                    val_str = f"{value[0]}"
                else:
                    val_str = ""
            else:
                val_str = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            if "min" in value and "max" in value:
                val_str = f"{value['min']}-{value['max']}"
            else:
                val_str = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, (int, float)):
            unit = ""
            if key == "potencia_w": unit = " W"
            elif "lumens" in key:  unit = " lm"
            elif key == "peso_g":  unit = " g"
            elif key == "fps_max": unit = " fps"
            val_str = f"{value}{unit}"
        else:
            val_str = str(value)
        out.append({"label": label, "value": val_str})
    return out


# ── Path por categoría ──────────────────────────────────────────────────

def _extract_iluminacion(html_content: str) -> dict:
    """Delega al extractor existente (luces_html_extractor) que ya funciona."""
    from services.luces_html_extractor import extract_from_html as luces_extract
    return luces_extract(html_content)


def _extract_via_lentes_parser(html_content: str) -> dict:
    """Usa tools/lentes_parser.py — clasifica lente/adaptador/filtro internamente.

    El parser ya tiene `_classify()`, `map_lente_specs()`, `map_filtro_specs()`,
    `map_adaptador_specs()`. Reusamos.
    """
    from lentes_parser import (  # type: ignore
        BHSpecsParser, _clean_title, _extract_brand, _classify,
        _normalize_mount, jsonld_specs, _build_lens_id, _build_filter_id,
        _build_adapter_id, _build_accesorio_model,
        map_lente_specs, map_filtro_specs, map_adaptador_specs,
        map_lente_extras, map_accesorio_extras,
    )

    # Parse DOM
    parser = BHSpecsParser()
    parser.feed(html_content)
    secciones = dict(parser.secciones)
    title = _clean_title(parser.title or "")
    image = _jsonld_image(html_content)
    url = _jsonld_url(html_content) or ""

    # Mergear JSON-LD (autoritativo)
    jsonld = _jsonld_props(html_content)
    if jsonld:
        items = []
        for name, value in jsonld.items():
            if isinstance(value, list):
                clean = [str(v) for v in value if str(v).strip() and str(v) not in ("1 x", "—", "n/a")]
                if clean:
                    items.append({"label": name, "value": "\n".join(clean)})
            elif value and str(value).strip() and str(value) not in ("1 x", "—", "n/a"):
                items.append({"label": name, "value": str(value)})
        if items:
            secciones = {"Specs (JSON-LD)": items, **secciones}

    clase = _classify(secciones, title)
    marca = _extract_brand(title)

    if clase == "lente":
        specs = map_lente_specs(secciones, title=title)
        extras = map_lente_extras(secciones, title=title)
        prod_id = _build_lens_id(marca, specs, title)
        modelo = title  # mantenemos el título canónico
        categoria_sugerida = "Lentes"
    elif clase == "filtro":
        specs = map_filtro_specs(secciones, title=title)
        extras = map_accesorio_extras(secciones, title=title)
        prod_id = _build_filter_id(marca, specs, title)
        modelo = _build_accesorio_model(marca, specs, title)
        categoria_sugerida = "Filtros"
    elif clase == "adaptador":
        specs = map_adaptador_specs(secciones, title=title)
        extras = map_accesorio_extras(secciones, title=title)
        prod_id = _build_adapter_id(marca, specs, title)
        modelo = _build_accesorio_model(marca, specs, title)
        categoria_sugerida = "Adaptadores"
    else:
        # Fallback genérico — devolver title como modelo, specs vacíos
        return _generic_result(title, marca, "", image, url, html_content)

    return _build_result(
        marca=marca, modelo=modelo, specs=specs, extras=extras,
        image=image, url=url, title=title, secciones=secciones,
        categoria_sugerida=categoria_sugerida,
    )


def _extract_via_camaras_parser(html_content: str) -> dict:
    """Usa tools/camaras_parser.py — cámaras."""
    from camaras_parser import (  # type: ignore
        BHSpecsParser, _clean_title, _extract_brand, _extract_modelo,
        map_camara_specs, map_camara_extras,
    )

    parser = BHSpecsParser()
    parser.feed(html_content)
    secciones = dict(parser.secciones)
    title = _clean_title(parser.title or "")
    image = _jsonld_image(html_content)
    url = _jsonld_url(html_content) or ""

    # Mergear JSON-LD
    jsonld = _jsonld_props(html_content)
    if jsonld:
        items = []
        for name, value in jsonld.items():
            if isinstance(value, list):
                clean = [str(v) for v in value if str(v).strip() and str(v) not in ("1 x", "—", "n/a")]
                if clean:
                    items.append({"label": name, "value": "\n".join(clean)})
            elif value and str(value).strip() and str(value) not in ("1 x", "—", "n/a"):
                items.append({"label": name, "value": str(value)})
        if items:
            secciones = {"Specs (JSON-LD)": items, **secciones}

    marca = _extract_brand(title)
    modelo = _extract_modelo(title)
    specs = map_camara_specs(secciones, title=title)
    extras = map_camara_extras(secciones, title=title)

    return _build_result(
        marca=marca, modelo=modelo, specs=specs, extras=extras,
        image=image, url=url, title=title, secciones=secciones,
        categoria_sugerida="Cámaras",
    )


def _generic_result(title: str, marca: str, modelo: str, image: str | None, url: str, html_content: str) -> dict:
    """Fallback cuando no se pudo clasificar: devuelve mínimo (title + foto)."""
    return {
        "marca": marca,
        "modelo": modelo or title,
        "nombre_normalizado": f"{marca} {modelo or title}".strip(),
        "descripcion": "",
        "specs": [],
        "keywords": [],
        "foto_url": image or "",
        "foto_candidates": [image] if image else [],
        "peso": None, "dimensiones": None,
        "montura": None, "formato": None, "resolucion": None,
        "alimentacion": None, "incluye": [], "conectividad": [],
        "compatible_con": [], "video_url": None,
        "precio_bh_usd": None, "categoria_sugerida": None,
        "fuente_url": url, "fuente_titulo": title,
        "fuente_foto_url": image,
        "foto_motivo": "JSON-LD Product.image" if image else None,
        "enriquecido_fuente": "html-upload (categoria desconocida)",
        "bh_url": url, "extras": {}, "fuente": "html-upload",
        "raw_secciones": {},
    }


def _build_result(*, marca: str, modelo: str, specs: dict, extras: dict,
                  image: str | None, url: str, title: str,
                  secciones: dict, categoria_sugerida: str) -> dict:
    """Estructura común AutocompletarResult con keywords canónicas."""
    specs_array = _specs_dict_to_array(specs)
    keywords = compute_keywords(specs)

    # Campos derivados para AutocompletarResult (ficha extendida)
    peso_str: str | None = None
    if isinstance(specs.get("peso_g"), (int, float)):
        g = specs["peso_g"]
        peso_str = f"{round(g/1000, 2)} kg" if g >= 1000 else f"{int(g)} g"

    return {
        "marca": marca,
        "modelo": modelo,
        "nombre_normalizado": f"{marca} {modelo}".strip(),
        "descripcion": "",
        "specs": specs_array,
        "keywords": keywords,  # ← derivadas de specs canónicos, no LLM
        "foto_url": image or "",
        "foto_candidates": [image] if image else [],
        "peso": peso_str,
        "dimensiones": specs.get("dimensiones") or extras.get("dimensiones") or None,
        "montura": specs.get("lens_mount"),
        "formato": specs.get("formato"),
        "resolucion": specs.get("resolucion_max"),
        "alimentacion": ", ".join(specs["alimentacion"]) if isinstance(specs.get("alimentacion"), list) else (specs.get("alimentacion") or None),
        "incluye": [],
        "conectividad": [],
        "compatible_con": [],
        "video_url": None,
        "precio_bh_usd": None,
        "categoria_sugerida": categoria_sugerida,
        "fuente_url": url,
        "fuente_titulo": title,
        "fuente_foto_url": image,
        "foto_motivo": "JSON-LD Product.image" if image else None,
        "enriquecido_fuente": f"html-upload (parser {categoria_sugerida.lower()})",
        "bh_url": url,
        "extras": extras,
        "fuente": "html-upload",
        "raw_secciones": secciones,
    }


# ── Entrada principal ──────────────────────────────────────────────────

def extract_from_html(html_content: str, categoria_hint: str | None = None) -> dict:
    """Extrae specs canónicos de un HTML B&H.

    Dispatcher: detecta categoría (o usa hint) y delega al parser específico.
    Devuelve `AutocompletarResult` con specs canónicos + keywords derivadas.

    Args:
        html_content: HTML completo (Cmd+S de B&H o rawHtml de Firecrawl).
        categoria_hint: si el frontend ya sabe la categoría (ej. usuario eligió
                        en un dropdown), evita la detección automática.
    """
    # Title del <head>
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else ""

    categoria = (categoria_hint or _detect_categoria(html_content, title)).strip()

    if categoria == "Iluminación":
        return _extract_iluminacion(html_content)
    if categoria == "Cámaras":
        return _extract_via_camaras_parser(html_content)
    if categoria in ("Lentes", "Adaptadores", "Filtros"):
        return _extract_via_lentes_parser(html_content)

    # Desconocido — intentar todos, el primero que funcione gana
    for fn in (_extract_via_lentes_parser, _extract_via_camaras_parser, _extract_iluminacion):
        try:
            r = fn(html_content)
            if r and r.get("specs"):
                return r
        except Exception:
            continue

    # Último recurso: resultado vacío con título
    image = _jsonld_image(html_content)
    url = _jsonld_url(html_content) or ""
    return _generic_result(title, "", "", image, url, html_content)
