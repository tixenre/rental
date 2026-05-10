"""
routes/settings.py — Settings panel y importación de datos desde CSV.
"""

import csv
import io
from collections import OrderedDict
from datetime import date as _date

from fastapi import APIRouter, UploadFile, File, Request, HTTPException
from database import get_db, row_to_dict
from routes.auth import get_session

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────

def require_admin(request: Request) -> dict:
    session = get_session(request)
    if not session:
        raise HTTPException(401, "No autenticado")
    return session


async def parse_csv_file(file: UploadFile) -> list[dict]:
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "Solo archivos CSV permitidos")
    try:
        content = await file.read()
        content = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            raise HTTPException(400, "CSV sin headers")
        return list(reader)
    except UnicodeDecodeError:
        raise HTTPException(400, "Error decodificando CSV — usar UTF-8")
    except Exception as e:
        raise HTTPException(400, f"Error leyendo CSV: {str(e)}")


# ── App settings (key/value config global) ───────────────────────────────────
#
# Tipo de cambio, defaults y otras configs globales que el admin edita
# desde el panel. Storage: tabla `app_settings` (key TEXT pk + value TEXT).
# Los valores se guardan siempre como string; el cliente parsea (Number,
# bool, etc.) según conozca el tipo.

# Whitelist de keys editables por la UI. Cualquier otra key se rechaza
# para no exponer settings internos accidentalmente.
ALLOWED_SETTINGS_KEYS = {
    "usd_rate",          # ARS por 1 USD. Float.
    "roi_pct_default",   # % default para nuevos equipos. Float.
    "shipping_usd",      # Envío default en USD para cálculo de reposición. Float.
}


@router.get("/settings/{key}")
def get_setting(key: str):
    """Devuelve el valor de una setting. Lectura pública (el USD rate
    afecta cálculos en el frontend público también)."""
    if key not in ALLOWED_SETTINGS_KEYS:
        raise HTTPException(404, f"Setting '{key}' no existe")
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT value, updated_at, updated_by FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Setting '{key}' sin valor")
        return {
            "key": key,
            "value": row["value"],
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "updated_by": row["updated_by"],
        }
    finally:
        conn.close()


@router.get("/settings")
def list_settings():
    """Lista todas las settings públicas. Útil para el panel admin."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT key, value, updated_at, updated_by FROM app_settings ORDER BY key"
        ).fetchall()
        return {
            "items": [
                {
                    "key": r["key"],
                    "value": r["value"],
                    "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                    "updated_by": r["updated_by"],
                }
                for r in rows
                if r["key"] in ALLOWED_SETTINGS_KEYS
            ]
        }
    finally:
        conn.close()


@router.put("/admin/settings/{key}")
def update_setting(key: str, payload: dict, request: Request):
    """Actualiza una setting (solo admin)."""
    session = require_admin(request)
    if key not in ALLOWED_SETTINGS_KEYS:
        raise HTTPException(400, f"Setting '{key}' no es editable")
    value = payload.get("value")
    if value is None or str(value).strip() == "":
        raise HTTPException(400, "El valor no puede estar vacío")
    value = str(value).strip()
    # Validación específica por key: ciertas settings son numéricas.
    if key in ("usd_rate", "roi_pct_default", "shipping_usd"):
        try:
            v = float(value)
            if v < 0:
                raise ValueError("debe ser >= 0")
        except (ValueError, TypeError) as e:
            raise HTTPException(400, f"Valor inválido para '{key}': debe ser un número >= 0 ({e})")
    actor = (session.get("email") or session.get("user_id") or "admin")[:255]
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO app_settings (key, value, updated_at, updated_by)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT (key) DO UPDATE
            SET value      = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = EXCLUDED.updated_by
        """, (key, value, actor))
        conn.commit()
        return {"key": key, "value": value, "updated_by": actor}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Recálculo masivo de precio_jornada según USD rate actual ─────────────────

@router.post("/admin/settings/recalcular-precios")
def recalcular_precios(payload: dict, request: Request):
    """Recalcula el precio_jornada de todos los equipos con precio_usd y
    roi_pct definidos. Fórmula:

        precio_jornada (ARS) = precio_usd × usd_rate × (roi_pct / 100)

    Útil cuando el admin actualiza el tipo de cambio mensual.

    Payload opcional:
        - dry_run: bool — si True, no escribe, solo devuelve el preview.
        - only_missing: bool — si True, solo recalcula equipos sin
          precio_jornada (no pisa valores manuales).
    """
    require_admin(request)
    dry_run = bool(payload.get("dry_run"))
    only_missing = bool(payload.get("only_missing"))

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", ("usd_rate",)
        ).fetchone()
        if not row:
            raise HTTPException(400, "usd_rate no configurado")
        try:
            usd_rate = float(row["value"])
        except (ValueError, TypeError):
            raise HTTPException(400, f"usd_rate inválido: {row['value']}")

        where = "precio_usd IS NOT NULL AND roi_pct IS NOT NULL"
        if only_missing:
            where += " AND precio_jornada IS NULL"
        rows = conn.execute(
            f"SELECT id, nombre, precio_usd, roi_pct, precio_jornada "
            f"FROM equipos WHERE {where}"
        ).fetchall()

        cambios: list[dict] = []
        for r in rows:
            # Redondeo al múltiplo de 100 más cercano: precios sin centavos
            # ni unidades sueltas. $1184 → $1200, $14442 → $14400.
            raw = r["precio_usd"] * usd_rate * (r["roi_pct"] / 100)
            nuevo = round(raw / 100) * 100
            anterior = r["precio_jornada"]
            if anterior != nuevo:
                cambios.append({
                    "id": r["id"], "nombre": r["nombre"],
                    "antes": anterior, "despues": nuevo,
                    "delta": nuevo - (anterior or 0),
                })
                if not dry_run:
                    conn.execute(
                        "UPDATE equipos SET precio_jornada = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (nuevo, r["id"]),
                    )
        if not dry_run:
            conn.commit()
        return {
            "usd_rate": usd_rate,
            "total_evaluados": len(rows),
            "total_cambios": len(cambios),
            "cambios": cambios[:50],  # cap por si son muchos
            "dry_run": dry_run,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/settings/import-equipos")
async def import_equipos(file: UploadFile = File(...), request: Request = None):
    require_admin(request)
    rows = await parse_csv_file(file)
    conn = get_db()
    success_count = 0
    error_details = []

    try:
        for idx, row in enumerate(rows, 1):
            # SAVEPOINT por fila: si falla, solo se revierte esa fila
            conn.execute("SAVEPOINT sp")
            try:
                nombre = row.get('nombre', '').strip()
                if not nombre:
                    error_details.append(f"Fila {idx}: nombre vacío")
                    conn.execute("RELEASE SAVEPOINT sp")
                    continue

                marca            = row.get('marca', '') or ''
                modelo           = row.get('modelo', '') or ''
                cantidad         = int(row.get('cantidad') or 1)
                precio_jornada   = int(row['precio_jornada'])   if row.get('precio_jornada')   else None
                precio_usd       = float(row['precio_usd'])     if row.get('precio_usd')       else None
                roi_pct          = float(row['roi_pct'])         if row.get('roi_pct')          else None
                valor_reposicion = float(row['valor_reposicion']) if row.get('valor_reposicion') else None
                foto_url         = row.get('foto_url', '') or ''
                fecha_compra     = row.get('fecha_compra', '') or ''
                serie            = row.get('serie', '') or ''
                bh_url           = row.get('bh_url', '') or ''
                dueno            = row.get('dueno', 'Rambla') or 'Rambla'
                visible_catalogo = int(row.get('visible_catalogo') or 1)
                estado           = row.get('estado', 'ok') or 'ok'

                existing = conn.execute(
                    "SELECT id FROM equipos WHERE nombre = ?", (nombre,)
                ).fetchone()

                if existing:
                    conn.execute("""
                        UPDATE equipos SET
                            marca=?, modelo=?, cantidad=?,
                            precio_jornada=?, precio_usd=?, roi_pct=?,
                            valor_reposicion=?, foto_url=?,
                            fecha_compra=?, serie=?, bh_url=?,
                            dueno=?, visible_catalogo=?, estado=?,
                            updated_at=CURRENT_TIMESTAMP
                        WHERE nombre=?
                    """, (marca, modelo, cantidad, precio_jornada, precio_usd,
                          roi_pct, valor_reposicion, foto_url, fecha_compra,
                          serie, bh_url, dueno, visible_catalogo, estado, nombre))
                else:
                    conn.execute("""
                        INSERT INTO equipos (
                            nombre, marca, modelo, cantidad,
                            precio_jornada, precio_usd, roi_pct, valor_reposicion,
                            foto_url, fecha_compra, serie, bh_url,
                            dueno, visible_catalogo, estado
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (nombre, marca, modelo, cantidad, precio_jornada,
                          precio_usd, roi_pct, valor_reposicion, foto_url,
                          fecha_compra, serie, bh_url, dueno, visible_catalogo, estado))

                conn.execute("RELEASE SAVEPOINT sp")
                success_count += 1

            except Exception as e:
                conn.execute("ROLLBACK TO SAVEPOINT sp")
                conn.execute("RELEASE SAVEPOINT sp")
                error_details.append(f"Fila {idx}: {str(e)}")

        conn.commit()
    finally:
        conn.close()

    return {
        "success": success_count,
        "errors": len(error_details),
        "details": error_details,
        "total_rows": len(rows),
    }


@router.post("/settings/import-clientes")
async def import_clientes(
    file: UploadFile = File(...),
    reset: bool = False,
    request: Request = None,
):
    """Importa clientes desde CSV.
    Si reset=true, borra todos los clientes primero y luego linkea alquileres por nombre.
    Upsert por nombre (case-insensitive) — no depende del email.
    """
    require_admin(request)
    rows = await parse_csv_file(file)
    conn = get_db()
    success_count = 0
    error_details = []

    try:
        if reset:
            conn.execute("DELETE FROM clientes")

        for idx, row in enumerate(rows, 1):
            conn.execute("SAVEPOINT sp")
            try:
                nombre = row.get('nombre', '').strip()
                if not nombre:
                    error_details.append(f"Fila {idx}: nombre vacío")
                    conn.execute("RELEASE SAVEPOINT sp")
                    continue

                apellido         = row.get('apellido', '').strip() or '-'
                email            = row.get('email', '').strip() or None
                telefono         = row.get('telefono', '') or ''
                direccion        = row.get('direccion', '') or ''
                cuit             = row.get('cuit', '') or ''
                descuento        = float(row['descuento']) if row.get('descuento') else 0.0
                perfil_impuestos = row.get('perfil_impuestos', 'consumidor_final') or 'consumidor_final'
                notas            = row.get('notas', '') or ''

                existing = conn.execute(
                    "SELECT id FROM clientes WHERE LOWER(nombre) = LOWER(%s) LIMIT 1",
                    (nombre,)
                ).fetchone()

                if existing:
                    conn.execute("""
                        UPDATE clientes SET
                            apellido=%s, email=COALESCE(%s, email), telefono=%s,
                            direccion=%s, cuit=%s, descuento=%s,
                            perfil_impuestos=%s, notas=%s,
                            updated_at=CURRENT_TIMESTAMP
                        WHERE id=%s
                    """, (apellido, email, telefono, direccion, cuit,
                          descuento, perfil_impuestos, notas, existing[0]))
                else:
                    conn.execute("""
                        INSERT INTO clientes (
                            nombre, apellido, email, telefono, direccion,
                            cuit, descuento, perfil_impuestos, notas
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (nombre, apellido, email, telefono, direccion,
                          cuit, descuento, perfil_impuestos, notas))

                conn.execute("RELEASE SAVEPOINT sp")
                success_count += 1

            except Exception as e:
                conn.execute("ROLLBACK TO SAVEPOINT sp")
                conn.execute("RELEASE SAVEPOINT sp")
                error_details.append(f"Fila {idx}: {str(e)}")

        # Si fue reset, linkear todos los alquileres por nombre
        alquileres_linkeados = 0
        if reset:
            alquileres = conn.execute(
                "SELECT id, cliente_nombre FROM alquileres"
            ).fetchall()
            for alquiler_id, cliente_nombre in alquileres:
                cliente = conn.execute(
                    "SELECT id FROM clientes WHERE LOWER(nombre) = LOWER(%s) LIMIT 1",
                    (cliente_nombre,)
                ).fetchone()
                if cliente:
                    conn.execute(
                        "UPDATE alquileres SET cliente_id = %s WHERE id = %s",
                        (cliente[0], alquiler_id)
                    )
                    alquileres_linkeados += 1

        conn.commit()
    finally:
        conn.close()

    result = {
        "success": success_count,
        "errors": len(error_details),
        "details": error_details,
        "total_rows": len(rows),
    }
    if reset:
        result["alquileres_linkeados"] = alquileres_linkeados
    return result


@router.post("/settings/import-alquileres")
async def import_alquileres(file: UploadFile = File(...), request: Request = None):
    """Importa alquileres desde CSV.

    Formato: una fila por ítem. Filas con el mismo numero_pedido se agrupan
    en un solo alquiler. Columnas de ítem opcionales: equipo_nombre, cantidad,
    precio_jornada (si se omite precio_jornada se usa el del equipo).
    """
    require_admin(request)
    rows = await parse_csv_file(file)
    conn = get_db()
    success_count = 0
    error_details = []
    item_warnings = []

    # Agrupar filas por numero_pedido; sin numero_pedido → cada fila es un pedido propio
    groups: OrderedDict = OrderedDict()
    for idx, row in enumerate(rows, 1):
        num = row.get('numero_pedido', '').strip()
        key = num if num else f'__row_{idx}__'
        groups.setdefault(key, []).append((idx, row))

    try:
        for key, group in groups.items():
            conn.execute("SAVEPOINT sp_group")
            try:
                idx, first = group[0]

                cliente_nombre = first.get('cliente_nombre', '').strip()
                fecha_desde    = first.get('fecha_desde', '').strip()
                fecha_hasta    = first.get('fecha_hasta', '').strip()

                if not cliente_nombre or not fecha_desde or not fecha_hasta:
                    error_details.append(f"Fila {idx}: campos obligatorios faltantes (cliente_nombre, fecha_desde, fecha_hasta)")
                    conn.execute("RELEASE SAVEPOINT sp_group")
                    continue

                cliente_email    = first.get('cliente_email', '') or ''
                cliente_telefono = first.get('cliente_telefono', '') or ''

                cliente_id = None
                if cliente_email:
                    found = conn.execute(
                        "SELECT id FROM clientes WHERE LOWER(email) = LOWER(?)", (cliente_email,)
                    ).fetchone()
                    if found:
                        cliente_id = found[0]

                notas         = first.get('notas', '') or ''
                estado        = first.get('estado', 'presupuesto') or 'presupuesto'
                monto_total   = int(first['monto_total'])   if first.get('monto_total')   else 0
                monto_pagado  = int(first['monto_pagado'])  if first.get('monto_pagado')  else 0
                descuento_pct = float(first['descuento_pct']) if first.get('descuento_pct') else 0.0
                fuente        = first.get('fuente', 'sistema') or 'sistema'
                numero_remito = first.get('numero_remito', '') or ''
                num_val       = first.get('numero_pedido', '').strip()
                numero_pedido_db = int(num_val) if num_val.isdigit() else None

                # Upsert: si ya existe un pedido con ese numero_pedido, actualizar
                existing_pedido = None
                if numero_pedido_db is not None:
                    existing_pedido = conn.execute(
                        "SELECT id FROM alquileres WHERE numero_pedido = ?", (numero_pedido_db,)
                    ).fetchone()

                if existing_pedido:
                    pedido_id = existing_pedido[0]
                    conn.execute("""
                        UPDATE alquileres SET
                            cliente_id=?, cliente_nombre=?, cliente_email=?, cliente_telefono=?,
                            notas=?, estado=?, fecha_desde=?, fecha_hasta=?,
                            monto_total=?, monto_pagado=?, descuento_pct=?,
                            fuente=?, numero_remito=?, updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                    """, (cliente_id, cliente_nombre, cliente_email, cliente_telefono,
                          notas, estado, fecha_desde, fecha_hasta, monto_total,
                          monto_pagado, descuento_pct, fuente, numero_remito, pedido_id))
                    # Limpiar ítems existentes para reemplazarlos
                    conn.execute("DELETE FROM alquiler_items WHERE pedido_id = ?", (pedido_id,))
                else:
                    cur = conn.execute("""
                        INSERT INTO alquileres (
                            cliente_id, cliente_nombre, cliente_email, cliente_telefono,
                            notas, estado, fecha_desde, fecha_hasta,
                            monto_total, monto_pagado, descuento_pct,
                            fuente, numero_remito, numero_pedido
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (cliente_id, cliente_nombre, cliente_email, cliente_telefono,
                          notas, estado, fecha_desde, fecha_hasta, monto_total,
                          monto_pagado, descuento_pct, fuente, numero_remito, numero_pedido_db))
                    pedido_id = cur.lastrowid

                # Calcular jornadas para subtotales
                try:
                    d1 = _date.fromisoformat(fecha_desde[:10])
                    d2 = _date.fromisoformat(fecha_hasta[:10])
                    jornadas = max(1, (d2 - d1).days)
                except Exception:
                    jornadas = 1

                # Insertar items de todas las filas del grupo
                for row_idx, row in group:
                    equipo_nombre = row.get('equipo_nombre', '').strip()
                    if not equipo_nombre:
                        continue

                    equipo_row = conn.execute(
                        "SELECT id, precio_jornada FROM equipos WHERE LOWER(nombre) = LOWER(?)",
                        (equipo_nombre,)
                    ).fetchone()

                    if not equipo_row:
                        item_warnings.append(f"Fila {row_idx}: equipo '{equipo_nombre}' no encontrado — ítem omitido")
                        continue

                    equipo_id    = equipo_row[0]
                    precio_base  = equipo_row[1] or 0

                    try:
                        cantidad = max(1, int(row.get('cantidad', '') or 1))
                    except (ValueError, TypeError):
                        cantidad = 1

                    try:
                        precio = int(row.get('precio_jornada', '') or precio_base)
                    except (ValueError, TypeError):
                        precio = precio_base

                    subtotal = precio * cantidad * jornadas

                    conn.execute("""
                        INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada, subtotal)
                        VALUES (?, ?, ?, ?, ?)
                    """, (pedido_id, equipo_id, cantidad, precio, subtotal))

                conn.execute("RELEASE SAVEPOINT sp_group")
                success_count += 1

            except Exception as e:
                conn.execute("ROLLBACK TO SAVEPOINT sp_group")
                conn.execute("RELEASE SAVEPOINT sp_group")
                error_details.append(f"Grupo '{key}': {str(e)}")

        conn.commit()
    finally:
        conn.close()

    return {
        "success":    success_count,
        "errors":     len(error_details),
        "warnings":   len(item_warnings),
        "details":    error_details + item_warnings,
        "total_rows": len(rows),
    }


@router.post("/settings/fix-apellidos")
async def fix_apellidos_duplicados(request: Request = None):
    """
    Limpia apellidos duplicados: si apellido == nombre, lo reemplaza con '-'.
    Usar una sola vez después de la primera importación.
    """
    require_admin(request)
    conn = get_db()
    try:
        result = conn.execute("""
            UPDATE clientes
            SET apellido = '-', updated_at = CURRENT_TIMESTAMP
            WHERE apellido = nombre
        """)
        conn.commit()
        # Contar cuántos se actualizaron
        count = conn.execute(
            "SELECT COUNT(*) FROM clientes WHERE apellido = '-'"
        ).fetchone()[0]
        return {"fixed": count, "message": "Apellidos duplicados corregidos"}
    finally:
        conn.close()


@router.post("/settings/reset-clientes-desde-backup")
async def reset_clientes_desde_backup(request: Request = None):
    """
    Borra TODOS los clientes e importa desde el backup JSON:
    - 148 clientes originales del backup
    - 10 clientes faltantes que están en alquileres
    - Linkea todos los alquileres al cliente_id correcto

    ⚠️ DESTRUCTIVO: Borra todos los clientes actuales
    """
    require_admin(request)

    import json

    # Cargar backup
    backup_path = '/Users/tincho/Downloads/rambla-rental/backend/db_backup.json'
    try:
        with open(backup_path, 'r') as f:
            backup = json.load(f)
    except Exception as e:
        raise HTTPException(500, f"No se pudo cargar backup: {str(e)}")

    conn = get_db()
    try:
        # Paso 1: Borrar todos los clientes
        conn.execute("DELETE FROM clientes")

        # Paso 2: Insertar clientes del backup
        clientes_insertados = 0
        for cliente in backup['clientes']:
            conn.execute("""
                INSERT INTO clientes
                (nombre, apellido, email, telefono, direccion, cuit, descuento, perfil_impuestos, notas)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cliente.get('nombre', ''),
                cliente.get('apellido', '') or '-',
                cliente.get('email', '') or None,
                cliente.get('telefono', '') or '',
                cliente.get('direccion', '') or '',
                cliente.get('cuit', '') or '',
                cliente.get('descuento', 0) or 0,
                cliente.get('perfil_impuestos', 'consumidor_final') or 'consumidor_final',
                cliente.get('notas', '') or ''
            ))
            clientes_insertados += 1

        # Paso 3: Crear clientes faltantes (que existen en alquileres pero no en tabla clientes)
        clientes_nombres_existentes = {c['nombre'] for c in backup['clientes']}
        clientes_en_alquileres = {}

        for alq in backup['alquileres']:
            nombre = alq['cliente_nombre']
            if nombre not in clientes_en_alquileres:
                clientes_en_alquileres[nombre] = {'email': None, 'telefono': None}
            if alq.get('cliente_email'):
                clientes_en_alquileres[nombre]['email'] = alq['cliente_email']
            if alq.get('cliente_telefono'):
                clientes_en_alquileres[nombre]['telefono'] = alq['cliente_telefono']

        faltantes = {
            nombre: info
            for nombre, info in clientes_en_alquileres.items()
            if nombre not in clientes_nombres_existentes
        }

        for nombre, info in faltantes.items():
            conn.execute("""
                INSERT INTO clientes
                (nombre, apellido, email, telefono, direccion, cuit, descuento, perfil_impuestos, notas)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                nombre,
                '-',
                info['email'] or None,
                info['telefono'] or '',
                '',
                '',
                0,
                'consumidor_final',
                'Creado de alquileres históricos'
            ))
            clientes_insertados += 1

        # Paso 4: Linkear alquileres por nombre
        alquileres = conn.execute(
            "SELECT id, cliente_nombre FROM alquileres"
        ).fetchall()

        alquileres_linkeados = 0
        for alquiler_id, cliente_nombre in alquileres:
            cliente = conn.execute(
                "SELECT id FROM clientes WHERE LOWER(nombre) = LOWER(%s) LIMIT 1",
                (cliente_nombre,)
            ).fetchone()

            if cliente:
                conn.execute(
                    "UPDATE alquileres SET cliente_id = %s WHERE id = %s",
                    (cliente[0], alquiler_id)
                )
                alquileres_linkeados += 1

        conn.commit()

        return {
            "ok": True,
            "clientes_insertados": clientes_insertados,
            "clientes_faltantes_creados": len(faltantes),
            "alquileres_linkeados": alquileres_linkeados,
            "message": f"Reset completado: {clientes_insertados} clientes insertados, {alquileres_linkeados} alquileres linkeados"
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"Error: {str(e)}")
    finally:
        conn.close()
