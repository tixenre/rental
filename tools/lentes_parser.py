#!/usr/bin/env python3
"""
tools/lentes_parser.py — CLI de dataset para Lentes + Filtros + Adaptadores.

⏰ LEGACY-ADYACENTE (F3 del rediseño de ingesta): la lógica de mapeo
(_classify, map_lente_specs, map_filtro_specs, map_adaptador_specs, los
_build_*_id, y los _parse_* propios) se movió a
backend/services/specs_ingesta/parsers/lentes.py — es la fuente única ahora,
usada tanto en vivo (admin) como acá. Este archivo conserva SOLO lo que
sigue siendo suyo: el CLI + I/O de docs/{lentes,adaptadores,filtros}*.json
(parse_html/main/load_*/save_*/jsonld_*), que ningún código en vivo usa.

La carpeta ~/Desktop/Paginas/Lentes/ es mixta: lentes + filtros + adaptadores.
El parser clasifica cada HTML por heurística y escribe a 3 datasets.

Las lentes Zeiss M42 son HTMLs de eBay (no B&H) — el parser las saltea y
las maneja tools/lentes_patches.py con datos curados manualmente.

Uso:
    python3 tools/lentes_parser.py ~/Desktop/Paginas/Lentes/*.html
"""

import html as html_lib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent

LENTES_RAW_PATH = ROOT / "docs" / "lentes_raw.json"
LENTES_CURADO_PATH = ROOT / "docs" / "lentes.json"
ADAPTADORES_RAW_PATH = ROOT / "docs" / "adaptadores_raw.json"
ADAPTADORES_CURADO_PATH = ROOT / "docs" / "adaptadores.json"
FILTROS_RAW_PATH = ROOT / "docs" / "filtros_raw.json"
FILTROS_CURADO_PATH = ROOT / "docs" / "filtros.json"

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
from services.specs_ingesta.parsers.lentes import (  # noqa: E402
    _classify,
    _build_lens_id,
    _build_filter_id,
    _build_adapter_id,
    _build_accesorio_model,
    map_lente_specs,
    map_filtro_specs,
    map_adaptador_specs,
    map_lente_extras,
    map_accesorio_extras,
)

__all__ = [
    "BHSpecsParser", "_clean_title", "_extract_id", "_extract_brand", "_extract_modelo",
    "_classify", "_build_lens_id", "_build_filter_id", "_build_adapter_id", "_build_accesorio_model",
    "map_lente_specs", "map_filtro_specs", "map_adaptador_specs", "map_lente_extras", "map_accesorio_extras",
    "parse_html", "load_raw", "save_raw", "load_curado", "save_curado", "main",
]


def _jsonld_blocks(html_path: Path):
    if not html_path.exists():
        return []
    content = html_path.read_text(encoding="utf-8", errors="replace")
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content, re.DOTALL,
    )
    out = []
    for b in blocks:
        try:
            out.append(json.loads(b))
        except json.JSONDecodeError:
            continue
    return out


def jsonld_specs(html_path: Path) -> dict:
    """Igual que en camaras_parser: preservar primera ocurrencia."""
    for data in _jsonld_blocks(html_path):
        if not (isinstance(data, dict) and data.get("@type") == "Product"):
            continue
        ap = data.get("additionalProperty", {})
        props = ap.get("value", []) if isinstance(ap, dict) else (ap if isinstance(ap, list) else [])
        result = {}
        for pv in props:
            if isinstance(pv, dict):
                n = pv.get("name")
                v = pv.get("value")
                if n and n not in result:
                    if isinstance(v, list):
                        v = [html_lib.unescape(x.replace(" ", " ")) if isinstance(x, str) else x for x in v]
                    elif isinstance(v, str):
                        v = html_lib.unescape(v.replace(" ", " "))
                    result[n] = v
        return result
    return {}


def jsonld_image(html_path: Path) -> str | None:
    for data in _jsonld_blocks(html_path):
        if isinstance(data, dict) and data.get("@type") == "Product":
            img = data.get("image")
            if isinstance(img, list) and img:
                return img[0]
            if isinstance(img, str):
                return img
    return None


def jsonld_url(html_path: Path) -> str | None:
    for data in _jsonld_blocks(html_path):
        if isinstance(data, dict) and data.get("@type") == "Product":
            url = data.get("url")
            if isinstance(url, str):
                return url
    return None


# ─── Procesamiento ──────────────────────────────────────────────────────

_GARBAGE_VALUES = {"1 x", "1x", ":", "—", "-", "N/A", "n/a", ""}


def _is_garbage(v: str) -> bool:
    v = (v or "").strip()
    return v in _GARBAGE_VALUES or v.lower().startswith("not specified")


def _is_bh_html(content: str) -> bool:
    return "bhphotovideo.com" in content.lower() or "data-selenium=" in content


def parse_html(path: Path) -> dict | None:
    """Parsea un HTML B&H de lente/filtro/adaptador.

    Devuelve None si:
      - El HTML no es de B&H (ej. eBay para Zeiss M42).
      - No se pudo clasificar (será warning para reviewmanual).
    """
    content = path.read_text(encoding="utf-8", errors="replace")

    if not _is_bh_html(content):
        # No es B&H — probable eBay (Zeiss vintage). Skip — los maneja patches.
        return None

    title_m = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else path.stem
    title = _clean_title(title)

    parser = BHSpecsParser()
    parser.feed(content)
    secciones = dict(parser.secciones)

    # Mergear JSON-LD (autoritativo)
    jl = jsonld_specs(path)
    if jl:
        jl_items = []
        for name, value in jl.items():
            if isinstance(value, list):
                clean_parts = [str(v) for v in value if not _is_garbage(str(v))]
                if clean_parts:
                    jl_items.append({"label": name, "value": "\n".join(clean_parts)})
            elif not _is_garbage(str(value)):
                jl_items.append({"label": name, "value": str(value)})
        if jl_items:
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
    clase = _classify(secciones, title)

    return {
        "id": prod_id,
        "clase": clase,  # "lente" | "filtro" | "adaptador" | "unknown"
        "marca": brand,
        "modelo": modelo,
        "url_source": url or "",
        "image_url": image or "",
        "title": title,
        "secciones": secciones,
    }


# ─── Persistencia ───────────────────────────────────────────────────────

_LENTES_META = {
    "version": "1.0",
    "descripcion": (
        "Dataset normalizado de lentes (zoom, fijos, vintage M42). Cada producto "
        "tiene specs (comparables/filtrables), extras (ficha técnica), y ficha (raw)."
    ),
    "fuente_principal": "B&H Photo HTML guardado + JSON-LD structured data",
    "fuente_alternativa": "eBay listings para Zeiss Jena vintage (vía patches manuales)",
    "ubicacion_htmls": "~/Desktop/Paginas/Lentes/",
    "schema": {
        "specs": (
            "15 spec_keys canónicos (lens_mount, distancia_focal [rango mm], "
            "apertura [rango f/], formato, diametro_filtro, linea, angulo_vision, "
            "distancia_minima_cm, magnificacion, hojas_diafragma, estabilizacion, "
            "autofocus, construccion_optica, peso_g, dimensiones)"
        ),
        "extras": "~15 campos estructurados (focus_type, optical_design_raw, etc.)",
        "ficha": "raw B&H/eBay — secciones tal cual aparecen"
    },
    "convenciones": {
        "ids": "{marca}_{modelo}, snake_case. Ej: sony_fe2470gm2, sigma_18-35",
        "rangos": "distancia_focal/apertura son LISTA: [v] fijo, [min, max] zoom/variable",
        "peso": "peso_g como INT en gramos (no string). Display lo computa la UI.",
        "lens_mount": "Enum: E, RF, EF, L, Z, X, MFT, PL, BMD, B4, M42"
    },
    "como_agregar_lente_nueva": [
        "1. Guardar página B&H en ~/Desktop/Paginas/Lentes/ (Cmd+S → Webpage Complete)",
        "2. Agregar la ruta en tools/lentes_rebuild.sh",
        "3. Correr: bash tools/lentes_rebuild.sh",
        "4. Si es lente vintage de eBay / sitio fabricante: editar tools/lentes_patches.py"
    ]
}

_ADAPTADORES_META = {
    "version": "1.0",
    "descripcion": (
        "Dataset normalizado de adaptadores de montura: convierten una rosca "
        "body (E/RF/L/Z) a recibir lentes de otra montura (EF/M42/etc.). "
        "Incluye speedboosters (Meike, Metabones) y drop-in filter adapters "
        "(Canon EF→RF con ND variable interno)."
    ),
    "fuente_principal": "B&H Photo HTML guardado + JSON-LD structured data",
    "ubicacion_htmls": "~/Desktop/Paginas/Lentes/ (mixta con lentes/filtros)",
    "schema": {
        "specs": (
            "7 spec_keys (tipo enum, lens_mount [body], lens_mount_out [lens], "
            "electronica [bool], incluye_iris [bool], magnificacion [string, solo speedboosters], peso_g)"
        ),
    },
    "convenciones": {
        "lens_mount_dual": "lens_mount=lado body (cámara); lens_mount_out=lado lente. Ej. Sigma MC-11 EF→E: lens_mount=E, lens_mount_out=EF",
        "tipo_enum": "Adaptador montura | Speedbooster | Macro tube",
    },
}

_FILTROS_META = {
    "version": "1.0",
    "descripcion": (
        "Dataset normalizado de filtros frontales: ND, polarizador, variable, "
        "difusión (Pro-Mist) y UV. Vinculados al frente del lente por su "
        "diámetro de filter thread (67mm, 77mm, 82mm)."
    ),
    "fuente_principal": "B&H Photo HTML guardado + JSON-LD structured data",
    "ubicacion_htmls": "~/Desktop/Paginas/Lentes/ (mixta con lentes/adaptadores)",
    "schema": {
        "specs": (
            "6 spec_keys (tipo enum, diametro_filtro [obligatorio], densidad [ND/variable], "
            "material [vidrio/resina], grade [solo difusión: 1/4, 1/8...], peso_g)"
        ),
    },
    "convenciones": {
        "tipo_enum": "Filtro ND | Filtro polarizador | Filtro UV | Filtro variable | Filtro difusión",
        "diametro_canonical": "Siempre mm. El diámetro define la sub-categoría (ej. '82mm', '77mm').",
    },
}


def load_raw(path: Path, meta: dict) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"_meta": meta, "products": []}


def save_raw(data: dict, path: Path):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_curado(path: Path, meta: dict) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"_meta": meta, "products": {}}


def save_curado(data: dict, path: Path):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ─── Main ───────────────────────────────────────────────────────────────

def main(html_paths: list[Path]):
    lentes_raw = load_raw(LENTES_RAW_PATH, _LENTES_META)
    adaptadores_raw = load_raw(ADAPTADORES_RAW_PATH, _ADAPTADORES_META)
    filtros_raw = load_raw(FILTROS_RAW_PATH, _FILTROS_META)
    lentes_curado = load_curado(LENTES_CURADO_PATH, _LENTES_META)
    adaptadores_curado = load_curado(ADAPTADORES_CURADO_PATH, _ADAPTADORES_META)
    filtros_curado = load_curado(FILTROS_CURADO_PATH, _FILTROS_META)

    counts = {"lente": 0, "filtro": 0, "adaptador": 0, "skipped_ebay": 0, "unknown": 0}

    for path in html_paths:
        if not path.exists():
            print(f"  WARN: no existe: {path}")
            continue

        print(f"Procesando: {path.name}")
        result = parse_html(path)

        if result is None:
            print(f"  → skip (no es B&H — probable eBay; los maneja patches)")
            counts["skipped_ebay"] += 1
            continue

        clase = result["clase"]
        if clase == "unknown":
            print(f"  ! WARN: no clasificable ({result['title']})")
            counts["unknown"] += 1
            continue

        counts[clase] += 1
        prod_id = result["id"]
        raw_entry = {
            "id": prod_id,
            "categoria_raiz": "Lentes" if clase == "lente" else "Adaptadores y Filtros",
            "subtipo": clase,
            "marca": result["marca"],
            "modelo": result["modelo"],
            "url_source": result["url_source"],
            "image_url": result["image_url"],
            "status_bh": "OK",
            "fuente": f"B&H HTML guardado ({date.today().isoformat()})",
            "secciones": result["secciones"],
        }

        # Dispatch a dataset correspondiente. `extras` removido del output:
        # no se persistía a DB. Las funciones map_*_extras quedan en el
        # módulo como helpers de debugging, sin caller activo.
        if clase == "lente":
            specs = map_lente_specs(result["secciones"], title=result["title"])
            curado_target = lentes_curado
            raw_target = lentes_raw
            prod_id = _build_lens_id(result["marca"], specs, result["title"])
            raw_entry["categoria_raiz"] = "Lentes"
        elif clase == "filtro":
            specs = map_filtro_specs(result["secciones"], title=result["title"])
            prod_id = _build_filter_id(result["marca"], specs, result["title"])
            result["modelo"] = _build_accesorio_model(result["marca"], specs, result["title"])
            curado_target = filtros_curado
            raw_target = filtros_raw
            raw_entry["categoria_raiz"] = "Filtros"
        else:  # adaptador
            specs = map_adaptador_specs(result["secciones"], title=result["title"])
            prod_id = _build_adapter_id(result["marca"], specs, result["title"])
            result["modelo"] = _build_accesorio_model(result["marca"], specs, result["title"])
            curado_target = adaptadores_curado
            raw_target = adaptadores_raw
            raw_entry["categoria_raiz"] = "Adaptadores"
        raw_entry["id"] = prod_id
        raw_entry["modelo"] = result["modelo"]

        # Raw (lista de productos)
        raw_target["products"] = [p for p in raw_target["products"] if p.get("id") != prod_id]
        raw_target["products"].append(raw_entry)

        # Curado (dict de productos)
        curado_target["products"][prod_id] = {
            "marca": result["marca"],
            "modelo": result["modelo"],
            "url_source": result["url_source"],
            "image_url": result["image_url"],
            "specs": specs,
            "ficha": result["secciones"],
        }
        print(f"  + {clase} agregado ({prod_id}) — {len(specs)} specs")

    save_raw(lentes_raw, LENTES_RAW_PATH)
    save_raw(adaptadores_raw, ADAPTADORES_RAW_PATH)
    save_raw(filtros_raw, FILTROS_RAW_PATH)
    save_curado(lentes_curado, LENTES_CURADO_PATH)
    save_curado(adaptadores_curado, ADAPTADORES_CURADO_PATH)
    save_curado(filtros_curado, FILTROS_CURADO_PATH)

    print()
    print(f"Listo. Lentes: {counts['lente']} | Adaptadores: {counts['adaptador']} | Filtros: {counts['filtro']}")
    print(f"  Skipped (eBay/no-B&H): {counts['skipped_ebay']} | Unknown: {counts['unknown']}")
    print(f"  → {LENTES_CURADO_PATH.relative_to(ROOT)}")
    print(f"  → {ADAPTADORES_CURADO_PATH.relative_to(ROOT)}")
    print(f"  → {FILTROS_CURADO_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tools/lentes_parser.py <archivo.html> [archivo2.html ...]")
        sys.exit(1)
    paths = []
    for arg in sys.argv[1:]:
        if "*" in arg:
            paths.extend(Path(arg).parent.glob(Path(arg).name))
        else:
            paths.append(Path(arg))
    main(paths)
