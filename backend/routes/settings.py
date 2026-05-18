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
    "logo_url",          # URL pública del logo (imagen). String.
    "email_from",        # From address de mails ('Rambla <pedidos@rambla.com.uy>'). Pisado por env EMAIL_FROM.
    "email_admin_to",    # Destinatario de notif al admin cuando entra un pedido. Pisado por env EMAIL_ADMIN_TO.
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

    Payload:
        - dry_run: bool — si True, no escribe, solo devuelve el preview.
        - mode: str — uno de:
            * "missing"  → sólo equipos sin precio_jornada cargado.
            * "auto"     → equipos automáticos (precio_jornada_manual=FALSE).
                            **Default** y el más usado: respeta los precios
                            que el admin tipeó a mano.
            * "all"      → todos, incluyendo manuales (los pisa).
            * "ids"      → sólo los equipo_ids pasados en `ids` (lista).
        - ids: list[int] — equipos específicos a recalcular (modo "ids").
        - only_missing: bool — DEPRECATED, equivale a mode="missing".

    Nunca toca equipos sin precio_usd o sin roi_pct (no hay fórmula
    que aplicar).
    """
    require_admin(request)
    dry_run = bool(payload.get("dry_run"))
    # Backwards compat: only_missing=True equivale a mode="missing".
    if payload.get("only_missing") is True:
        mode = "missing"
    else:
        mode = payload.get("mode") or "auto"
    if mode not in ("missing", "auto", "all", "ids"):
        raise HTTPException(400, f"mode inválido: {mode}")
    ids = payload.get("ids") or []
    if mode == "ids" and not ids:
        raise HTTPException(400, "mode=ids requiere lista `ids` no vacía")

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
        params: list = []
        if mode == "missing":
            where += " AND precio_jornada IS NULL"
        elif mode == "auto":
            where += " AND precio_jornada_manual = FALSE"
        elif mode == "ids":
            placeholders = ",".join(["?"] * len(ids))
            where += f" AND id IN ({placeholders})"
            params.extend(int(i) for i in ids)
        # mode == "all": sin filtro adicional
        rows = conn.execute(
            f"SELECT id, nombre, precio_usd, roi_pct, precio_jornada, precio_jornada_manual "
            f"FROM equipos WHERE {where}",
            tuple(params),
        ).fetchall()

        cambios: list[dict] = []
        for r in rows:
            # Redondeo al múltiplo de 100 más cercano.
            raw = r["precio_usd"] * usd_rate * (r["roi_pct"] / 100)
            nuevo = round(raw / 100) * 100
            anterior = r["precio_jornada"]
            if anterior != nuevo:
                cambios.append({
                    "id": r["id"], "nombre": r["nombre"],
                    "antes": anterior, "despues": nuevo,
                    "delta": nuevo - (anterior or 0),
                    "manual": bool(r["precio_jornada_manual"]),
                })
                if not dry_run:
                    # Al recalcular bulk, marcamos como auto (precio
                    # vuelve a la fórmula). Si el admin quiere preservarlo
                    # como manual debe usar mode="auto" que ya skipea.
                    conn.execute(
                        "UPDATE equipos SET precio_jornada = ?, "
                        "precio_jornada_manual = FALSE, "
                        "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (nuevo, r["id"]),
                    )
        if not dry_run:
            conn.commit()
        return {
            "usd_rate": usd_rate,
            "mode": mode,
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


@router.get("/admin/equipos/precios-manuales")
def listar_precios_manuales(request: Request):
    """Devuelve todos los equipos con `precio_jornada_manual = TRUE`,
    junto con el precio que daría la fórmula con el USD rate actual.
    Útil para revisar uno por uno qué hacer cuando se actualiza el USD."""
    require_admin(request)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", ("usd_rate",)
        ).fetchone()
        usd_rate = float(row["value"]) if row else 0.0

        rows = conn.execute(
            """
            SELECT id, nombre, marca, modelo, foto_url,
                   precio_jornada, precio_usd, roi_pct
            FROM equipos
            WHERE precio_jornada_manual = TRUE
            ORDER BY LOWER(nombre)
            """
        ).fetchall()

        items = []
        for r in rows:
            calculado = None
            if r["precio_usd"] and r["roi_pct"] and usd_rate > 0:
                raw = r["precio_usd"] * usd_rate * (r["roi_pct"] / 100)
                calculado = round(raw / 100) * 100
            items.append({
                "id": r["id"],
                "nombre": r["nombre"],
                "marca": r["marca"],
                "modelo": r["modelo"],
                "foto_url": r["foto_url"],
                "precio_actual": r["precio_jornada"],
                "precio_usd": r["precio_usd"],
                "roi_pct": r["roi_pct"],
                "precio_calculado": calculado,
                "delta": (calculado - r["precio_jornada"]) if calculado is not None and r["precio_jornada"] is not None else None,
            })
        return {"usd_rate": usd_rate, "items": items}
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


# ── Upload logo a R2 ──────────────────────────────────────────────────────────

def _optimize_logo(raw_content: bytes) -> tuple[bytes, str, str]:
    """Optimiza una imagen para usar como logo del top bar.

    Distinto de `_optimize_image` (que es para fotos de equipos):
    - NO recorta al ras (trim_and_square).
    - NO hace cuadrado.
    - Mantiene aspect ratio original (wordmark horizontal queda horizontal).
    - Resize si el ancho excede 600px (preserva proporciones).
    - Guarda como PNG para preservar transparencia.

    Retorna (bytes, content_type, ext).
    """
    from io import BytesIO
    from PIL import Image

    img = Image.open(BytesIO(raw_content))
    # Convertir a RGBA para preservar transparencia.
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    MAX_WIDTH = 600
    if img.width > MAX_WIDTH:
        new_height = int(img.height * (MAX_WIDTH / img.width))
        img = img.resize((MAX_WIDTH, new_height), Image.Resampling.LANCZOS)

    out = BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue(), "image/png", "png"


@router.post("/admin/settings/upload-logo")
async def upload_logo(request: Request):
    """Sube una imagen como logo a R2 y guarda la URL en app_settings.

    Path fijo: 'branding/logo.png'. R2 sobreescribe — cada upload reemplaza
    la versión anterior (no acumula basura). La URL guardada incluye un
    query string `?v=<timestamp>` como cache buster para invalidar el cache
    del navegador / CDN sin esperar TTL.

    Issue #127.
    """
    session = require_admin(request)
    actor = (session.get("email") or session.get("user_id") or "admin")[:255]

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file'")

    raw_content = await file.read()
    if not raw_content:
        raise HTTPException(400, "Archivo vacío")
    if len(raw_content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Archivo muy grande (máx 5MB)")

    # Optimizar manteniendo aspect ratio (wordmarks horizontales no se
    # vuelven cuadrados — eso engrosaba el top bar mobile, issue #127).
    try:
        content, ctype, ext = _optimize_logo(raw_content)
    except Exception as e:
        raise HTTPException(400, f"No se pudo procesar la imagen: {e}")

    # Path FIJO — R2 sobreescribe.
    path = f"branding/logo.{ext}"

    from routes.equipos import _upload_to_r2
    public_url = _upload_to_r2(path, content, ctype)

    # Cache buster: cada upload genera un ?v=<timestamp> distinto. El
    # navegador descarga la versión nueva sin esperar TTL del CDN.
    import time as _time
    versioned_url = f"{public_url}?v={int(_time.time())}"

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO app_settings (key, value, updated_at, updated_by)
            VALUES ('logo_url', %s, CURRENT_TIMESTAMP, %s)
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = EXCLUDED.updated_by
        """, (versioned_url, actor))
        conn.commit()
        return {"ok": True, "url": versioned_url}
    finally:
        conn.close()


# ── Backup manual ─────────────────────────────────────────────────────────────

@router.post("/admin/backup-manual")
def trigger_backup_manual(request: Request):
    """Dispara un pg_dump → R2 on-demand.

    Requiere BACKUP_ENABLED=true y las credenciales R2 configuradas.
    Útil para hacer un backup antes de una migración o cambio importante.
    """
    require_admin(request)
    from services.backup_service import run_backup, BACKUP_ENABLED
    if not BACKUP_ENABLED:
        raise HTTPException(503, "Backup no habilitado. Setear BACKUP_ENABLED=true en Railway cuando estén en producción.")
    try:
        result = run_backup()
        return result
    except Exception as e:
        raise HTTPException(500, f"Backup falló: {e}")
