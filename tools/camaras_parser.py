#!/usr/bin/env python3
"""
tools/camaras_parser.py — CLI de dataset para Cámaras.

⏰ LEGACY-ADYACENTE (F3 del rediseño de ingesta): la lógica de mapeo
(map_camara_specs, map_camara_extras, y los _parse_* de cámaras) se movió a
backend/services/specs_ingesta/parsers/camaras.py — es la fuente única
ahora, usada tanto en vivo (admin) como acá. Este archivo conserva SOLO lo
que sigue siendo suyo: el CLI + I/O de docs/camaras*.json (parse_html/main/
load_*/save_*/jsonld_*), que ningún código en vivo usa.

Uso:
    python3 tools/camaras_parser.py ~/Desktop/Paginas/Camaras/*.html
"""

import html as html_lib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
RELEVAMIENTO_PATH = ROOT / "docs" / "camaras_raw.json"
CURADO_PATH = ROOT / "docs" / "camaras.json"

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
from services.specs_ingesta.parsers.camaras import (  # noqa: E402
    _parse_tipo,
    map_camara_specs,
    map_camara_extras,
)

__all__ = [
    "BHSpecsParser", "_clean_title", "_extract_id", "_extract_brand", "_extract_modelo",
    "_parse_tipo", "map_camara_specs", "map_camara_extras",
    "parse_html", "load_raw", "save_raw", "load_curado", "save_curado", "main",
]


def jsonld_specs(html_path: Path) -> dict:
    """Extrae propiedades desde Product.additionalProperty del JSON-LD.

    Si una propiedad aparece varias veces (ej. "Weight" para cuerpo +
    accesorios del kit), se PRESERVA LA PRIMERA — que es típicamente el
    item principal del producto (cuerpo de cámara), no los accesorios.
    """
    if not html_path.exists():
        return {}
    content = html_path.read_text(encoding="utf-8", errors="replace")
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content, re.DOTALL,
    )
    for b in blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError:
            continue
        if not (isinstance(data, dict) and data.get("@type") == "Product"):
            continue
        ap = data.get("additionalProperty", {})
        props = ap.get("value", []) if isinstance(ap, dict) else (ap if isinstance(ap, list) else [])
        result = {}
        for pv in props:
            if isinstance(pv, dict):
                n = pv.get("name")
                v = pv.get("value")
                if n and n not in result:  # NO sobreescribir — la primera ocurrencia gana
                    if isinstance(v, list):
                        v = [html_lib.unescape(x.replace(" ", " ")) if isinstance(x, str) else x for x in v]
                    elif isinstance(v, str):
                        v = html_lib.unescape(v.replace(" ", " "))
                    result[n] = v
        return result
    return {}


def jsonld_image(html_path: Path) -> str | None:
    if not html_path.exists():
        return None
    content = html_path.read_text(encoding="utf-8", errors="replace")
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content, re.DOTALL,
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


def jsonld_url(html_path: Path) -> str | None:
    if not html_path.exists():
        return None
    content = html_path.read_text(encoding="utf-8", errors="replace")
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content, re.DOTALL,
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


# ── Procesamiento de archivo ────────────────────────────────────────────

_GARBAGE_VALUES = {"1 x", "1x", ":", "—", "-", "N/A", "n/a", ""}


def _is_garbage(v: str) -> bool:
    v = (v or "").strip()
    return v in _GARBAGE_VALUES or v.lower().startswith("not specified")


def parse_html(path: Path) -> dict:
    """Parsea un .html de B&H cámara y devuelve dict raw del producto."""
    content = path.read_text(encoding="utf-8", errors="replace")

    title_m = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else path.stem
    title = _clean_title(title)

    parser = BHSpecsParser()
    parser.feed(content)
    secciones = dict(parser.secciones)

    # Mergear JSON-LD (más rico que DOM para cámaras)
    jl = jsonld_specs(path)
    if jl:
        jl_items = []
        for name, value in jl.items():
            if isinstance(value, list):
                # Filtrar basura, JOIN como string multi-línea para preservar contexto
                # (ej. "Max Recording Modes" tiene codec + resolución + fps en cadena)
                clean_parts = [str(v) for v in value if not _is_garbage(str(v))]
                if clean_parts:
                    jl_items.append({"label": name, "value": "\n".join(clean_parts)})
            elif not _is_garbage(str(value)):
                jl_items.append({"label": name, "value": str(value)})
        if jl_items:
            # JSON-LD primero (autoritativo), DOM como fallback
            secciones = {"Specs (JSON-LD)": jl_items, **secciones}

    image = jsonld_image(path)
    url = jsonld_url(path)
    if not url:
        saved = re.search(r"saved from url=\(\d+\)(https?://\S+)", content)
        if saved:
            url = saved.group(1).strip()

    prod_id = _extract_id(title)
    brand = _extract_brand(title)
    modelo = _extract_modelo(title)
    tipo = _parse_tipo(secciones, title) or "Camera"

    return {
        "id": prod_id,
        "categoria_raiz": "Cámaras",
        "subtipo": tipo,
        "marca": brand,
        "modelo": modelo,
        "url_source": url or "",
        "image_url": image or "",
        "status_bh": "Desconocido",
        "fuente": f"html guardado manual ({date.today().isoformat()})",
        "secciones": secciones,
    }


# ── Persistencia ────────────────────────────────────────────────────────

_META_TEMPLATE = {
    "version": "1.0",
    "descripcion": (
        "Dataset crudo de specs reales de B&H Photo (cámaras) capturadas por html "
        "guardado manual. Mismo workflow que docs/iluminacion_raw.json — fuente "
        "agnóstica, B&H primario + manufacturer sites como fallback."
    ),
    "metodo_captura": "HTML guardado manual (Cmd+S → Webpage Complete)",
    "convencion": "secciones B&H + JSON-LD merged",
}


def load_raw() -> dict:
    if RELEVAMIENTO_PATH.exists():
        return json.loads(RELEVAMIENTO_PATH.read_text(encoding="utf-8"))
    return {"_meta": _META_TEMPLATE, "products": []}


def save_raw(data: dict):
    RELEVAMIENTO_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


_CURADO_META_DEFAULT = {
    "version": "1.0",
    "descripcion": (
        "Dataset normalizado de cámaras del inventario. Cada producto tiene specs "
        "(comparables/filtrables), extras (ficha técnica), y ficha (raw B&H/manufacturer)."
    ),
    "fuente_principal": "B&H Photo HTML guardado + JSON-LD structured data",
    "fuente_alternativa": "manufacturer sites (sony.com, canon.com, red.com, etc.) vía WebFetch",
    "ubicacion_htmls": "~/Desktop/Paginas/Camaras/",
    "schema": {
        "specs": (
            "21 spec_keys canónicos (tipo, lens_mount, formato, resolucion_max, "
            "fps_max, codecs, megapixels, iso_nativo/extendido, rango_dinamico_stops, "
            "estabilizacion, autofocus, fast_slow_motion, lens_communication, gps, "
            "ip_streaming, netflix_approved, continuous_shooting_fps, max_aperture, "
            "sensor_crop, recording_limit_min, peso_g)"
        ),
        "extras": "~80 campos estructurados (sensor, af_puntos, ISO range, video_io, audio_io, etc.)",
        "ficha": "raw B&H — secciones tal cual aparecen"
    },
    "convenciones": {
        "ids": "{marca}_{modelo}, snake_case. Ej: sony_fx3a, red_komodo, red_komodo_x",
        "unidades": "Numéricos en base SI (g, K, fps, MP). UI computa display.",
        "ausencia": "null o campo ausente = 'no aplica'. Ej. lens_mount=null para GoPro (lente fijo)",
        "lens_mount": "null para action/fixed-lens. Enum: E, RF, EF, L, Z, X, MFT, PL, BMD, B4, M42"
    },
    "categorizacion": {
        "nivel_1": "Foto / Video (contenedor) / Acción — por use case",
        "nivel_2_video": "Sub-categorías por montura (Montura E, RF, EF, L, Z, PL, BMD)",
        "multi_cat": "Mirrorless híbridas aparecen en Foto + Video/Montura X (ej. a7V)"
    },
    "como_agregar_camara_nueva": [
        "1. Guardar página B&H del producto en ~/Desktop/Paginas/Camaras/ (Cmd+S → Webpage Complete)",
        "2. Agregar la ruta del HTML en tools/camaras_rebuild.sh",
        "3. Correr: bash tools/camaras_rebuild.sh",
        "4. Verificar resultado en docs/camaras.json",
        "5. Si el HTML viene del sitio fabricante (no B&H), agregar entrada manual en tools/camaras_patches.py"
    ]
}


def load_curado() -> dict:
    if CURADO_PATH.exists():
        return json.loads(CURADO_PATH.read_text(encoding="utf-8"))
    return {"_meta": _CURADO_META_DEFAULT, "products": {}}


def save_curado(data: dict):
    CURADO_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ── Main ────────────────────────────────────────────────────────────────

def main(html_paths: list[Path]):
    raw_data = load_raw()
    curado = load_curado()

    existing_ids = {p["id"] for p in raw_data["products"]}
    added_raw = 0
    added_curado = 0
    skipped = 0

    for path in html_paths:
        if not path.exists():
            print(f"  WARN: no existe: {path}")
            continue

        print(f"Procesando: {path.name}")
        raw = parse_html(path)
        prod_id = raw["id"]

        if prod_id in existing_ids:
            print(f"  → raw ya existe ({prod_id}), skip")
            skipped += 1
        else:
            raw_data["products"].append(raw)
            existing_ids.add(prod_id)
            added_raw += 1
            print(f"  + raw agregado ({prod_id})")

        # `extras` removido del output: no se persistía a DB ni se leía
        # desde el frontend. Si en el futuro se necesita re-habilitar
        # campos descriptivos no-canónicos, declararlos en el registry
        # y emitirlos via `map_camara_specs`.
        specs = map_camara_specs(raw["secciones"], title=raw["modelo"])
        curado["products"][prod_id] = {
            "marca": raw["marca"],
            "modelo": raw["modelo"],
            "url_source": raw.get("url_source", ""),
            "image_url": raw.get("image_url", ""),
            "specs": specs,
            "ficha": raw["secciones"],
        }
        added_curado += 1
        print(f"  + curado: {specs}")

    save_raw(raw_data)
    save_curado(curado)
    print(f"\nListo. Raw nuevos: {added_raw} | Curado: {added_curado} | Skipped: {skipped}")
    print(f"  → {RELEVAMIENTO_PATH.relative_to(ROOT)}")
    print(f"  → {CURADO_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tools/camaras_parser.py <archivo.html> [archivo2.html ...]")
        sys.exit(1)
    paths = []
    for arg in sys.argv[1:]:
        paths.extend(Path(arg).parent.glob(Path(arg).name) if "*" in arg else [Path(arg)])
    main(paths)
