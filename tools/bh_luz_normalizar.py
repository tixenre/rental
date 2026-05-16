#!/usr/bin/env python3
"""
tools/bh_luz_normalizar.py — Normalización post-parse del dataset de luces.

Toma docs/bh_luces_curado.json y docs/bh_specs_relevamiento.json,
aplica reglas de canonicalización y guarda los archivos normalizados.

Reglas que aplica:
  1. Marcas canónicas (Mole-Richardson, Aputure, etc.) — case y guiones consistentes
  2. Modelos limpios (quita "(Gray)", "RGB LED Monolight", redundancias, etc.)
  3. IDs estables y específicos (nanlite_forza → nanlite_forza_500)
  4. extras de cleanup (None/"" → eliminar)
  5. Orden consistente de campos
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
CURADO_PATH = ROOT / "docs" / "bh_luces_curado.json"
RAW_PATH = ROOT / "docs" / "bh_specs_relevamiento.json"


# ── Marcas canónicas ────────────────────────────────────────────────────────

BRAND_CANON = {
    "amaran": "Amaran",
    "aputure": "Aputure",
    "godox": "Godox",
    "nanlite": "Nanlite",
    "mole-richardson": "Mole-Richardson",
    "mole richardson": "Mole-Richardson",
    "molerichardson": "Mole-Richardson",
    "arri": "ARRI",
}


def canon_brand(brand: str) -> str:
    key = brand.strip().lower()
    return BRAND_CANON.get(key, brand.strip())


# ── Limpieza de modelo ──────────────────────────────────────────────────────

# Frases redundantes que NO aportan info (ya están en `tipo` o `specs`)
# Orden importa: patrones largos PRIMERO para que coincidan antes que los cortos.
MODEL_NOISE_PHRASES = [
    # Frases largas — primero
    r"\bOn-Camera\s+Video\s+LED\s+Light\b",
    r"\bRGB\s+LED\s+Monolight\b",
    r"\bRGB\s+LED\s+Tube\s+Light\b",
    r"\bLED\s+RGBWW\s+Light\b",
    r"\bDaylight\s+LED\s+Monolight\b",
    r"\bBi-Color\s+LED\s+(?:Monolight|Spotlight|Flexible\s+Mat|Light\s+Panel)\b",
    r"\bTunable\s+Color\s+LED\s+Light\s+Panel\b",
    r"\b(?:Video|Studio)\s+LED\s+Light\b",
    r"\bLED\s+Light\s+Panel\b",
    r"\bLED\s+Light\s+Tube(?:/Wand)?\b",
    r"\bLED\s+Flexible\s+(?:Light|Mat)\b",
    r"\bFlash\s+for\s+(?:Sony|Canon|Nikon|Fuji|Olympus)\b",
    r"\bTungsten\s+Fresnel(?:\s+Spotlight)?\b",
    r"\bFresnel\s+with\s+DMX\b",
    # Frases medias
    r"\bLED\s+Monolight\b",
    r"\bLED\s+Spotlight\b",
    r"\bLED\s+Lamp\b",
    r"\bLED\s+Light\b",
    r"\bLight\s+Panel\b",
    r"\bTube\s+Light\b",
    r"\bVideo\s+Light\b",
    # Palabras solas — al final
    r"\bMonolight\b",
    r"\bSpotlight\b",
    r"\bFresnel\b",
    r"\bPanel\b",
]

# Parentéticos a remover del modelo
MODEL_PARENS_NOISE = [
    r"\s*\(Gray\)\s*",
    r"\s*\(Black\)\s*",
    r"\s*\(V-Mount\)\s*",
    r"\s*\(V100S\)\s*",
    r"\s*\(\d+W\)\s*",  # "(320W)"
    r"\s*\([\d.]+'\)\s*",  # "(2.5')"
]


def canon_modelo(modelo: str) -> str:
    s = modelo
    # Quitar parentéticos ruidosos
    for pat in MODEL_PARENS_NOISE:
        s = re.sub(pat, " ", s)
    # Quitar frases redundantes
    for pat in MODEL_NOISE_PHRASES:
        s = re.sub(pat, " ", s, flags=re.IGNORECASE)
    # Quitar "LED" suelta al final (ej. "VL150 LED" → "VL150")
    s = re.sub(r"\s+LED\s*$", "", s, flags=re.IGNORECASE)
    # Quitar SKU duplicado al final (ej. "V100 V100S" → "V100")
    parts = s.split()
    while len(parts) >= 2:
        last = parts[-1].upper()
        prev_str = " ".join(parts[:-1]).upper()
        # Si el último contiene completo al penúltimo (V100 → V100S) o viceversa
        if any(last.startswith(p.upper()) for p in parts[:-1] if len(p) >= 3):
            parts = parts[:-1]
        else:
            break
    s = " ".join(parts)
    # Collapse whitespace, normalizar separadores
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ── IDs canónicos ───────────────────────────────────────────────────────────

# Mapeo manual de IDs ambiguos a IDs específicos
ID_REMAP = {
    "nanlite_forza": "nanlite_forza_500",
    "nanlite_60b": "nanlite_forza_60b",
    "aputure_nova": "aputure_nova_ii_2x1",
    "molerichardson_juniorled": "molerichardson_juniorled_200",
}


def canon_id(pid: str) -> str:
    return ID_REMAP.get(pid, pid)


# ── Limpieza de extras ──────────────────────────────────────────────────────

def clean_extras(extras: dict) -> dict:
    """Filtra valores vacíos/basura del dict de extras."""
    cleaned = {}
    for k, v in extras.items():
        if v is None or v == "" or v == "—":
            continue
        if isinstance(v, str):
            v_clean = v.strip()
            if v_clean.lower() in ("1 x", "1x", "n/a", "no", "none", ":"):
                continue
            if v_clean.lower().startswith("not specified"):
                continue
            cleaned[k] = v_clean
        else:
            cleaned[k] = v
    return cleaned


# ── Reordenar specs (orden visual canónico) ──────────────────────────────────

SPECS_ORDER = [
    "potencia_w", "lumens", "cri", "temperatura_k",
    "bicolor", "rgb", "dimming",
    "control_inalambrico", "alimentacion", "montaje", "peso",
]

EXTRAS_ORDER = [
    "tipo", "item_type", "bulb_type", "base_type",
    "beam_angle", "cooling", "ip_rating",
    "dimensiones", "photometrics_1m",
    "cri", "tlci",
    "display", "app_compatible",
    "modificador_incluido", "case_incluido",
    "vida_util_horas",
    "yoke", "fixture_mount", "accessory_diameter",
    "wireless_range", "io", "cable_length",
    "voltaje", "materiales", "certificaciones", "reflector", "serie",
]


def reorder(d: dict, order: list[str]) -> dict:
    out = {}
    for k in order:
        if k in d:
            out[k] = d[k]
    # Mantener otros que no están en el orden
    for k, v in d.items():
        if k not in out:
            out[k] = v
    return out


# ── Main ────────────────────────────────────────────────────────────────────

def normalizar():
    with open(CURADO_PATH) as f:
        curado = json.load(f)
    with open(RAW_PATH) as f:
        raw = json.load(f)

    new_products = {}
    id_remaps_applied = []

    for old_id, p in curado["products"].items():
        new_id = canon_id(old_id)
        if new_id != old_id:
            id_remaps_applied.append((old_id, new_id))

        # Normalizar campos
        p["marca"] = canon_brand(p.get("marca", ""))
        p["modelo"] = canon_modelo(p.get("modelo", ""))
        p["specs"] = reorder(p.get("specs", {}), SPECS_ORDER)
        p["extras"] = reorder(clean_extras(p.get("extras", {})), EXTRAS_ORDER)
        # Reorder top-level
        ordered = {
            "marca": p["marca"],
            "modelo": p["modelo"],
            "url_source": p.get("url_source", ""),
        }
        for k in ("specs", "extras", "ficha", "_nota"):
            if k in p:
                ordered[k] = p[k]
        new_products[new_id] = ordered

    curado["products"] = new_products

    # Aplicar mismos remaps al raw
    for old_id, new_id in id_remaps_applied:
        for rp in raw["products"]:
            if rp.get("id") == old_id:
                rp["id"] = new_id
        print(f"  ID remapped: {old_id} → {new_id}")

    # Normalizar marcas también en raw
    for rp in raw["products"]:
        rp["marca"] = canon_brand(rp.get("marca", ""))

    with open(CURADO_PATH, "w") as f:
        json.dump(curado, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(RAW_PATH, "w") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nNormalización aplicada: {len(curado['products'])} productos")


if __name__ == "__main__":
    normalizar()
