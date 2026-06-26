"""dataio/csv_importers.py — Import de planillas CSV al inventario.

Solo soporta el CSV de inventario (serie / valor_reposicion / bh_url /
fecha_compra). Match por columna `id`. Modo dry-run por default: devuelve
el diff sin tocar la BD. Modo apply: actualiza y devuelve resumen.

Contrato de la planilla:
- Primera columna obligatoria: `id` (entero, key de match).
- Columnas editables reconocidas: serie, valor_reposicion, bh_url, fecha_compra.
- Columnas extra (nombre, marca, specs…) se ignoran silenciosamente.
- Celdas vacías = sin cambio (no nullean el valor existente).
- BOM UTF-8 al inicio se descarta automáticamente.
"""

import csv
import io
import re
from datetime import date

_EDITABLES = frozenset({"serie", "valor_reposicion", "bh_url", "fecha_compra"})

# Regex laxo de fecha: acepta YYYY-MM-DD y DD/MM/YYYY
_DATE_ISO  = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DATE_DDMM = re.compile(r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$")


class CSVImportError(ValueError):
    pass


def _parse_date(raw: str) -> date | None:
    s = raw.strip()
    if not s:
        return None
    m = _DATE_ISO.match(s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _DATE_DDMM.match(s)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    raise CSVImportError(f"fecha_compra inválida: {s!r} (usar YYYY-MM-DD o DD/MM/YYYY)")


def _parse_valor(raw: str) -> float | None:
    s = raw.strip().replace(",", ".")
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        raise CSVImportError(f"valor_reposicion inválido: {raw!r} (debe ser un número)")
    if v < 0:
        raise CSVImportError(f"valor_reposicion no puede ser negativo: {v}")
    return v


def _parse_csv_bytes(raw: bytes) -> list[dict]:
    """Decodifica CSV (UTF-8 con o sin BOM) y devuelve lista de dicts."""
    text = raw.decode("utf-8-sig").strip()
    if not text:
        raise CSVImportError("El archivo CSV está vacío.")
    reader = csv.DictReader(io.StringIO(text))
    if "id" not in (reader.fieldnames or []):
        raise CSVImportError("El CSV debe tener una columna 'id'.")
    rows = list(reader)
    if not rows:
        raise CSVImportError("El CSV no tiene filas de datos.")
    return rows


def import_inventario_csv(conn, raw: bytes, *, dry_run: bool = True) -> dict:
    """Procesa el CSV de inventario y aplica (o simula) las actualizaciones.

    Args:
        conn: conexión de BD activa (PGConnection / similar).
        raw: bytes del CSV subido.
        dry_run: si True no escribe nada — devuelve solo el diff previsto.

    Returns:
        {
          dry_run: bool,
          total_filas: int,
          actualizados: int,
          sin_cambio: int,
          no_encontrados: list[int],   # ids que no existen en la BD
          errores: list[str],          # filas con datos inválidos (no bloquean las demás)
          diff: list[{id, campo, antes, despues}],  # siempre presente
        }
    """
    rows = _parse_csv_bytes(raw)

    # Traer estado actual de todos los equipos del CSV en una sola query.
    try:
        ids_csv = [int(r["id"]) for r in rows if r.get("id", "").strip()]
    except ValueError as exc:
        raise CSVImportError(f"Columna 'id' contiene un valor no numérico: {exc}")

    if not ids_csv:
        raise CSVImportError("Ninguna fila tiene un 'id' válido.")

    placeholders = ",".join(["%s"] * len(ids_csv))
    existing = {
        r["id"]: r
        for r in conn.execute(
            f"SELECT id, serie, valor_reposicion, bh_url, fecha_compra"
            f" FROM equipos WHERE id IN ({placeholders}) AND eliminado_at IS NULL",
            ids_csv,
        ).fetchall()
    }

    diff: list[dict] = []
    errores: list[str] = []
    no_encontrados: list[int] = []
    updates: list[tuple] = []  # (id, {campo: valor})

    for row in rows:
        raw_id = row.get("id", "").strip()
        if not raw_id:
            continue
        try:
            equipo_id = int(raw_id)
        except ValueError:
            errores.append(f"id inválido: {raw_id!r}")
            continue

        if equipo_id not in existing:
            no_encontrados.append(equipo_id)
            continue

        current = existing[equipo_id]
        patch: dict = {}

        # serie
        if "serie" in row:
            val = row["serie"].strip() or None
            if val != (current["serie"] or None):
                diff.append({"id": equipo_id, "campo": "serie",
                             "antes": current["serie"], "despues": val})
                patch["serie"] = val

        # valor_reposicion
        if "valor_reposicion" in row:
            try:
                val_f = _parse_valor(row["valor_reposicion"])
            except CSVImportError as exc:
                errores.append(f"Fila id={equipo_id}: {exc}")
                continue
            cur_val = current["valor_reposicion"]
            if val_f != cur_val and not (val_f is None and cur_val is None):
                diff.append({"id": equipo_id, "campo": "valor_reposicion",
                             "antes": cur_val, "despues": val_f})
                if val_f is not None:
                    patch["valor_reposicion"] = val_f

        # bh_url
        if "bh_url" in row:
            val = row["bh_url"].strip() or None
            if val != (current["bh_url"] or None):
                diff.append({"id": equipo_id, "campo": "bh_url",
                             "antes": current["bh_url"], "despues": val})
                patch["bh_url"] = val

        # fecha_compra
        if "fecha_compra" in row:
            try:
                val_d = _parse_date(row["fecha_compra"])
            except CSVImportError as exc:
                errores.append(f"Fila id={equipo_id}: {exc}")
                continue
            cur_d = current["fecha_compra"]
            # Normalizar: la BD devuelve un date, comparar sin hora
            if isinstance(cur_d, str):
                cur_d = _parse_date(cur_d)
            if val_d != cur_d:
                diff.append({"id": equipo_id, "campo": "fecha_compra",
                             "antes": str(cur_d) if cur_d else None,
                             "despues": str(val_d) if val_d else None})
                patch["fecha_compra"] = val_d.isoformat() if val_d else None

        if patch:
            updates.append((equipo_id, patch))

    actualizados = len(updates)
    sin_cambio   = len(ids_csv) - actualizados - len(no_encontrados) - len(errores)

    if not dry_run and updates:
        for equipo_id, patch in updates:
            set_clause = ", ".join(f"{k} = %s" for k in patch)
            conn.execute(
                f"UPDATE equipos SET {set_clause}, updated_at = CURRENT_TIMESTAMP"
                f" WHERE id = %s",
                list(patch.values()) + [equipo_id],
            )
        conn.commit()

    return {
        "dry_run":        dry_run,
        "total_filas":    len(ids_csv),
        "actualizados":   actualizados,
        "sin_cambio":     max(0, sin_cambio),
        "no_encontrados": no_encontrados,
        "errores":        errores,
        "diff":           diff,
    }
