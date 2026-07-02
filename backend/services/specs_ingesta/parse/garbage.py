"""parse/garbage.py — Filtro de valores "basura" en HTML de producto (B&H y otros).

Antes: 3 implementaciones divergentes con drift real de comportamiento —
generic_html_extractor tenía `{"1 x", "1x", "—", "-", "n/a", "", "not specified"}`
(case-insensitive, vía .lower() antes de comparar); luces_html_extractor tenía
`{"1 x", "1x", ":", "—", "-", "N/A", "n/a", ""}` (case-SENSITIVE, por eso
necesitaba las dos variantes de mayúscula); equipo_html_extractor tenía inline
`v not in ("1 x", "—", "n/a")` (ni siquiera cubría "1x"/":"/"-"/"N/A"/"not specified").

Acá hay UNA sola: unión de los 3 sets + comparación case-insensitive (más
robusta que cualquiera de las 3 — ya no hace falta declarar "N/A" Y "n/a")."""

from __future__ import annotations

_GARBAGE_VALUES = frozenset({"1 x", "1x", "—", "-", ":", "n/a", ""})


def is_garbage(value: str) -> bool:
    v = (value or "").strip().lower()
    return v in _GARBAGE_VALUES or v.startswith("not specified")
