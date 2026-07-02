"""parsers/lentes.py — Mappers de specs para Lentes, Filtros y Adaptadores.

Movido verbatim de tools/lentes_parser.py (F3 del rediseño de ingesta) — la
lógica de mapeo + clasificación + IDs estables (usados por equipo_html_extractor
para el prod_id/modelo del form); parse_html/main/load_*/save_*/jsonld_*
(CLI + I/O de docs/lentes*.json) quedan en tools/lentes_parser.py.

Único parser que clasifica internamente (_classify: lente/filtro/adaptador
por presencia de "Focal Length"/"Filter Type"/"Mount Type") y produce 3
categorías desde una sola pasada.

Entry points: map_lente_specs, map_filtro_specs, map_adaptador_specs,
map_lente_extras, map_accesorio_extras — todos (secciones, title) -> dict.
_classify(secciones, title) -> "lente"|"filtro"|"adaptador"|None."""

from __future__ import annotations

import re

from .base import _find_value, _parse_peso_g


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
    _add("distancia_minima_cm", _parse_min_focus_cm(secciones))  # valor en cm (key canónica)
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
    _add("dimensions_mm", _parse_dimensiones_lens(secciones))
    return result


def map_lente_extras(secciones: dict, title: str = "") -> dict:
    """Campos extra estructurados para ficha técnica de lentes."""
    result: dict = {}
    FIELD_MAP = [
        ("Image Stabilization",     "estabilizacion_sistema"),
        # focus_type eliminado del registry (duplicaba el bool `autofocus`).
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


def _parse_filtro_light_loss(secciones: dict) -> float | None:
    """'Exposure Reduction: 1.2-Stop' → 1.2 (en stops). Mismo patrón que
    modificadores._parse_light_loss. Se usa para filtros NO-ND (polarizador/
    difusión/UV) — ahí la pérdida de luz es una propiedad incidental, no la
    "densidad ND" del producto (ver map_filtro_specs: gatea por subtipo)."""
    val = _find_value(secciones, "Exposure Reduction")
    if not val:
        return None
    m = re.search(r"([\d.]+)\s*-?\s*stop", val, re.IGNORECASE)
    return float(m.group(1)) if m else None


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

    subtipo = _parse_filtro_tipo(secciones, title)
    _add("filtro_subtipo", subtipo)
    _add("diametro_filtro", _parse_filtro_diametro(secciones, title))
    # "Exposure Reduction" es el mismo raw label para dos conceptos
    # distintos según el subtipo — ver el comentario de light_loss_stops
    # en el registry (services/specs/registry/catalogo/filtros.py).
    if subtipo in ("Filtro ND", "Filtro variable"):
        _add("densidad", _parse_filtro_densidad(secciones))
    else:
        _add("light_loss_stops", _parse_filtro_light_loss(secciones))
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
