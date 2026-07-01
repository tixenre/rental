"""services/spec_persist.py — Persistencia canónica de specs por equipo.

Un único punto de guardado: DELETE + INSERT con coerción+validación antes de
escribir. Importable sin dep de database (no importa psycopg2/get_db).
"""

from __future__ import annotations

import json

from fastapi import HTTPException


def _validate_tabla_value(value: str, columnas: list[dict], spec_label: str) -> str:
    """Valida que `value` sea JSON array donde cada row tiene las keys de
    `columnas` con los tipos correctos. Devuelve el JSON re-serializado
    (compactado) para garantizar storage normalizado."""
    try:
        data = json.loads(value)
    except Exception:
        raise HTTPException(400, f"Spec '{spec_label}' tipo tabla: value debe ser JSON válido.")
    if not isinstance(data, list):
        raise HTTPException(400, f"Spec '{spec_label}': tabla debe ser un array de filas.")
    cleaned: list[dict] = []
    col_by_key = {c["key"]: c for c in columnas}
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            raise HTTPException(400, f"Spec '{spec_label}' fila {i}: debe ser objeto.")
        clean_row: dict = {}
        for key, col in col_by_key.items():
            v = row.get(key)
            if v is None or v == "":
                continue
            ctipo = col["tipo"]
            if ctipo == "number":
                try:
                    clean_row[key] = float(v) if "." in str(v) else int(v)
                except (TypeError, ValueError):
                    raise HTTPException(
                        400,
                        f"Spec '{spec_label}' fila {i} columna '{key}': debe ser número, vino {v!r}.",
                    )
            elif ctipo == "valor_unidad":
                if not isinstance(v, dict):
                    raise HTTPException(
                        400,
                        f"Spec '{spec_label}' fila {i} columna '{key}': debe ser objeto {{valor, unidad}}.",
                    )
                valor_raw = v.get("valor")
                unidad_raw = v.get("unidad", "")
                has_valor = valor_raw not in (None, "")
                has_unidad = bool(str(unidad_raw or "").strip())
                if not has_valor and not has_unidad:
                    continue
                cell: dict = {}
                if has_valor:
                    try:
                        cell["valor"] = float(valor_raw) if "." in str(valor_raw) else int(valor_raw)
                    except (TypeError, ValueError):
                        cell["valor"] = str(valor_raw).strip()
                if has_unidad:
                    cell["unidad"] = str(unidad_raw).strip()
                clean_row[key] = cell
            elif ctipo == "bool":
                clean_row[key] = bool(v) if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes", "sí", "si")
            elif ctipo == "enum":
                if str(v) not in (col.get("options") or []):
                    raise HTTPException(
                        400,
                        f"Spec '{spec_label}' fila {i} columna '{key}': '{v}' no está en opciones {col.get('options')}.",
                    )
                clean_row[key] = str(v)
            else:  # string
                clean_row[key] = str(v).strip()
        if clean_row:
            cleaned.append(clean_row)
    return json.dumps(cleaned, ensure_ascii=False)


def persistir_specs(
    conn,
    equipo_id: int,
    specs: dict,
    defs_by_id: dict,
    *,
    coerce: bool = True,
) -> dict:
    """Reemplaza todas las specs del equipo (DELETE + INSERT).

    Si coerce=True (default), aplica coerce_and_serialize a cada valor antes
    de persistir. Valores que no pasan la coerción se descartan sin lanzar
    error — el llamador recibe la lista de descartados para mostrar al admin.
    El tipo 'tabla' siempre se valida estructuralmente (independiente de coerce).

    Returns: {"persisted": int, "discarded": list[dict]}
    """
    from .coerce import coerce_and_serialize

    conn.execute("DELETE FROM equipo_specs WHERE equipo_id = %s", (equipo_id,))
    persisted = 0
    discarded: list[dict] = []

    for key, value in specs.items():
        if value is None or value == "":
            continue

        spec_def_id = int(key)
        sd = defs_by_id.get(spec_def_id)
        tipo = sd.get("tipo", "string") if sd else "string"
        label = sd.get("label", str(spec_def_id)) if sd else str(spec_def_id)

        if tipo == "tabla":
            cols = sd.get("tabla_columnas") if sd else None
            if isinstance(cols, str):
                cols = json.loads(cols)
            if not cols:
                raise HTTPException(
                    500, f"Spec '{label}' tipo tabla sin tabla_columnas definidas."
                )
            persist_value = _validate_tabla_value(str(value), cols, label)
            if persist_value == "[]":
                continue
        elif coerce:
            persist_value = coerce_and_serialize(
                value,
                tipo,
                sd.get("unidad") if sd else None,
                sd.get("enum_options") if sd else None,
            )
            if persist_value is None:
                discarded.append({
                    "spec_def_id": spec_def_id,
                    "label": label,
                    "raw": str(value)[:200],
                })
                continue
        else:
            persist_value = str(value)

        conn.execute(
            "INSERT INTO equipo_specs (equipo_id, spec_def_id, value) VALUES (%s, %s, %s)"
            " ON CONFLICT (equipo_id, spec_def_id) DO UPDATE SET value = EXCLUDED.value",
            (equipo_id, spec_def_id, persist_value),
        )
        persisted += 1

    return {"persisted": persisted, "discarded": discarded}
