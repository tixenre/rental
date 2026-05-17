#!/usr/bin/env python3
"""
tools/lentes_parser.py — Parser de HTMLs de B&H para lentes + filtros + adaptadores.

Mismo pipeline que iluminacion_parser/camaras_parser. La carpeta
~/Desktop/Paginas/Lentes/ es mixta: 11 lentes + 4 filtros + 4 adaptadores.
El parser clasifica cada HTML por heurística (presencia de Focal Length /
Item Type / Filter Type) y escribe a DOS datasets:

  - docs/lentes.json + docs/lentes_raw.json     → categoría "Lentes"
  - docs/accesorios.json + docs/accesorios_raw.json → categoría "Adaptadores y Filtros"

Las 2 lentes Zeiss M42 son HTMLs de eBay (no B&H) — el parser las saltea y
las maneja tools/lentes_patches.py con datos curados manualmente.

Reusa primitives genéricas de iluminacion_parser (BHSpecsParser, _clean_title,
_extract_brand, _extract_modelo, _extract_id, _find_value, _parse_peso_g).

Uso:
    python3 tools/lentes_parser.py ~/Desktop/Paginas/Lentes/*.html
"""

import html as html_lib
import json
import re
import sys
from datetime import date
from pathlib import Path

from iluminacion_parser import (  # type: ignore
    BHSpecsParser,
    _clean_title,
    _extract_brand,
    _extract_id,
    _extract_modelo,
    _find_value,
    _parse_peso_g,
)

ROOT = Path(__file__).parent.parent

LENTES_RAW_PATH = ROOT / "docs" / "lentes_raw.json"
LENTES_CURADO_PATH = ROOT / "docs" / "lentes.json"
ADAPTADORES_RAW_PATH = ROOT / "docs" / "adaptadores_raw.json"
ADAPTADORES_CURADO_PATH = ROOT / "docs" / "adaptadores.json"
FILTROS_RAW_PATH = ROOT / "docs" / "filtros_raw.json"
FILTROS_CURADO_PATH = ROOT / "docs" / "filtros.json"


# ─── Helpers de clasificación ────────────────────────────────────────────

def _classify(secciones: dict, title: str) -> str:
    """Devuelve 'lente', 'filtro', 'adaptador' o 'unknown'."""
    item_type = (_find_value(secciones, "Item Type") or "").lower()
    if "lens mount adapter" in item_type or "mount adapter" in item_type:
        return "adaptador"
    if _find_value(secciones, "Filter Type"):
        return "filtro"
    if _find_value(secciones, "Focal Length") and _find_value(secciones, "Aperture"):
        return "lente"
    # Fallback por título
    t = title.lower()
    if "filter" in t and "adapter" not in t:
        return "filtro"
    if "adapter" in t or "speedbooster" in t or "converter" in t:
        return "adaptador"
    if "lens" in t:
        return "lente"
    return "unknown"


# ─── Lens mount mapping ─────────────────────────────────────────────────

_LENS_MOUNT_MAP = [
    # (regex sobre value, canónico)
    (r"\bsony\s*e\b|\be[\s-]?mount\b|^e$|^e\s", "E"),
    (r"\bcanon\s*rf\b|\brf[\s-]?mount\b|^rf$|^rf\s", "RF"),
    (r"\bcanon\s*ef-?s?\b|\bef[\s-]?mount\b|^ef$|^ef\s|^ef/", "EF"),
    (r"\bl[\s-]?mount\b|\bleica\s*l\b", "L"),
    (r"\bnikon\s*z\b|\bz[\s-]?mount\b|^z$|^z\s", "Z"),
    (r"\bfuji.*x\b|\bx[\s-]?mount\b", "X"),
    (r"\bmicro\s*four\s*thirds\b|\bm4/3\b|\bmft\b", "MFT"),
    (r"\bpl[\s-]?mount\b|\barri\s*pl\b|^pl$|^pl\s", "PL"),
    (r"\bblackmagic\b|\bbmd\b", "BMD"),
    (r"\bm42\b", "M42"),
    (r"\bb4[\s-]?mount\b|^b4$", "B4"),
]
# Pre-compilado para evitar re.compile() en hot loop (se llama ~50 veces por
# rebuild — 12 lentes + 4 adaptadores + 4 filtros, cada uno chequea ambos
# lados de la rosca).
_MOUNT_PATTERNS = [(re.compile(pat), canonical) for pat, canonical in _LENS_MOUNT_MAP]


def _normalize_mount(raw: str) -> str | None:
    if not raw:
        return None
    v = raw.lower().strip()
    for pat, canonical in _MOUNT_PATTERNS:
        if pat.search(v):
            return canonical
    return None


# ─── Spec mappers: LENTES ────────────────────────────────────────────────

def _parse_focal_length(secciones: dict) -> list[float] | None:
    """Devuelve lista de 1 o 2 floats (mm).

    Ej.: "24 to 70mm"           → [24, 70]
         "35mm"                 → [35]
         "18 to 35mm (35mm Eq…" → [18, 35] (ignora equivalente entre paréntesis)
    """
    val = _find_value(secciones, "Focal Length")
    if not val:
        return None
    # Sacar paréntesis (35mm Equivalent: …)
    primary = re.sub(r"\([^)]*\)", "", val).strip()
    # Zoom "X to Y mm"
    m = re.search(r"([\d.]+)\s*(?:to|-|–)\s*([\d.]+)\s*mm", primary, re.IGNORECASE)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return [int(lo) if lo.is_integer() else lo, int(hi) if hi.is_integer() else hi]
    # Fijo "Xmm"
    m = re.search(r"([\d.]+)\s*mm", primary)
    if m:
        v = float(m.group(1))
        return [int(v) if v.is_integer() else v]
    return None


def _parse_apertura(secciones: dict) -> list[float] | None:
    """Apertura máxima (la importante). Soporta rango variable.

    Ej.: "Maximum: f/2.8 Minimum: f/22"          → [2.8]
         "Maximum: f/3.5-6.3 Minimum: f/22-29"   → [3.5, 6.3]
         "f/1.4"                                  → [1.4]
    """
    val = _find_value(secciones, "Aperture")
    if not val:
        return None
    # Tomar solo el Maximum si existe
    m_max = re.search(r"maximum:\s*f/?([\d.\s\-–to]+?)(?:\s+minimum|$)", val, re.IGNORECASE)
    target = m_max.group(1).strip() if m_max else val
    # Rango variable f/3.5-6.3
    m = re.search(r"([\d.]+)\s*(?:-|–|to)\s*([\d.]+)", target)
    if m:
        return [float(m.group(1)), float(m.group(2))]
    # Valor único f/2.8
    m = re.search(r"f?/?([\d.]+)", target)
    if m:
        return [float(m.group(1))]
    return None


def _parse_lens_format(secciones: dict) -> str | None:
    val = _find_value(secciones, "Lens Format Coverage", "Format Coverage", "Coverage")
    if not val:
        return None
    v = val.lower().strip()
    if "full" in v:
        return "Full-frame"
    if "aps-c" in v or "apsc" in v:
        return "APS-C"
    if "super 35" in v or "s35" in v:
        return "Super 35"
    if "micro four thirds" in v or "mft" in v or "m4/3" in v:
        return "MFT"
    if "medium format" in v:
        return "Medium Format"
    return val.strip()


def _parse_filter_size(secciones: dict) -> int | None:
    val = _find_value(secciones, "Filter Size")
    if not val:
        return None
    m = re.search(r"(\d+)\s*mm", val)
    return int(m.group(1)) if m else None


def _parse_angulo_vision(secciones: dict) -> list[float] | None:
    """ '84° to 34°' → [34, 84] (orden ascendente)  | '63.4°' → [63.4]"""
    val = _find_value(secciones, "Angle of View")
    if not val:
        return None
    m = re.search(r"([\d.]+)\s*°\s*(?:to|-|–)\s*([\d.]+)\s*°", val, re.IGNORECASE)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        lo, hi = min(a, b), max(a, b)
        return [int(lo) if lo.is_integer() else lo,
                int(hi) if hi.is_integer() else hi]
    m = re.search(r"([\d.]+)\s*°", val)
    if m:
        v = float(m.group(1))
        return [int(v) if v.is_integer() else v]
    return None


def _parse_min_focus_cm(secciones: dict) -> float | None:
    """'8.3" / 21 cm' → 21.0"""
    val = _find_value(secciones, "Minimum Focus Distance")
    if not val:
        return None
    m_cm = re.search(r"([\d.]+)\s*cm", val, re.IGNORECASE)
    if m_cm:
        return float(m_cm.group(1))
    m_m = re.search(r"([\d.]+)\s*m\b", val)
    if m_m:
        return float(m_m.group(1)) * 100
    # Solo imperial
    m_ft = re.search(r"([\d.]+)\s*(?:'|ft)", val)
    if m_ft:
        return round(float(m_ft.group(1)) * 30.48, 1)
    m_in = re.search(r"([\d.]+)\s*[\"”]", val)
    if m_in:
        return round(float(m_in.group(1)) * 2.54, 1)
    return None


def _parse_magnificacion(secciones: dict) -> str | None:
    val = _find_value(secciones, "Magnification")
    if not val:
        return None
    # "1:3.13 Macro Reproduction Ratio 0.32x Magnification" → "0.32x"
    m = re.search(r"([\d.]+x)\s*Magnification", val, re.IGNORECASE)
    if m:
        return m.group(1)
    # "0.71x" (speedbooster)
    m = re.search(r"([\d.]+x)", val)
    if m:
        return m.group(1)
    return val.strip()


def _parse_iris_blades(secciones: dict) -> int | None:
    """'11, Rounded' → 11"""
    val = _find_value(secciones, "Aperture/Iris Blades", "Iris Blades")
    if not val:
        return None
    m = re.search(r"(\d+)", val)
    return int(m.group(1)) if m else None


def _parse_estabilizacion_lens(secciones: dict) -> bool | None:
    """Para LENTES: 'Image Stabilization' = 'No' | 'Yes' | nombre del sistema."""
    val = _find_value(secciones, "Image Stabilization")
    if val is None:
        return None
    v = val.strip().lower()
    if v in ("no", "none", "n/a", ""):
        return False
    return True


def _parse_autofocus_lens(secciones: dict) -> bool | None:
    val = _find_value(secciones, "Focus Type", "Focus Mode")
    if val is None:
        return None
    v = val.strip().lower()
    return "auto" in v or "af" in v


def _parse_construccion_optica(secciones: dict) -> str | None:
    """'20 Elements in 15 Groups' → '20 elementos / 15 grupos'"""
    val = _find_value(secciones, "Optical Design")
    if not val:
        return None
    m = re.search(r"(\d+)\s*Elements?\s*in\s*(\d+)\s*Groups?", val, re.IGNORECASE)
    if m:
        return f"{m.group(1)} elementos / {m.group(2)} grupos"
    return val.strip()


def _parse_dimensiones_lens(secciones: dict) -> str | None:
    """'ø: 3.5 x L: 4.7" / ø: 87.8 x L: 119.9 mm' → 'Ø87.8 × 119.9 mm'"""
    val = _find_value(secciones, "Dimensions")
    if not val:
        return None
    # Patrón métrico ø: D x L: L mm
    m = re.search(r"ø:\s*([\d.]+)\s*x\s*L:\s*([\d.]+)\s*mm", val, re.IGNORECASE)
    if m:
        return f"Ø{m.group(1)} × {m.group(2)} mm"
    # Diameter X mm Depth Y mm (adaptadores y filtros)
    m = re.search(r"Diameter:\s*([\d.]+)\s*[\"']\s*/\s*([\d.]+)\s*mm", val, re.IGNORECASE)
    if m:
        return f"Ø{m.group(2)} mm"
    m_cm = re.search(r"([\d.]+)\s*x\s*([\d.]+)\s*x\s*([\d.]+)\s*cm", val, re.IGNORECASE)
    if m_cm:
        return f"{m_cm.group(1)} × {m_cm.group(2)} × {m_cm.group(3)} cm"
    return val.split("/")[0].strip()


def _parse_linea(title: str) -> str | None:
    """Detecta linea/serie de la lente desde el título.
    'Sigma 35mm f/1.4 DG HSM Art Lens' → 'Art'
    'Sony FE 24-70mm f/2.8 GM II' → 'GM'
    """
    t = title
    for tag in ("GM II", "GM OSS II", "GM OSS", "GM", "Art", "Contemporary", "Sports",
                "L II", "L IS II", "L IS", "L USM", "L", "Cinema", "Master Prime",
                "Probe"):
        # Buscar palabra completa con boundaries
        if re.search(rf"\b{re.escape(tag)}\b", t):
            return tag
    return None


# ─── ID builders ────────────────────────────────────────────────────────

def _build_lens_id(brand: str, specs: dict, title: str = "") -> str:
    """Construye ID estable para lente: brand_focal_apertura[_linea].

    Ej:
      Sony FE 24-70 f/2.8 GM II → "sony_24_70_28_gm_ii"
      Sigma 35 f/1.4 Art        → "sigma_35_14_art"
      Canon EF 70-200 f/2.8L    → "canon_ef_70_200_28_l"
      Venus Optics Laowa 24 f/14 Probe → "laowa_24_14_probe"
    """
    parts: list[str] = []

    # Para Venus Optics → preferimos "laowa" como brand corto (más reconocido)
    brand_canon = brand.strip().lower()
    if "venus" in brand_canon or "laowa" in (brand_canon + title.lower()):
        parts.append("laowa")
    else:
        parts.append(re.sub(r"[^a-z0-9]", "", brand_canon) or "unknown")

    focal = specs.get("distancia_focal")
    if focal:
        if len(focal) >= 2:
            parts.append(f"{_to_int_str(focal[0])}_{_to_int_str(focal[1])}")
        else:
            parts.append(_to_int_str(focal[0]))

    apertura = specs.get("apertura")
    if apertura:
        a = apertura[0]
        # f/2.8 → "28", f/1.4 → "14", f/14 → "f14" (probe lens)
        if a < 10:
            parts.append(str(int(round(a * 10))))
        else:
            parts.append(f"f{int(a)}")

    linea = specs.get("linea")
    if linea:
        slug = re.sub(r"[^a-z0-9 ]", "", linea.lower()).replace(" ", "_")
        if slug:
            parts.append(slug)

    return "_".join(parts)


def _build_filter_id(brand: str, specs: dict, title: str = "") -> str:
    """ID estable para filtro: brand_diametro_tipo[_grade]."""
    parts = [re.sub(r"[^a-z0-9]", "", brand.lower()) or "filter"]

    d = specs.get("diametro_filtro")
    if d:
        parts.append(str(d))

    tipo = (specs.get("filtro_subtipo") or "").lower()
    if "polariz" in tipo:
        parts.append("cpl")
    elif "variable" in tipo:
        parts.append("vnd")
    elif "difus" in tipo or "mist" in title.lower() or "pro-mist" in title.lower():
        parts.append("promist")
    elif "nd" in tipo:
        parts.append("nd")
    elif "uv" in tipo:
        parts.append("uv")

    # Grade para Pro-Mist (1/4, 1/8)
    m = re.search(r"grade\s*(\d+)\s*/\s*(\d+)", title, re.IGNORECASE)
    if m:
        parts.append(f"{m.group(1)}_{m.group(2)}")

    return "_".join(parts)


def _build_adapter_id(brand: str, specs: dict, title: str = "") -> str:
    """ID estable para adaptador: brand_mountout_mount[_tipo]."""
    parts = [re.sub(r"[^a-z0-9]", "", brand.lower()) or "adapter"]

    # Lo distintivo es el par de monturas (lens → body)
    mount_out = (specs.get("lens_mount_out") or "").lower()
    mount = (specs.get("lens_mount") or "").lower()
    if mount_out and mount:
        parts.append(f"{mount_out}_{mount}")

    # Diferenciador: speedbooster vs regular vs drop-in
    tipo = (specs.get("adaptador_subtipo") or "").lower()
    title_l = title.lower()
    if "speedbooster" in tipo or "speed" in title_l:
        parts.append("speedbooster")
    elif "drop" in title_l or specs.get("incluye_iris"):
        parts.append("dropin")
    elif "mc-11" in title_l or "mc11" in title_l:
        parts.append("mc11")

    return "_".join(parts)


def _build_accesorio_model(brand: str, specs: dict, title: str) -> str:
    """Construye un nombre human-readable para accesorios.

    Filtros: '{Tipo descriptivo} {diametro}mm'
        - 'Polarizador circular 82mm'
        - 'Black Pro-Mist 1/4 82mm'
        - 'Variable ND 2-8 stops 82mm'

    Adaptadores: '{tipo} {mount_out} → {mount}' [+ identificador modelo]
        - 'MC-11 EF → E'
        - 'Speedbooster 0.71x EF → RF'
        - 'Drop-In EF → RF'
        - 'M42 → E'
    """
    title_l = title.lower()

    # ── Filtros ──────────────────────────────────────────────────────
    if specs.get("diametro_filtro") and not specs.get("lens_mount"):
        d = specs["diametro_filtro"]
        # Pro-Mist con grade
        m = re.search(r"grade\s*(\d+\s*/\s*\d+)", title, re.IGNORECASE)
        if m:
            return f"Black Pro-Mist {m.group(1)} {d}mm"
        tipo = (specs.get("filtro_subtipo") or "").lower()
        if "polariz" in tipo:
            return f"Polarizador circular {d}mm"
        if "variable" in tipo:
            dens = specs.get("densidad", "")
            if dens:
                return f"Variable ND {dens} {d}mm"
            return f"Variable ND {d}mm"
        if "nd" in tipo:
            return f"ND {d}mm"
        if "uv" in tipo:
            return f"UV {d}mm"
        return f"{specs.get('filtro_subtipo', 'Filtro')} {d}mm"

    # ── Adaptadores ─────────────────────────────────────────────────
    mount_out = specs.get("lens_mount_out", "")
    mount = specs.get("lens_mount", "")
    if mount_out and mount:
        arrow = f"{mount_out} → {mount}"
        # Detectar marca-modelo identificador
        if "mc-11" in title_l or "mc11" in title_l:
            return f"MC-11 {arrow}"
        if "speedbooster" in title_l or specs.get("adaptador_subtipo") == "Speedbooster":
            m = re.search(r"([\d.]+x)", title)
            ratio = f" {m.group(1)}" if m else ""
            return f"Speedbooster{ratio} {arrow}"
        if specs.get("incluye_iris") or "drop" in title_l:
            return f"Drop-In Filter Adapter {arrow}"
        return f"Adaptador {arrow}"

    return title  # fallback


def _to_int_str(n) -> str:
    """123.0 → '123'; 1.4 → '14' (sin punto)."""
    f = float(n)
    if f.is_integer():
        return str(int(f))
    return str(f).replace(".", "")


def map_lente_specs(secciones: dict, title: str = "") -> dict:
    """Mapea raw → spec_keys canónicos de Lentes (15 specs)."""
    result: dict = {}

    def _add(key, val):
        if val is not None and val != "" and val != []:
            result[key] = val

    _add("lens_mount", _normalize_mount(_find_value(secciones, "Lens Mount") or ""))
    _add("distancia_focal", _parse_focal_length(secciones))
    _add("apertura", _parse_apertura(secciones))
    _add("formato", _parse_lens_format(secciones))
    _add("diametro_filtro", _parse_filter_size(secciones))
    _add("linea", _parse_linea(title))
    _add("angulo_vision", _parse_angulo_vision(secciones))
    _add("distancia_minima_m", _parse_min_focus_cm(secciones))  # cm en spec_template
    _add("magnificacion", _parse_magnificacion(secciones))
    _add("hojas_diafragma", _parse_iris_blades(secciones))

    est = _parse_estabilizacion_lens(secciones)
    if est is not None:
        result["estabilizacion"] = est
    af = _parse_autofocus_lens(secciones)
    if af is not None:
        result["autofocus"] = af

    _add("construccion_optica", _parse_construccion_optica(secciones))
    _add("peso_g", _parse_peso_g(secciones))  # alineado a iluminación/cámaras (peso_g int)
    _add("dimensiones", _parse_dimensiones_lens(secciones))
    return result


def map_lente_extras(secciones: dict, title: str = "") -> dict:
    """Campos extra estructurados para ficha técnica de lentes."""
    result: dict = {}
    FIELD_MAP = [
        ("Image Stabilization",     "estabilizacion_sistema"),
        ("Focus Type",              "focus_type"),
        ("Tripod Mounting",         "tripod_mounting"),
        ("Lens Format Coverage",    "format_coverage_raw"),
        ("Magnification",           "magnificacion_raw"),
        ("Minimum Focus Distance",  "min_focus_raw"),
        ("Aperture",                "aperture_raw"),
        ("Aperture/Iris Blades",    "iris_blades_raw"),
        ("Optical Design",          "optical_design_raw"),
        ("Angle of View",           "angle_of_view_raw"),
        ("Filter Size",             "filter_size_raw"),
        ("Dimensions",              "dimensions_raw"),
        ("Weight",                  "weight_raw"),
        ("Package Weight",          "package_weight"),
        ("Box Dimensions (LxWxH)",  "box_dimensions"),
    ]
    for src, dst in FIELD_MAP:
        v = _find_value(secciones, src)
        if v:
            line = v.strip()
            if line.lower() not in ("no", "n/a", "none", "1 x", ""):
                result[dst] = line
    return result


# ─── Spec mappers: ACCESORIOS (filtros y adaptadores) ────────────────────

_FILTER_TYPE_MAP = [
    (r"circular\s*polariz", "Filtro polarizador"),
    (r"variable\s*nd|vari-?nd", "Filtro variable"),
    (r"\bnd\b", "Filtro ND"),
    (r"\buv\b", "Filtro UV"),
    (r"black\s*(?:pro-?)?mist|pro-?mist", "Filtro polarizador"),  # Pro-Mist técnicamente difusión, no polarizador
]


def _parse_filtro_tipo(secciones: dict, title: str = "") -> str | None:
    """Mapea Filter Type a enum del proyecto."""
    val = (_find_value(secciones, "Filter Type") or title).lower()
    # Pro-Mist es un filtro de difusión — no es polarizador. El enum no tiene
    # "difusión" — mejor lo dejamos como "Filtro polarizador" sería incorrecto.
    # Decisión: si es Pro-Mist, retornar string custom; el enum se puede extender
    # luego desde admin. Por ahora lo categorizamos como "Filtro UV" (la única
    # categoría enum genérica "no clasificable"). Mejor: extender el enum desde
    # spec_templates al ejecutar el seed.
    if re.search(r"black\s*(?:pro-?)?mist|pro-?mist", val):
        return "Filtro difusión"  # ← nueva opción enum que agrego al spec_template
    if re.search(r"variable\s*nd|vari-?nd", val):
        return "Filtro variable"
    if re.search(r"circular\s*polariz|\bcpl\b|\bcir\.?\s*pol", val):
        return "Filtro polarizador"
    if re.search(r"\bnd\b", val):
        return "Filtro ND"
    if re.search(r"\buv\b", val):
        return "Filtro UV"
    return None


def _parse_filtro_densidad(secciones: dict) -> str | None:
    val = _find_value(secciones, "Exposure Reduction", "Density")
    if not val:
        return None
    return val.strip()


def _parse_filtro_diametro(secciones: dict, title: str = "") -> int | None:
    val = _find_value(secciones, "Size", "Filter Size")
    if val:
        m = re.search(r"(\d+)\s*mm", val)
        if m:
            return int(m.group(1))
    # Fallback título "82mm"
    m = re.search(r"(\d+)\s*mm", title, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _parse_adaptador_tipo(secciones: dict) -> str | None:
    item = (_find_value(secciones, "Item Type") or "").lower()
    if "reducing" in item or "speedboost" in item:
        return "Speedbooster"
    if "lens mount adapter" in item or "mount adapter" in item:
        return "Adaptador montura"
    return None


def _parse_adaptador_electronica(secciones: dict) -> bool | None:
    val = _find_value(secciones, "Electronic Communication")
    if val is None:
        return None
    return val.strip().lower() in ("yes", "true", "sí", "si")


def _parse_adaptador_incluye_iris(secciones: dict) -> bool | None:
    item = (_find_value(secciones, "Item Type") or "").lower()
    return "drop-in filter" in item or "filter support" in item or "variable nd included" in item


def _parse_filtro_material(secciones: dict) -> str | None:
    val = (_find_value(secciones, "Filter Material") or "").lower()
    if not val:
        return None
    if "glass" in val or "vidrio" in val:
        return "Vidrio"
    if "resin" in val:
        return "Resina"
    if "polymer" in val or "polímer" in val or "polimer" in val:
        return "Polímero"
    return None


def _parse_filtro_grade(title: str) -> str | None:
    """Pro-Mist 1/4 → '1/4'; 1/8 → '1/8'; etc."""
    import re as _re
    m = _re.search(r"grade\s*(\d+\s*/\s*\d+|\d+)", title, _re.IGNORECASE)
    return m.group(1).replace(" ", "") if m else None


def map_filtro_specs(secciones: dict, title: str = "") -> dict:
    """Mapea raw → spec_keys de 'Filtros'. `diametro_filtro` es la MISMA spec
    que en Lentes — match automático cross-categoría vía el motor de compat."""
    result: dict = {}

    def _add(key, val):
        if val is not None and val != "" and val != []:
            result[key] = val

    _add("filtro_subtipo", _parse_filtro_tipo(secciones, title))
    _add("diametro_filtro", _parse_filtro_diametro(secciones, title))
    _add("densidad", _parse_filtro_densidad(secciones))
    _add("material", _parse_filtro_material(secciones))
    _add("grade", _parse_filtro_grade(title))
    _add("peso_g", _parse_peso_g(secciones))
    return result


def map_adaptador_specs(secciones: dict, title: str = "") -> dict:
    """Mapea raw → spec_keys de 'Adaptadores' (categoría raíz independiente)."""
    result: dict = {}

    def _add(key, val):
        if val is not None and val != "" and val != []:
            result[key] = val

    _add("adaptador_subtipo", _parse_adaptador_tipo(secciones))
    _add("lens_mount", _normalize_mount(_find_value(secciones, "Camera Compatibility") or ""))
    _add("lens_mount_out", _normalize_mount(_find_value(secciones, "Lens Compatibility") or ""))

    el = _parse_adaptador_electronica(secciones)
    if el is not None:
        result["electronica"] = el
    iris = _parse_adaptador_incluye_iris(secciones)
    if iris is not None:
        result["incluye_iris"] = iris

    # Magnificación: solo aplica a speedboosters
    mag = _parse_magnificacion(secciones)
    if mag and "x" in str(mag).lower():
        result["magnificacion"] = mag

    _add("peso_g", _parse_peso_g(secciones))
    return result


def map_accesorio_extras(secciones: dict, title: str = "") -> dict:
    """Extras para filtros y adaptadores."""
    result: dict = {}
    FIELD_MAP = [
        ("Item Type",                "item_type"),
        ("Filter Type",              "filter_type_raw"),
        ("Filter Material",          "filter_material"),
        ("Filter Thickness",         "filter_thickness"),
        ("Coating",                  "coating"),
        ("Exposure Reduction",       "exposure_reduction_raw"),
        ("Size",                     "size_raw"),
        ("Front Accessory Thread / Bayonet", "front_thread"),
        ("Ring Material",            "ring_material"),
        ("Materials",                "materiales"),
        ("Camera Compatibility",     "camera_compat_raw"),
        ("Lens Compatibility",       "lens_compat_raw"),
        ("Electronic Communication", "electronic_comm_raw"),
        ("Magnification",            "magnificacion"),
        ("Exposure Change",          "exposure_change"),
        ("Included Shims",           "included_shims"),
        ("Inputs/Outputs",           "inputs_outputs"),
        ("Dimensions",               "dimensions_raw"),
        ("Weight",                   "weight_raw"),
        ("Package Weight",           "package_weight"),
        ("Box Dimensions (LxWxH)",   "box_dimensions"),
    ]
    for src, dst in FIELD_MAP:
        v = _find_value(secciones, src)
        if v:
            line = v.strip()
            if line.lower() not in ("no", "n/a", "none", "1 x", ""):
                result[dst] = line
    return result


# ─── JSON-LD enrichment ─────────────────────────────────────────────────

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
            "distancia_minima_m, magnificacion, hojas_diafragma, estabilizacion, "
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

        # Dispatch a dataset correspondiente
        if clase == "lente":
            specs = map_lente_specs(result["secciones"], title=result["title"])
            extras = map_lente_extras(result["secciones"], title=result["title"])
            curado_target = lentes_curado
            raw_target = lentes_raw
            prod_id = _build_lens_id(result["marca"], specs, result["title"])
            raw_entry["categoria_raiz"] = "Lentes"
        elif clase == "filtro":
            specs = map_filtro_specs(result["secciones"], title=result["title"])
            extras = map_accesorio_extras(result["secciones"], title=result["title"])
            prod_id = _build_filter_id(result["marca"], specs, result["title"])
            result["modelo"] = _build_accesorio_model(result["marca"], specs, result["title"])
            curado_target = filtros_curado
            raw_target = filtros_raw
            raw_entry["categoria_raiz"] = "Filtros"
        else:  # adaptador
            specs = map_adaptador_specs(result["secciones"], title=result["title"])
            extras = map_accesorio_extras(result["secciones"], title=result["title"])
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
            "extras": extras,
            "ficha": result["secciones"],
        }
        print(f"  + {clase} agregado ({prod_id}) — {len(specs)} specs, {len(extras)} extras")

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
