"""
services/spec_render.py — Fuente de verdad para renderizar specs.

Centraliza el formateo de valores de spec a texto para los placeholders
`{spec:Label}`, `{spec:Label.colKey}` y `{spec:Label.colKey[i]}` del nombre
público, y para la ficha pública del equipo.

Antes esta lógica vivía duplicada en `routes/equipos.py` y
`services/nombre_builder.py` con nombres distintos pero algoritmo idéntico.
Y un mirror más en TypeScript (`src/lib/equipment/nombre-template.ts`).
Acá vive la canónica; el mirror TS sigue la misma `output_config`.

Convención de `output_config`:
    {
        "row_strategy": "all" | "first" | "last"
    }

`row_strategy` solo aplica a specs tipo 'tabla'. NULL u omitido → "all".
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Optional


# ── Helpers básicos ─────────────────────────────────────────────────────


def norm_spec_label(s: str) -> str:
    """Normaliza un label para lookup: lowercase + sin tildes + trim.
    Tiene que matchear `normalizeLabel` del frontend (nombre-template.ts).
    """
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().strip()


def format_tabla_cell(cell: Any) -> str:
    """Formatea una celda de spec tabla a texto. Soporta valor_unidad
    (`{valor, unidad}` → "19389 lm") y escalares."""
    if cell is None or cell == "":
        return ""
    if isinstance(cell, dict) and "valor" in cell:
        valor = cell.get("valor")
        unidad = cell.get("unidad") or ""
        txt = str(valor) if valor is not None else ""
        if unidad:
            txt = f"{txt} {str(unidad).strip()}".strip()
        return txt.strip()
    return str(cell).strip()


def _apply_row_strategy(rows: list, output_config: Optional[dict]) -> list:
    """Filtra las filas según `output_config.row_strategy`."""
    if not rows:
        return rows
    strategy = (output_config or {}).get("row_strategy") or "all"
    if strategy == "first":
        return rows[:1]
    if strategy == "last":
        return rows[-1:]
    return rows


def format_tabla_value(
    value_json: str,
    columnas: list,
    output_config: Optional[dict] = None,
) -> str:
    """Formatea el JSON serializado de una spec tabla a texto legible.
    Usa las columnas (con prefijo/unidad) para construir la oración:
    "10000 lm a 5700 K". Múltiples filas se separan con \\n.
    Aplica `output_config.row_strategy` para limitar a primera/última fila.
    Si el formato falla, devuelve el value original."""
    try:
        rows = json.loads(value_json)
    except Exception:
        return value_json
    if not isinstance(rows, list) or not rows:
        return value_json
    rows = _apply_row_strategy(rows, output_config)
    cols = columnas or []
    lines: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parts: list[str] = []
        for i, c in enumerate(cols):
            key = c.get("key") if isinstance(c, dict) else None
            if not key:
                continue
            cell = row.get(key)
            if cell is None or cell == "":
                continue
            prefijo = c.get("prefijo") if isinstance(c, dict) else None
            if i > 0 and prefijo:
                parts.append(str(prefijo))
            txt = format_tabla_cell(cell)
            # Si la columna tiene unidad fija (no valor_unidad), sufijarla.
            fixed_unit = c.get("unidad") if isinstance(c, dict) else None
            if fixed_unit and c.get("tipo") != "valor_unidad" and not isinstance(cell, dict):
                txt = f"{txt} {fixed_unit}".strip()
            if txt:
                parts.append(txt)
        if parts:
            lines.append(" ".join(parts))
    return "\n".join(lines) if lines else value_json


# ── Resolver de placeholder ────────────────────────────────────────────


_RE_COL_INDEX = re.compile(r"^(.+?)\[(\d+)\]$")


def _parse_path(path: str) -> tuple[Optional[str], int]:
    """Parsea `colKey` o `colKey[i]`. Devuelve (col_key, row_idx)."""
    m = _RE_COL_INDEX.match(path)
    if m:
        return m.group(1), int(m.group(2))
    return path or None, 0


def render_spec_placeholder(
    value: str,
    tipo: Optional[str],
    tabla_columnas: Optional[list],
    output_config: Optional[dict],
    path: str = "",
) -> str:
    """Resuelve un placeholder de spec.

    - `path == ""` (placeholder es `{spec:Label}`):
        * Si tipo == 'tabla', formatea con conectores aplicando row_strategy.
        * Si no, devuelve el value tal cual.
    - `path == "colKey"` o `"colKey[i]"`:
        * Solo aplica a tipo tabla. Extrae la celda colKey de la fila i.
        * Sin índice explícito, usa fila 0 (no se aplica row_strategy: el
          path explícito gana sobre la config).
    """
    if not path:
        if tipo == "tabla":
            return format_tabla_value(value or "", tabla_columnas or [], output_config)
        return value or ""
    if not value or not (value.startswith("[") or value.startswith("{")):
        return ""
    col_key, row_idx = _parse_path(path)
    if not col_key:
        return ""
    try:
        parsed = json.loads(value)
    except Exception:
        return ""
    if not isinstance(parsed, list) or row_idx >= len(parsed):
        return ""
    row = parsed[row_idx]
    if not isinstance(row, dict):
        return ""
    return format_tabla_cell(row.get(col_key))
