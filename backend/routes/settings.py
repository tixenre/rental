"""
routes/settings.py — Settings panel (app_settings y mantenimiento).

Los endpoints de import-equipos/clientes/alquileres por CSV se removieron
en favor del módulo dataio (backend/dataio/) que ofrece export/import
JSON bidireccional. Para migrar datos legacy ahora se usa el CLI:
    python -m backend.dataio.cli export
    python -m backend.dataio.cli import
"""

import json
import re

from fastapi import APIRouter, Request, HTTPException
from database import get_db, MARCA_SUBQUERY
from routes.auth import get_session

router = APIRouter()

DIAS_VALIDOS = {"lun", "mar", "mie", "jue", "vie", "sab", "dom"}
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ── Helpers ──────────────────────────────────────────────────────────────────

def require_admin(request: Request) -> dict:
    session = get_session(request)
    if not session:
        raise HTTPException(401, "No autenticado")
    return session


def _validar_horarios(value: str) -> str:
    """Valida y normaliza el JSON de horarios habilitados.

    Forma: { "lun": {"desde":"08:00","hasta":"18:00"}, ..., "dom": null }.
    `null` en un día = cerrado. Cada franja exige desde < hasta en HH:MM."""
    try:
        data = json.loads(value)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"horarios_retiro debe ser JSON válido ({e})")
    if not isinstance(data, dict):
        raise HTTPException(400, "horarios_retiro debe ser un objeto por día")
    out: dict = {}
    for dia, franja in data.items():
        if dia not in DIAS_VALIDOS:
            raise HTTPException(400, f"Día inválido: '{dia}'")
        if franja is None:
            out[dia] = None
            continue
        if not isinstance(franja, dict) or "desde" not in franja or "hasta" not in franja:
            raise HTTPException(400, f"Franja inválida para '{dia}'")
        desde, hasta = str(franja["desde"]), str(franja["hasta"])
        if not _HHMM.match(desde) or not _HHMM.match(hasta):
            raise HTTPException(400, f"Horas inválidas para '{dia}' (formato HH:MM)")
        if desde >= hasta:
            raise HTTPException(400, f"'{dia}': la apertura debe ser anterior al cierre")
        out[dia] = {"desde": desde, "hasta": hasta}
    return json.dumps(out)


def _validar_hero_taglines(value: str) -> str:
    """Valida el JSON de taglines del hero.

    Forma: [["línea 1", "línea 2"], ...]. Mínimo 1, máximo 12."""
    try:
        data = json.loads(value)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"hero_taglines debe ser JSON válido ({e})")
    if not isinstance(data, list) or len(data) == 0:
        raise HTTPException(400, "hero_taglines debe ser una lista con al menos un tagline")
    if len(data) > 12:
        raise HTTPException(400, "hero_taglines no puede tener más de 12 taglines")
    out = []
    for item in data:
        if not isinstance(item, list) or len(item) != 2:
            raise HTTPException(400, "Cada tagline debe ser una lista de exactamente 2 strings")
        l1, l2 = str(item[0]).strip(), str(item[1]).strip()
        if not l1 or not l2:
            raise HTTPException(400, "Cada línea del tagline debe tener texto")
        out.append([l1, l2])
    return json.dumps(out, ensure_ascii=False)


def _validar_faq(value: str) -> str:
    """Valida y normaliza el JSON de preguntas frecuentes.

    Forma: [{ "title": str, "items": [{ "q": str, "a": str }] }]."""
    try:
        data = json.loads(value)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"faq_json debe ser JSON válido ({e})")
    if not isinstance(data, list):
        raise HTTPException(400, "faq_json debe ser una lista de grupos")
    out = []
    for g in data:
        if not isinstance(g, dict):
            raise HTTPException(400, "Cada grupo debe ser un objeto")
        title = str(g.get("title", "")).strip()
        if not title:
            raise HTTPException(400, "Cada grupo necesita un título")
        items_in = g.get("items", [])
        if not isinstance(items_in, list):
            raise HTTPException(400, f"'{title}': items debe ser una lista")
        items_out = []
        for it in items_in:
            if not isinstance(it, dict):
                raise HTTPException(400, f"'{title}': cada pregunta debe ser un objeto")
            q = str(it.get("q", "")).strip()
            a = str(it.get("a", "")).strip()
            if not q or not a:
                raise HTTPException(400, f"'{title}': cada pregunta necesita texto y respuesta")
            items_out.append({"q": q, "a": a})
        out.append({"title": title, "items": items_out})
    return json.dumps(out, ensure_ascii=False)


def _validar_comisiones(value: str) -> str:
    """Valida el modelo de reparto de comisiones (#88) y lo re-serializa.
    La forma/validación canónica vive en el motor de reportes."""
    from reportes.comisiones import validar_modelo

    try:
        data = json.loads(value)
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(400, f"comisiones_modelo debe ser JSON válido ({e})")
    try:
        validar_modelo(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return json.dumps(data, ensure_ascii=False)


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
    "og_image_url",      # URL pública del OG image para preview en redes (1200x630).
    # ── Marca: SVG masters + assets derivados (motor services/branding) ──
    "wordmark_svg_url",       # SVG master del wordmark (subido desde el back-office). URL R2.
    "wordmark_svg",           # SVG del wordmark saneado (texto) → logo inline de la web + PDFs.
    "isologo_svg_url",        # SVG master del isologo.
    "email_logo_url",         # Wordmark blanco/transparente derivado → header del mail.
    "favicon_url",            # Favicon derivado del isologo (tile amber + ink).
    "apple_touch_icon_url",   # Ícono iOS derivado del isologo.
    "icon_512_url",           # Ícono cuadrado 512 derivado del isologo (no es el og:image).
    "whatsapp_phone",    # Teléfono del negocio para click-to-chat (formato +5492235852510).
    "email_from",        # From address de mails ('Rambla <pedidos@rambla.com.uy>'). Pisado por env EMAIL_FROM.
    "email_admin_to",    # Destinatario de notif al admin cuando entra un pedido. Pisado por env EMAIL_ADMIN_TO.
    "buffer_horas_alquiler",  # Horas de prep/revisión exigidas entre alquileres. Int >= 0.
    "horarios_retiro",   # Horas habilitadas de retiro/devolución por día de semana. JSON.
    "faq_json",          # Preguntas frecuentes editables. JSON [{title, items:[{q,a}]}].
    "hero_taglines",     # Taglines del hero del catálogo. JSON [[línea1, línea2], ...].
    # ── Datos del negocio (editables desde "Diseño y marca") ─────────
    # Si vienen vacíos en el frontend, el hook useBusinessContact cae al
    # default hardcodeado en src/data/contact.ts.
    "business_address",        # Dirección free-form display ("Calle X 123, Mar del Plata").
    "business_maps_url",       # URL absoluta a Google Maps con la ubicación.
    "business_phone_display",  # Display human-readable del teléfono ("+54 9 223 585 2510").
    "business_email",          # Email de contacto público ("hola@rambla.studio").
    "business_instagram",      # Handle de IG sin @ ("ramblarental").
    # ── Analítica ────────────────────────────────────────────────────
    "ga4_measurement_id",      # Measurement ID de Google Analytics 4 ("G-XXXXXXXXXX"). Vacío = GA apagado.
    # ── Facturación electrónica ARCA (#1139) ─────────────────────────
    # Solo los no-secretos (CUIT y PtoVta). Cert/clave van en ENV, nunca acá.
    "afip_pablo_cuit",         # CUIT del emisor Pablo (RI, Factura A). Número sin guiones.
    "afip_pablo_ptovta",       # Punto de venta ARCA de Pablo para Web Services.
    "afip_santini_cuit",       # CUIT del emisor Santini (Monotributo, Factura C).
    "afip_santini_ptovta",     # Punto de venta ARCA de Santini para Web Services.
    # ── Reportes ─────────────────────────────────────────────────────
    "comisiones_modelo",       # Reparto de ingresos por dueño (#88). JSON {dueño: {beneficiario: %}}.
    # ── Recordatorio de retiro (Fase B mails) ────────────────────────
    # Control del job "mañana retirás" desde la UI. Override por env
    # (REMINDERS_ENABLED/REMINDERS_HOUR/REMINDERS_DIAS_ANTES) — ver
    # jobs/recordatorios_config.py. Lo resuelve el scheduler en runtime.
    "recordatorios_enabled",      # Encendido del recordatorio automático. "1"/"0".
    "recordatorios_hora",         # Hora AR del barrido diario. Int 0-23.
    "recordatorios_dias_antes",   # Días de anticipación. Int 1-14.
}

# Keys cuyo valor puede borrarse (volver al default) desde la UI. El resto
# rechaza string vacía para no romper cálculos / settings críticas.
CLEARABLE_SETTINGS_KEYS = {
    "business_address",
    "business_maps_url",
    "business_phone_display",
    "business_email",
    "business_instagram",
    "ga4_measurement_id",  # Vaciarlo apaga Google Analytics.
}

# Formato de un Measurement ID de GA4: 'G-' seguido de alfanuméricos.
_GA4_ID = re.compile(r"^G-[A-Z0-9]{4,}$")


@router.get("/analytics-config")
def analytics_config():
    """Config pública de analítica para el front del catálogo.

    Devuelve el Measurement ID de GA4 SOLO en producción. En staging (`dev`,
    que corre con una BD copiada de prod) y en local devuelve `null` para no
    contaminar las analíticas de prod con tráfico de prueba. El `ga4_id` no es
    secreto (queda visible en el HTML del sitio público), así que es lectura
    abierta — el único gate es el ambiente."""
    from config import settings as app_settings

    if not app_settings.is_production:
        return {"ga4_id": None}
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", ("ga4_measurement_id",)
        ).fetchone()
        value = row["value"].strip() if row and row["value"] else None
        return {"ga4_id": value or None}


@router.get("/settings/{key}")
def get_setting(key: str):
    """Devuelve el valor de una setting. Lectura pública (el USD rate
    afecta cálculos en el frontend público también)."""
    if key not in ALLOWED_SETTINGS_KEYS:
        raise HTTPException(404, f"Setting '{key}' no existe")
    with get_db() as conn:
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


@router.get("/settings")
def list_settings():
    """Lista todas las settings públicas. Útil para el panel admin."""
    with get_db() as conn:
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


@router.put("/admin/settings/{key}")
def update_setting(key: str, payload: dict, request: Request):
    """Actualiza una setting (solo admin)."""
    session = require_admin(request)
    if key not in ALLOWED_SETTINGS_KEYS:
        raise HTTPException(400, f"Setting '{key}' no es editable")
    value = payload.get("value")
    is_empty = value is None or str(value).strip() == ""
    if is_empty:
        if key not in CLEARABLE_SETTINGS_KEYS:
            raise HTTPException(400, "El valor no puede estar vacío")
        # Para claves "limpiables" borrar la fila → cae al default del cliente.
        with get_db() as conn:
            conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
            conn.commit()
            return {"key": key, "value": "", "updated_by": None}
    value = str(value).strip()
    # Validaciones livianas para datos de contacto (display-only).
    if key == "business_email" and "@" not in value:
        raise HTTPException(400, "Email inválido (falta @)")
    if key == "business_instagram":
        # Aceptamos con o sin @, lo normalizamos sin @.
        value = value.lstrip("@")
        if not value:
            raise HTTPException(400, "Handle de Instagram vacío")
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
    if key == "recordatorios_enabled":
        # Checkbox → normalizamos a "1"/"0".
        value = "1" if value.lower() in ("1", "true", "yes", "on") else "0"
    if key == "recordatorios_hora":
        try:
            v = int(value)
            if not (0 <= v <= 23):
                raise ValueError("fuera de rango 0-23")
            value = str(v)
        except (ValueError, TypeError) as e:
            raise HTTPException(400, f"Valor inválido para '{key}': hora entre 0 y 23 ({e})")
    if key == "recordatorios_dias_antes":
        try:
            v = int(value)
            if not (1 <= v <= 14):
                raise ValueError("fuera de rango 1-14")
            value = str(v)
        except (ValueError, TypeError) as e:
            raise HTTPException(400, f"Valor inválido para '{key}': días entre 1 y 14 ({e})")
    if key == "ga4_measurement_id":
        # GA4 IDs son case-insensitive pero conviven mejor en mayúscula.
        value = value.upper()
        if not _GA4_ID.match(value):
            raise HTTPException(
                400,
                "Measurement ID inválido. Tiene que ser como 'G-XXXXXXXXXX' "
                "(lo sacás de Google Analytics → Admin → Flujos de datos → Web).",
            )
    if key == "horarios_retiro":
        value = _validar_horarios(value)
    if key == "faq_json":
        value = _validar_faq(value)
    if key == "hero_taglines":
        value = _validar_hero_taglines(value)
    if key == "comisiones_modelo":
        value = _validar_comisiones(value)
    actor = (session.get("email") or session.get("user_id") or "admin")[:255]
    with get_db() as conn:
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
            # El motor de reservas cachea el buffer global → invalidar al cambiarlo
            # para que la próxima cotización/confirmación use el valor nuevo.
            if key == "buffer_horas_alquiler":
                from reservas import invalidate_buffer_cache
                invalidate_buffer_cache()
            return {"key": key, "value": value, "updated_by": actor}
        except Exception:
            conn.rollback()
            raise


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

    with get_db() as conn:
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


@router.get("/admin/equipos/precios-manuales")
def listar_precios_manuales(request: Request):
    """Devuelve todos los equipos con `precio_jornada_manual = TRUE`,
    junto con el precio que daría la fórmula con el USD rate actual.
    Útil para revisar uno por uno qué hacer cuando se actualiza el USD."""
    require_admin(request)
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", ("usd_rate",)
        ).fetchone()
        usd_rate = float(row["value"]) if row else 0.0

        rows = conn.execute(
            f"""
            SELECT e.id, e.nombre, {MARCA_SUBQUERY}, e.modelo, e.foto_url,
                   e.precio_jornada, e.precio_usd, e.roi_pct
            FROM equipos e
            WHERE e.precio_jornada_manual = TRUE
            ORDER BY LOWER(e.nombre)
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



# ── Upload de imágenes a R2 (OG image) ────────────────────────────────────────
# El logo del sitio ya NO se sube como imagen: se unificó en el SVG master del
# wordmark (sección "Marca (SVG)" → setting `wordmark_svg`), que la web inyecta
# inline. Ver `services/branding` + `upload-wordmark`.

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


@router.post("/admin/settings/upload-og-image")
async def upload_og_image(request: Request):
    """Sube imagen como preview de Open Graph (1200x630) y guarda la URL
    en `app_settings.og_image_url`.

    Es la imagen que ven WhatsApp / IG / Facebook al compartir el link de
    la home. Path fijo en R2 + cache-buster (?v=<ts>).
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

    from services.media.storage import put as _r2_put
    from services.media_fastapi import media_http
    with media_http():
        public_url = _r2_put(path, content, ctype)

    import time as _time
    versioned_url = f"{public_url}?v={int(_time.time())}"

    with get_db() as conn:
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


# ── Marca: subir SVG (wordmark + isologo) → derivar assets ────────────────────

def _save_settings(conn, mapping: dict, actor: str) -> None:
    """Upsert de varias settings en una transacción."""
    for key, value in mapping.items():
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at, updated_by)
            VALUES (%s, %s, CURRENT_TIMESTAMP, %s)
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = EXCLUDED.updated_by
            """,
            (key, value, actor),
        )
    conn.commit()


async def _upload_brand_svg(request: Request, kind: str):
    """Sube un SVG master de marca (`wordmark` | `isologo`) a R2 y deriva los
    assets raster que consume el sistema (mail / favicon / íconos).

    Solo acepta SVG: es la fuente vectorial themable de la que se rasteriza todo
    (motor `services.branding`). El master + cada derivado se guardan en
    `app_settings` con su URL versionada (cache-buster).
    """
    from services.branding import derive_from_isologo, derive_from_wordmark, sanitize_svg
    from services.media.storage import put as _r2_put
    from services.media_fastapi import media_http

    session = require_admin(request)
    actor = (session.get("email") or session.get("user_id") or "admin")[:255]

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file'")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Archivo vacío")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "Archivo muy grande (máx 5MB)")

    filename = (getattr(file, "filename", "") or "").lower()
    ctype_in = (getattr(file, "content_type", "") or "").lower()
    is_svg = filename.endswith(".svg") or "svg" in ctype_in or b"<svg" in raw[:1024].lower()
    if not is_svg:
        raise HTTPException(400, "Solo se admite SVG (es la fuente vectorial de la marca)")

    try:
        svg_text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "El SVG no es UTF-8 válido")

    # Master a R2 (path fijo → sobreescribe).
    with media_http():
        master_url = _r2_put(f"branding/{kind}.svg", raw, "image/svg+xml")
    import time as _time

    master_key = f"{kind}_svg_url"
    settings_out = {master_key: f"{master_url}?v={int(_time.time())}"}

    # Derivar los assets raster del master.
    try:
        if kind == "wordmark":
            settings_out.update(await derive_from_wordmark(svg_text))
            # SVG saneado como texto → lo inyectan inline el logo de la web
            # (themable vía currentColor) y, en el follow-up, los PDFs.
            settings_out["wordmark_svg"] = sanitize_svg(svg_text)
        else:
            settings_out.update(await derive_from_isologo(svg_text))
    except Exception as e:
        raise HTTPException(500, f"No se pudieron derivar los assets: {e}")

    with get_db() as conn:
        _save_settings(conn, settings_out, actor)
    return {"ok": True, "settings": settings_out}


@router.post("/admin/settings/upload-wordmark")
async def upload_wordmark(request: Request):
    """SVG del wordmark → deriva el logo del mail (blanco sobre transparente)."""
    return await _upload_brand_svg(request, "wordmark")


@router.post("/admin/settings/upload-isologo")
async def upload_isologo(request: Request):
    """SVG del isologo → deriva favicon + apple-touch + icon-512 (tile amber + ink)."""
    return await _upload_brand_svg(request, "isologo")


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
