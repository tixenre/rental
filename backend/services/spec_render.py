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


def _is_prefix_unit(unidad: Optional[str]) -> bool:
    """Unidades que van PEGADAS antes del número (f/, $, €) en vez de después.
    Convención: termina en "/" o empieza con símbolo monetario. Espejo de
    `isPrefixUnit` del frontend (SpecsDiffEditor.tsx)."""
    u = (unidad or "").strip()
    if not u:
        return False
    return u.endswith("/") or u[:1] in "$€£¥"


def _apply_unit(text: str, unidad: Optional[str]) -> str:
    """Pega la unidad al valor según su estilo:
    - prefijo pegado: `f/`, `$` → "f/2.8", "$100"
    - prefijo con espacio: `ISO` → "ISO 80 - 102400"
    - sufijo pegado: `°` → "84°"
    - sufijo con espacio (default): mm, g, W, K, fps… → "640 g"
    """
    u = (unidad or "").strip()
    if not u or not text:
        return text
    if _is_prefix_unit(u):
        return f"{u}{text}"
    if u.lower() == "iso":
        return f"{u} {text}"
    if u == "°":
        return f"{text}°"
    return f"{text} {u}"


def _format_value_by_tipo(
    value: str, tipo: Optional[str], unidad: Optional[str] = None
) -> str:
    """Formatea el value de una spec según su tipo para renderización en
    nombres públicos / contextos legibles.

    - `multi_enum`: parsea JSON array → join con ` · `. Si el value es string
      simple (legacy), lo devuelve tal cual.
    - `rango`: parsea JSON array → `"min - max"` o solo `"v"` si es fijo. Si
      hay unidad, la agrega (prefijo para `f/`/monedas, sufijo para el resto).
    - `bool`: `"true"` → "Sí", `"false"` → "" (vacío para colapsar conectores).
    - resto (string, number, enum): devuelve value tal cual.
    """
    if not value:
        return ""
    v = value.strip()
    if not v:
        return ""

    if tipo == "multi_enum":
        if v.startswith("["):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return " · ".join(str(x) for x in parsed if str(x).strip())
            except Exception:
                pass
        return v

    if tipo == "rango":
        if v.startswith("["):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    items = [str(x) for x in parsed if str(x).strip()]
                    if len(items) == 1:
                        out = items[0]
                    elif len(items) >= 2:
                        out = f"{items[0]} - {items[1]}"
                    else:
                        return ""
                    return _apply_unit(out, unidad)
            except Exception:
                pass
        # value no es JSON — devolver tal cual
        return v

    if tipo == "bool":
        low = v.lower()
        if low in ("true", "1", "yes", "sí", "si"):
            return "Sí"
        return ""

    return v


def render_spec_value(
    value: str, tipo: Optional[str], unidad: Optional[str] = None
) -> str:
    """Render de display de un valor de spec — fuente ÚNICA para la ficha
    pública y los specs destacados (quick facts). Comparte la lógica de
    `_format_value_by_tipo` (rango/multi_enum/bool) que también alimenta el
    nombre público, así un mismo valor se ve idéntico en todos lados.

    Diferencia con el nombre: acá un `number` con unidad la muestra inline
    (ej. "82 mm", "640 g") — en el nombre la unidad la pone el template.
    """
    base = _format_value_by_tipo(value, tipo, unidad)
    if tipo == "number" and unidad and base:
        return _apply_unit(base, unidad)
    return base


def render_spec_placeholder(
    value: str,
    tipo: Optional[str],
    tabla_columnas: Optional[list],
    output_config: Optional[dict],
    path: str = "",
    unidad: Optional[str] = None,
) -> str:
    """Resuelve un placeholder de spec.

    - `path == ""` (placeholder es `{spec:Label}`):
        * Si tipo == 'tabla', formatea con conectores aplicando row_strategy.
        * Si no, devuelve el value tal cual — o aplica `name_format` si está
          configurado en `output_config`.
    - `path == "colKey"` o `"colKey[i]"`:
        * Solo aplica a tipo tabla. Extrae la celda colKey de la fila i.
        * Sin índice explícito, usa fila 0 (no se aplica row_strategy: el
          path explícito gana sobre la config).

    `output_config.name_format` (str, opcional): template con `{value}` y
    `{unidad}` para personalizar cómo se renderiza el spec dentro del
    nombre auto. Ej. "Potencia {value} lúmenes" → "Potencia 19389 lúmenes".
    Si el value está vacío, no se aplica (devuelve string vacío para que
    los conectores adyacentes del template también se colapsen).
    """
    if not path:
        if tipo == "tabla":
            return format_tabla_value(value or "", tabla_columnas or [], output_config)
        # Formatear value según tipo antes de aplicar name_format.
        rendered = _format_value_by_tipo(value or "", tipo, unidad)
        # Aplicar name_format si está configurado y hay value rendered.
        nf = (output_config or {}).get("name_format") if output_config else None
        if nf and rendered:
            try:
                return nf.replace("{value}", rendered).replace("{unidad}", unidad or "")
            except Exception:
                return rendered
        return rendered
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
