"""services/spec_coerce.py — Coerción de valores crudos al tipo canónico del registry.

Convierte strings de origen externo (B&H HTML, JSON-LD, parser) al formato
TEXT canónico de equipo_specs.value, guiado por el tipo/unidad/enum_options
del spec_def.

Diseño:
- `coerce_and_serialize(raw, tipo, unidad, enum_options_json)` → str | None
  Devuelve None si la coerción falla; el llamador usa el raw como fallback.
- `derive_lumens_from_lux(lux, beam_angle_deg)` → int | None
  Derivación fotométrica: lux a 1m + ángulo de haz → lúmenes totales.
  Se usa como post-proceso en _matchear_y_persistir_specs cuando el HTML
  tiene datos de lux pero no reporta lúmenes directamente.

El inverso (valor canónico → display humano) vive en spec_render.py.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any


_TRUE_VALS = frozenset({"yes", "si", "sí", "true", "1", "y", "verdadero", "on", "enabled"})
_FALSE_VALS = frozenset({"no", "false", "0", "n", "falso", "off", "disabled"})


def coerce_and_serialize(
    raw: Any,
    tipo: str,
    unidad: str | None = None,  # noqa: ARG001 — reservado para futura lógica de unidad
    enum_options_json: Any = None,
) -> str | None:
    """Coerce raw value from HTML/parser to canonical TEXT for equipo_specs.value.

    Returns None if coercion fails (caller should fall back to raw string).
    """
    if raw is None:
        return None
    raw_str = str(raw).strip()
    if not raw_str:
        return None

    try:
        if tipo == "number":
            return _coerce_number(raw_str)
        if tipo == "bool":
            return _coerce_bool(raw_str)
        if tipo == "enum":
            return _coerce_enum(raw_str, _parse_opts(enum_options_json))
        if tipo == "rango":
            return _coerce_rango(raw_str)
        if tipo == "multi_enum":
            return _coerce_multi_enum(raw_str, _parse_opts(enum_options_json))
        # string: passthrough
        return raw_str
    except Exception:
        return None


def derive_lumens_from_lux(lux: float, beam_angle_deg: float) -> int | None:
    """Calcula lúmenes desde iluminancia a 1m y ángulo de haz (sin modificador).

    Fórmula punto-a-cono: Lumens = Lux × 2π × (1 − cos(θ/2))
    donde θ/2 es el semi-ángulo en radianes. Válida para d = 1m.
    Convención: el valor de lux debe ser SIN modificador (fixture desnudo).
    """
    if lux <= 0 or beam_angle_deg <= 0 or beam_angle_deg > 360:
        return None
    half_rad = math.radians(beam_angle_deg / 2)
    lumens = lux * 2 * math.pi * (1 - math.cos(half_rad))
    return max(1, round(lumens))


# ── helpers internos ─────────────────────────────────────────────────────────


def _parse_opts(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _coerce_number(s: str) -> str | None:
    """Extrae el primer número del string; descarta prefijo/sufijo de unidad."""
    m = re.search(r"-?\d+(?:[.,]\d+)?", s)
    if not m:
        return None
    val = float(m.group().replace(",", "."))
    return str(int(val)) if val == int(val) else str(val)


def _coerce_bool(s: str) -> str | None:
    low = s.lower().strip()
    if low in _TRUE_VALS:
        return "true"
    if low in _FALSE_VALS:
        return "false"
    return None


def _coerce_enum(s: str, opts: list[str]) -> str | None:
    if not opts:
        return None
    low = s.lower().strip()
    # Exact match (case-insensitive)
    for opt in opts:
        if opt.lower() == low:
            return opt
    # Substring: opt is inside input ("Wi-Fi" in "Wi-Fi 6 (802.11ax)").
    # First match in list order wins.
    for opt in opts:
        if opt.lower() in low:
            return opt
    return None


def _coerce_rango(s: str) -> str | None:
    """Parsea '24-70mm', 'f/2.8-4', '50mm', '2.8' → JSON array [min,max] o [v]."""
    # Eliminar prefijo de unidad tipo "f/" al inicio
    s = re.sub(r"^f/", "", s.strip(), flags=re.IGNORECASE)
    # Eliminar sufijo de unidad al final (letras, °, etc.)
    s = re.sub(r"[a-zA-Z°/]+\s*$", "", s.strip()).strip()

    # Formato "min-max" (guion ascii o dash unicode)
    m = re.match(r"^(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)$", s)
    if m:
        lo = float(m.group(1).replace(",", "."))
        hi = float(m.group(2).replace(",", "."))
        return json.dumps([_clean_num(lo), _clean_num(hi)])

    # Valor simple
    m = re.match(r"^(\d+(?:[.,]\d+)?)$", s)
    if m:
        v = float(m.group(1).replace(",", "."))
        return json.dumps([_clean_num(v)])

    return None


def _coerce_multi_enum(s: str, opts: list[str]) -> str | None:
    # Parse input to a flat list of parts (JSON array or CSV/slash separated)
    if s.startswith("["):
        try:
            vals = json.loads(s)
            parts = [str(v).strip() for v in vals if str(v).strip()]
        except Exception:
            parts = [p.strip() for p in re.split(r"[,/]", s) if p.strip()]
    else:
        parts = [p.strip() for p in re.split(r"[,/]", s) if p.strip()]

    if not parts:
        return None

    if opts:
        # Fuzzy-match each part via _coerce_enum (exact first, then substring).
        # Parts that don't map to any option are silently discarded — never 400.
        matched: list[str] = []
        seen: set[str] = set()
        for p in parts:
            m = _coerce_enum(p, opts)
            if m is not None and m not in seen:
                seen.add(m)
                matched.append(m)
        return json.dumps(matched) if matched else None

    # No opts declared → passthrough raw parts (unchanged behaviour)
    return json.dumps(parts)


def _clean_num(v: float) -> int | float:
    return int(v) if v == int(v) else v
