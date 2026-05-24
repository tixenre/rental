"""
routes/settings.py — Settings panel (app_settings y mantenimiento).

Los endpoints de import-equipos/clientes/alquileres por CSV se removieron
en favor del módulo dataio (backend/dataio/) que ofrece export/import
JSON bidireccional. Para migrar datos legacy ahora se usa el CLI:
    python -m backend.dataio.cli export
    python -m backend.dataio.cli import
"""

from fastapi import APIRouter, Request, HTTPException
from database import get_db, row_to_dict
from routes.auth import get_session

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────

def require_admin(request: Request) -> dict:
    session = get_session(request)
    if not session:
        raise HTTPException(401, "No autenticado")
    return session


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
    "og_image_url",      # URL pública del OG image para preview en redes (1200x630).
    "whatsapp_phone",    # Teléfono del negocio para click-to-chat (formato +5492235852510).
    "email_from",        # From address de mails ('Rambla <pedidos@rambla.com.uy>'). Pisado por env EMAIL_FROM.
    "email_admin_to",    # Destinatario de notif al admin cuando entra un pedido. Pisado por env EMAIL_ADMIN_TO.
    "buffer_horas_alquiler",  # Horas de prep/revisión exigidas entre alquileres. Int >= 0.
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
    if key == "buffer_horas_alquiler":
        try:
            v = int(value)
            if v < 0:
                raise ValueError("debe ser >= 0")
            value = str(v)
        except (ValueError, TypeError) as e:
            raise HTTPException(400, f"Valor inválido para '{key}': debe ser un entero >= 0 ({e})")
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


def _optimize_og_image(raw_content: bytes) -> tuple[bytes, str, str]:
    """Optimiza imagen para preview Open Graph (WhatsApp / IG / Facebook).

    Target: 1200x630 (recomendación de Facebook). Si la imagen no tiene
    ese aspect ratio (1.91:1), la centramos sobre fondo blanco y cubrimos.
    Se sirve como JPEG (mejor compresión que PNG para fotos).

    Retorna (bytes, content_type, ext).
    """
    from io import BytesIO
    from PIL import Image

    TARGET_W, TARGET_H = 1200, 630

    img = Image.open(BytesIO(raw_content))
    if img.mode in ("RGBA", "LA", "P"):
        # Aplanamos sobre fondo blanco (los OG images suelen rendererarse en
        # plataformas que no manejan transparencia bien).
        bg = Image.new("RGB", img.size, (255, 255, 255))
        img_rgba = img.convert("RGBA") if img.mode != "RGBA" else img
        bg.paste(img_rgba, mask=img_rgba.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")

    # Cover: escalar y centrar para llenar 1200x630.
    src_ratio = img.width / img.height
    tgt_ratio = TARGET_W / TARGET_H
    if src_ratio > tgt_ratio:
        # Imagen más ancha que el target — recortar lados.
        new_h = TARGET_H
        new_w = int(img.width * (TARGET_H / img.height))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - TARGET_W) // 2
        img = img.crop((left, 0, left + TARGET_W, TARGET_H))
    else:
        # Imagen más alta — recortar top/bottom.
        new_w = TARGET_W
        new_h = int(img.height * (TARGET_W / img.width))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - TARGET_H) // 2
        img = img.crop((0, top, TARGET_W, top + TARGET_H))

    out = BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue(), "image/jpeg", "jpg"


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

    # SVG: es vectorial, no pasa por PIL (que no lo entiende → "cannot
    # identify image file"). Se sube tal cual; <img> lo renderiza bien y
    # escala sin pérdida. Se sirve con content-type image/svg+xml.
    filename = (getattr(file, "filename", "") or "").lower()
    ctype_in = (getattr(file, "content_type", "") or "").lower()
    is_svg = (
        filename.endswith(".svg")
        or "svg" in ctype_in
        or b"<svg" in raw_content[:1024].lower()
    )

    if is_svg:
        content, ctype, ext = raw_content, "image/svg+xml", "svg"
    else:
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


@router.post("/admin/settings/upload-og-image")
async def upload_og_image(request: Request):
    """Sube imagen como preview de Open Graph (1200x630) y guarda la URL
    en `app_settings.og_image_url`.

    Es la imagen que ven WhatsApp / IG / Facebook al compartir el link de
    la home. Misma estrategia que upload-logo: path fijo + cache-buster.
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

    try:
        content, ctype, ext = _optimize_og_image(raw_content)
    except Exception as e:
        raise HTTPException(400, f"No se pudo procesar la imagen: {e}")

    path = f"branding/og-image.{ext}"

    from routes.equipos import _upload_to_r2
    public_url = _upload_to_r2(path, content, ctype)

    import time as _time
    versioned_url = f"{public_url}?v={int(_time.time())}"

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO app_settings (key, value, updated_at, updated_by)
            VALUES ('og_image_url', %s, CURRENT_TIMESTAMP, %s)
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
