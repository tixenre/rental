#!/usr/bin/env python3
"""
tools/lentes_normalizar.py — Normalización post-parse de lentes + accesorios.

Aplica:
  1. Marcas canónicas (Sony, Canon, Sigma, Tiffen, etc.)
  2. Modelos limpios (sin "Lens", "for Canon EF" redundante)
  3. IDs estables (sigma_18-35, canon_ef_70-200, etc.)
  4. Cleanup de extras vacíos
  5. Reorden por relevancia

Procesa AMBOS datasets (docs/lentes.json y docs/accesorios.json) en una pasada.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

DATASETS = [
    ("lente",     ROOT / "docs" / "lentes.json",      ROOT / "docs" / "lentes_raw.json"),
    ("adaptador", ROOT / "docs" / "adaptadores.json", ROOT / "docs" / "adaptadores_raw.json"),
    ("filtro",    ROOT / "docs" / "filtros.json",     ROOT / "docs" / "filtros_raw.json"),
]


# ── Marcas canónicas ────────────────────────────────────────────────────

BRAND_CANON = {
    "sony": "Sony",
    "canon": "Canon",
    "nikon": "Nikon",
    "sigma": "Sigma",
    "tamron": "Tamron",
    "zeiss": "Carl Zeiss",
    "carl": "Carl Zeiss",  # "Carl Zeiss Jena" → primer word es "Carl"
    "leica": "Leica",
    "tiffen": "Tiffen",
    "hoya": "Hoya",
    "b+w": "B+W",
    "nisi": "NiSi",
    "polarpro": "PolarPro",
    "meike": "Meike",
    "vello": "Vello",
    "viltrox": "Viltrox",
    "metabones": "Metabones",
    "fotodiox": "Fotodiox",
    "kipon": "Kipon",
    "novoflex": "Novoflex",
    "fujifilm": "Fujifilm",
}


def canon_brand(brand: str) -> str:
    key = brand.strip().lower()
    return BRAND_CANON.get(key, brand.strip())


# ── Modelo cleanup ──────────────────────────────────────────────────────

# Frases redundantes a quitar del modelo (largas primero)
MODEL_NOISE_PHRASES = [
    # Frases compuestas
    r"\bDigital\s+Lens\s+Mount\s+Adapter\b",
    r"\bLens\s+Mount\s+Adapter\b",
    r"\bMount\s+Converter\s*/\s*Lens\s+Adapter\b",
    r"\bMount\s+Converter\b",
    r"\bDrop-?In\s+Filter\s+Mount\s+Adapter\b",
    r"\bSpeedbooster\s+Adapter\s+for\s+\w+\s+Lens\s+to\s+\w+\s+(?:Cameras?|Mount)\b",
    r"\bAdapter\s+for\s+\w+(?:\s+\w+)?\s+Lens\s+to\s+\w+\s+(?:Cameras?|Mount)\b",
    r"\bfor\s+\w+\s+(?:Cameras?|Mount)\b",
    # Genéricos al final
    r"\bCamera\s+Lens\b",
    r"\bfor\s+Canon\s+EF(?:-S)?\b",
    r"\bfor\s+Sony\s+E\b",
    r"\bfor\s+Nikon\s+Z\b",
    r"\b\(?Sony\s+E\)?\b",
    r"\b\(?Canon\s+EF(?:-S)?\)?\b",
    r"\b\(?Canon\s+RF\)?\b",
    # Lens al final / Filter al final (preservando "Filter" descriptivo en filtros)
    r"\bLens\b",  # se podría preservar en algunos pero ya está claro por categoría
]

# Parentéticos a remover
MODEL_PARENS_NOISE = [
    r"\s*\(Black\)\s*",
    r"\s*\(Gray\)\s*",
    r"\s*\(Silver\)\s*",
    r"\s*\(Sony\s+E\)\s*",
    r"\s*\(Canon\s+EF(?:-S)?\)\s*",
    r"\s*\(Canon\s+RF\)\s*",
    r"\s*\([^)]*Body[^)]*\)\s*",
    r"\s*\([^)]*Kit[^)]*\)\s*",
]


def canon_modelo(modelo: str) -> str:
    s = modelo
    for pat in MODEL_PARENS_NOISE:
        s = re.sub(pat, " ", s)
    for pat in MODEL_NOISE_PHRASES:
        s = re.sub(pat, " ", s, flags=re.IGNORECASE)

    # Quitar SKUs al final (token aislado al final del string).
    # IMPORTANTE: cada patrón requiere que el SKU sea su propio token (con
    # leading \s+) para no comerse partes del modelo real.
    s = re.sub(r"\s+[A-Z][A-Z0-9]*-[A-Z0-9-]+\s*$", "", s)  # ej. SEL-1234
    s = re.sub(r"\s+\d{6,}\s*$", "", s)  # SKU numérico largo (576954)
    # SKU tipo Canon "2569A004": dígitos+letra+dígitos. Requerimos
    # que el primer grupo de dígitos sea EXACTAMENTE 4 y la letra UNA sola
    # mayúscula, para no comer "16-35mm" o "70-200mm".
    s = re.sub(r"\s+\d{4}[A-Z]\d{2,4}\s*$", "", s)  # 2569A004
    # SKU "210-101" estilo Sigma — exactamente 3+3 dígitos
    s = re.sub(r"\s+\d{3}-\d{3}\s*$", "", s)
    # SKU largo alfanumérico tipo "SEL2470GM2" — 7+ chars, mezcla letras+dígitos
    s = re.sub(r"\s+(?=[A-Z0-9]{7,}\s*$)(?=.*\d)(?=.*[A-Z])[A-Z0-9]+\s*$", "", s)

    # Compactar
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ── IDs canónicos ───────────────────────────────────────────────────────

# IDs remapeados — el parser ahora usa _build_lens_id / _build_filter_id /
# _build_adapter_id que producen IDs estables. Este dict queda vacío como
# escape hatch para casos edge futuros (cuando aparezca una lente cuyo ID
# auto-generado necesite override manual).
ID_REMAP: dict[str, str] = {}


def canon_id(pid: str) -> str:
    return ID_REMAP.get(pid, pid)


# ── Limpieza de extras ──────────────────────────────────────────────────

def clean_extras(extras: dict) -> dict:
    """Filtra valores basura de extras. Lógica simple post-audit fix B3."""
    cleaned = {}
    GARBAGE = {"1 x", "1x", "n/a", "no", "none", ":", "yes", ""}
    for k, v in extras.items():
        if v is None or v == "" or v == "—":
            continue
        if isinstance(v, str):
            vc = v.strip()
            if vc.lower() in GARBAGE:
                continue
            if vc.lower().startswith("not specified"):
                continue
            cleaned[k] = vc
        else:
            cleaned[k] = v
    return cleaned


# ── Reorden ─────────────────────────────────────────────────────────────

LENTE_SPECS_ORDER = [
    "lens_mount", "distancia_focal", "apertura", "formato",
    "diametro_filtro", "linea",
    "angulo_vision", "distancia_minima_m", "magnificacion",
    "hojas_diafragma",
    "estabilizacion", "autofocus",
    "construccion_optica",
    "peso_g", "dimensions_mm",
]

ADAPTADOR_SPECS_ORDER = [
    "adaptador_subtipo", "lens_mount", "lens_mount_out",
    "electronica", "incluye_iris", "magnificacion",
    "peso_g",
]

FILTRO_SPECS_ORDER = [
    "filtro_subtipo", "diametro_filtro", "densidad",
    "material", "grade", "peso_g",
]

LENTE_EXTRAS_ORDER = [
    "estabilizacion_sistema",
    "format_coverage_raw", "aperture_raw", "iris_blades_raw",
    "optical_design_raw", "angle_of_view_raw",
    "filter_size_raw", "min_focus_raw", "magnificacion_raw",
    "tripod_mounting",
    "dimensions_raw", "weight_raw",
    "package_weight", "box_dimensions",
]

ADAPTADOR_EXTRAS_ORDER = [
    "item_type",
    "camera_compat_raw", "lens_compat_raw",
    "electronic_comm_raw", "magnificacion",
    "exposure_change", "included_shims",
    "materiales", "inputs_outputs",
    "dimensions_raw", "weight_raw",
    "package_weight", "box_dimensions",
]

FILTRO_EXTRAS_ORDER = [
    "item_type",
    "filter_type_raw", "filter_material", "filter_thickness",
    "coating", "exposure_reduction_raw",
    "size_raw", "front_thread", "ring_material",
    "package_weight", "box_dimensions",
]


def reorder(d: dict, order: list[str]) -> dict:
    out = {}
    for k in order:
        if k in d:
            out[k] = d[k]
    for k, v in d.items():
        if k not in out:
            out[k] = v
    return out


# ── Main ────────────────────────────────────────────────────────────────

def normalizar_dataset(curado_path: Path, raw_path: Path, kind: str):
    """Normaliza un dataset. kind: 'lente' | 'adaptador' | 'filtro'."""
    if not curado_path.exists():
        print(f"  WARN: {curado_path.name} no existe — skip")
        return

    with open(curado_path) as f:
        curado = json.load(f)
    with open(raw_path) as f:
        raw = json.load(f)

    if kind == "lente":
        specs_order = LENTE_SPECS_ORDER
    elif kind == "adaptador":
        specs_order = ADAPTADOR_SPECS_ORDER
    else:  # filtro
        specs_order = FILTRO_SPECS_ORDER

    new_products = {}
    id_remaps = []

    for old_id, p in curado["products"].items():
        new_id = canon_id(old_id)
        if new_id != old_id:
            id_remaps.append((old_id, new_id))

        p["marca"] = canon_brand(p.get("marca", ""))
        p["modelo"] = canon_modelo(p.get("modelo", ""))
        p["specs"] = reorder(p.get("specs", {}), specs_order)
        # `extras` removido del output (no se persistía a DB).
        p.pop("extras", None)

        ordered = {
            "marca": p["marca"],
            "modelo": p["modelo"],
            "url_source": p.get("url_source", ""),
            "image_url": p.get("image_url", ""),
        }
        for k in ("specs", "extras", "ficha", "_nota"):
            if k in p:
                ordered[k] = p[k]
        new_products[new_id] = ordered

    curado["products"] = new_products

    for old_id, new_id in id_remaps:
        for rp in raw.get("products", []):
            if rp.get("id") == old_id:
                rp["id"] = new_id
        print(f"    ID remapped: {old_id} → {new_id}")

    for rp in raw.get("products", []):
        rp["marca"] = canon_brand(rp.get("marca", ""))

    with open(curado_path, "w") as f:
        json.dump(curado, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(raw_path, "w") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"  → {curado_path.name}: {len(curado['products'])} productos")


def normalizar():
    for kind, curado, raw in DATASETS:
        print(f"Normalizando {kind}s:")
        normalizar_dataset(curado, raw, kind=kind)


if __name__ == "__main__":
    normalizar()
