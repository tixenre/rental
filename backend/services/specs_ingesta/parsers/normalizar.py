"""parsers/normalizar.py — Canonicalización de identidad (marca/modelo/extras).

Movido verbatim de tools/iluminacion_normalizar.py (F3 del rediseño de
ingesta) — solo las 3 funciones que usa el código en vivo (canon_brand,
canon_modelo, clean_extras). canon_id/canonicalizar_specs/reorder/normalizar
(orquestación del dataset completo, I/O de docs/iluminacion*.json) quedan en
tools/iluminacion_normalizar.py — solo las usa el CLI offline.

camaras_normalizar.py y lentes_normalizar.py (tools/) NO tienen equivalente
acá todavía — ningún código en vivo los importa hoy (confirmado F3); si se
cablean a futuro, se suman a este mismo archivo."""

from __future__ import annotations

import re


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
