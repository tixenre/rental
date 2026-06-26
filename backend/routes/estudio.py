"""
routes/estudio.py — CRUD del Estudio (singleton) + galería de fotos (E1)
                    + trabajos/producciones (galería "en acción").
"""

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from pydantic import BaseModel

from admin_guard import require_admin
from database import MARCA_SUBQUERY, get_db, now_ar, to_datetime
from routes.clientes import nombre_completo_cliente
from reservas import ESTADOS_RESERVADO, validar_stock as _check_stock
from routes.alquileres import (
    _dispatch_pedido_creado_emails,
    _get_alquiler_detail,
    _next_numero_pedido,
    get_disponibilidad,
)
from services.media.security import _download_image_bytes, _validate_ssrf_only
from services.media.storage import delete_object as _delete_from_r2
from services.media import (
    DISPLAY_KEEP_ASPECT,
    DISPLAY_KEEP_ASPECT_AVIF,
    DISPLAY_KEEP_ASPECT_SM,
    DISPLAY_KEEP_ASPECT_SM_AVIF,
    collect_asset_keys,
    purge_r2,
    store_upload,
)
from services.media_fastapi import media_http

router = APIRouter()


# ── Helpers internos ─────────────────────────────────────────────────────────

def _foto_path_estudio() -> str:
    ts = int(time.time() * 1000)
    return f"estudio/{ts}.webp"


def _get_estudio_row(conn):
    cur = conn.execute("SELECT * FROM estudio WHERE id = 1")
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Fila estudio no encontrada — ejecutá init_db")
    return row


def _require_cliente(request):
    """Guard de cliente logueado (mismo que /api/cliente/pedidos). Import diferido
    para no acoplar el módulo a toda la cadena del portal; envuelto en helper para
    ser patcheable en tests."""
    from routes.cliente_portal import require_cliente
    return require_cliente(request)


def _get_fotos(conn) -> list:
    cur = conn.execute(
        "SELECT id, url, url_sm, url_avif, url_sm_avif, path, orden, es_principal, created_at "
        "FROM estudio_fotos WHERE estudio_id = 1 ORDER BY orden, id",
        (),
    )
    rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "url": r["url"],
            "url_sm": r["url_sm"],
            "url_avif": r["url_avif"],
            "url_sm_avif": r["url_sm_avif"],
            "path": r["path"],
            "orden": r["orden"],
            "es_principal": bool(r["es_principal"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


def _parse_json_field(value) -> list | None:
    if not value:
        return None
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


def _build_response(row, fotos: list) -> dict:
    return {
        "id": row["id"],
        "equipo_id": row["equipo_id"],
        "nombre": row["nombre"],
        "tagline": row["tagline"],
        "descripcion": row["descripcion"],
        "precio_hora": row["precio_hora"],
        "min_horas": row["min_horas"],
        "open_hour": row["open_hour"],
        "close_hour": row["close_hour"],
        "buffer_horas": row["buffer_horas"],
        "anticipacion_min_horas": row["anticipacion_min_horas"],
        "pack_activo": bool(row["pack_activo"]),
        "pack_nombre": row["pack_nombre"],
        "pack_descripcion": row["pack_descripcion"],
        "pack_precio": row["pack_precio"],
        "features": _parse_json_field(row["features_json"]),
        "faq": _parse_json_field(row["faq_json"]),
        "direccion": row["direccion"],
        "como_llegar": row["como_llegar"],
        "testimonios": _parse_json_field(row["testimonios_json"]),
        "mapa_url": row["mapa_url"],
        "mapa_embed_url": row["mapa_embed_url"],
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "fotos": fotos,
    }


def _insert_foto(
    conn,
    url: str,
    path: str,
    media_id: int | None = None,
    url_sm: str | None = None,
    url_avif: str | None = None,
    url_sm_avif: str | None = None,
) -> dict:
    cur = conn.execute(
        "SELECT COALESCE(MAX(orden), -1) + 1 AS next_orden FROM estudio_fotos WHERE estudio_id = 1",
        (),
    )
    orden = cur.fetchone()["next_orden"]

    cur2 = conn.execute("SELECT COUNT(*) AS cnt FROM estudio_fotos WHERE estudio_id = 1", ())
    is_first = cur2.fetchone()["cnt"] == 0

    conn.execute(
        "INSERT INTO estudio_fotos "
        "(estudio_id, url, url_sm, url_avif, url_sm_avif, path, orden, es_principal, media_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1, url, url_sm, url_avif, url_sm_avif, path, orden, is_first, media_id),
    )
    conn.commit()

    cur3 = conn.execute(
        "SELECT id, url, url_sm, url_avif, url_sm_avif, path, orden, es_principal, created_at "
        "FROM estudio_fotos WHERE path = ? AND estudio_id = 1",
        (path,),
    )
    r = cur3.fetchone()
    return {
        "id": r["id"],
        "url": r["url"],
        "url_sm": r["url_sm"],
        "url_avif": r["url_avif"],
        "url_sm_avif": r["url_sm_avif"],
        "path": r["path"],
        "orden": r["orden"],
        "es_principal": bool(r["es_principal"]),
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    }


# ── Endpoint público ─────────────────────────────────────────────────────────

def _get_trabajos(conn, solo_activos: bool = True) -> list:
    q = (
        "SELECT id, titulo, realizador, realizador_logo_url, "
        "realizador_instagram, realizador_web, categoria, descripcion, "
        "tipo, youtube_url, fotos_json, orden, activo, created_at, updated_at "
        "FROM estudio_trabajos "
    )
    q += "WHERE activo = TRUE " if solo_activos else ""
    q += "ORDER BY orden, id"
    cur = conn.execute(q)
    rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "titulo": r["titulo"],
            "realizador": r["realizador"],
            "realizador_logo_url": r["realizador_logo_url"],
            "realizador_instagram": r["realizador_instagram"],
            "realizador_web": r["realizador_web"],
            "categoria": r["categoria"] or "",
            "descripcion": r["descripcion"] or "",
            "tipo": r["tipo"],
            "youtube_url": r["youtube_url"],
            "fotos": _parse_json_field(r["fotos_json"]) or [],
            "orden": r["orden"],
            "activo": bool(r["activo"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]


@router.get("/estudio")
def get_estudio(response: Response):
    """Devuelve la configuración pública del estudio + fotos + pack curado + trabajos."""
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=30"
    with get_db() as conn:
        row = _get_estudio_row(conn)
        fotos = _get_fotos(conn)
        resp = _build_response(row, fotos)
        resp["pack_equipos"] = _pack_curado(conn)
        resp["trabajos"] = _get_trabajos(conn, solo_activos=True)
        return resp


# ── Endpoints admin ──────────────────────────────────────────────────────────

@router.get("/admin/estudio")
def get_estudio_admin(request: Request):
    """Versión admin del GET /estudio — sin Cache-Control público (el endpoint
    público está cacheado 5min en Cloudflare, lo que causaba que subir/borrar
    fotos no se reflejara hasta que el caché expirara)."""
    require_admin(request)
    with get_db() as conn:
        row = _get_estudio_row(conn)
        fotos = _get_fotos(conn)
        resp = _build_response(row, fotos)
        resp["pack_equipos"] = _pack_curado(conn)
        resp["trabajos"] = _get_trabajos(conn, solo_activos=False)
        return resp

class EstudioUpdate(BaseModel):
    nombre: Optional[str] = None
    tagline: Optional[str] = None
    descripcion: Optional[str] = None
    precio_hora: Optional[int] = None
    min_horas: Optional[int] = None
    open_hour: Optional[int] = None
    close_hour: Optional[int] = None
    buffer_horas: Optional[int] = None
    anticipacion_min_horas: Optional[int] = None
    pack_activo: Optional[bool] = None
    pack_nombre: Optional[str] = None
    pack_descripcion: Optional[str] = None
    pack_precio: Optional[int] = None
    features_json: Optional[str] = None
    faq_json: Optional[str] = None
    direccion: Optional[str] = None
    como_llegar: Optional[str] = None
    testimonios_json: Optional[str] = None
    # Link de Google Maps que pega el dueño (shortlink, URL larga o iframe HTML).
    # El backend lo parsea/resuelve y deriva `mapa_embed_url`.
    mapa_url: Optional[str] = None


@router.patch("/admin/estudio")
def patch_estudio(body: EstudioUpdate, request: Request):
    require_admin(request)

    updates = {k: v for k, v in body.dict().items() if v is not None}

    # Si el dueño cambió `mapa_url`, derivamos `mapa_embed_url`. Si lo dejó vacío,
    # vaciamos ambos.
    if "mapa_url" in updates:
        from services.maps_url import MapsParseError, parse_maps_input

        raw = (updates["mapa_url"] or "").strip()
        if not raw:
            updates["mapa_url"] = ""
            updates["mapa_embed_url"] = ""
        else:
            try:
                parsed = parse_maps_input(raw)
            except MapsParseError as e:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"No pude leer ese link de Google Maps: {e}. "
                        "Probá copiar 'Compartir → Insertar mapa' (código iframe) "
                        "o el link que da 'Compartir' en la app de Maps."
                    ),
                ) from e
            updates["mapa_url"] = parsed.raw_url
            updates["mapa_embed_url"] = parsed.embed_url

    with get_db() as conn:
        if updates:
            set_parts = [f"{k} = ?" for k in updates]
            set_parts.append("updated_at = ?")
            values = list(updates.values())
            values.append(datetime.now(tz=timezone.utc))
            values.append(1)
            conn.execute(
                f"UPDATE estudio SET {', '.join(set_parts)} WHERE id = ?",
                tuple(values),
            )
            conn.commit()
        row = _get_estudio_row(conn)
        fotos = _get_fotos(conn)
        return _build_response(row, fotos)


@router.post("/admin/estudio/upload-foto")
async def upload_foto(request: Request):
    """Sube un archivo (multipart, campo 'file') a R2 y lo registra en estudio_fotos."""
    require_admin(request)

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file' en el form-data")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Archivo vacío")
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(413, "Archivo muy grande (máx 20 MB)")

    with get_db() as conn:
        try:
            with media_http():
                asset = store_upload(
                    raw,
                    kind="estudio",
                    derive_specs=[
                        DISPLAY_KEEP_ASPECT,
                        DISPLAY_KEEP_ASPECT_SM,
                        DISPLAY_KEEP_ASPECT_AVIF,
                        DISPLAY_KEEP_ASPECT_SM_AVIF,
                    ],
                    conn=conn,
                )
            display = asset.variant("display")
            display_sm = asset.variant("display-sm")
            display_avif = asset.variant("display-avif")
            display_sm_avif = asset.variant("display-sm-avif")
            foto = _insert_foto(
                conn,
                url=display.url,
                path=display.key,
                media_id=asset.id,
                url_sm=display_sm.url if display_sm else None,
                url_avif=display_avif.url if display_avif else None,
                url_sm_avif=display_sm_avif.url if display_sm_avif else None,
            )
        except Exception:
            conn.rollback()
            raise

    return {
        "id": foto["id"],
        "public_url": display.url,
        "path": display.key,
        "size": display.bytes,
        "size_original": len(raw),
        "content_type": display.content_type,
        "width": display.width or None,
        "height": display.height or None,
    }


class UploadFromUrlBody(BaseModel):
    url: str


@router.post("/admin/estudio/upload-foto-from-url")
def upload_foto_from_url(body: UploadFromUrlBody, request: Request):
    """Descarga URL externa, optimiza y sube a R2. SSRF-safe."""
    require_admin(request)

    url = (body.url or "").strip()
    if not url:
        raise HTTPException(400, "URL vacía")

    with media_http():
        _validate_ssrf_only(url)
        raw, _raw_ctype = _download_image_bytes(url)

    with get_db() as conn:
        try:
            with media_http():
                asset = store_upload(
                    raw,
                    kind="estudio",
                    derive_specs=[
                        DISPLAY_KEEP_ASPECT,
                        DISPLAY_KEEP_ASPECT_SM,
                        DISPLAY_KEEP_ASPECT_AVIF,
                        DISPLAY_KEEP_ASPECT_SM_AVIF,
                    ],
                    conn=conn,
                )
            display = asset.variant("display")
            display_sm = asset.variant("display-sm")
            display_avif = asset.variant("display-avif")
            display_sm_avif = asset.variant("display-sm-avif")
            foto = _insert_foto(
                conn,
                url=display.url,
                path=display.key,
                media_id=asset.id,
                url_sm=display_sm.url if display_sm else None,
                url_avif=display_avif.url if display_avif else None,
                url_sm_avif=display_sm_avif.url if display_sm_avif else None,
            )
        except Exception:
            conn.rollback()
            raise

    return {
        "id": foto["id"],
        "public_url": display.url,
        "path": display.key,
        "size": display.bytes,
        "size_original": len(raw),
        "content_type": display.content_type,
        "width": display.width or None,
        "height": display.height or None,
    }


@router.delete("/admin/estudio/fotos/{foto_id}")
def delete_foto(foto_id: int, request: Request):
    require_admin(request)

    with get_db() as conn:
        cur = conn.execute(
            "SELECT path, media_id FROM estudio_fotos WHERE id = ? AND estudio_id = 1",
            (foto_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Foto no encontrada")
        path = row["path"]
        media_id = row["media_id"]

        # Recolectar keys R2 ANTES del DELETE (cascade borrará las filas de variants)
        r2_keys: list[str] = []
        if media_id:
            r2_keys = collect_asset_keys(conn, media_id)

        conn.execute("DELETE FROM estudio_fotos WHERE id = ?", (foto_id,))
        if media_id:
            conn.execute("DELETE FROM media_assets WHERE id = ?", (media_id,))
        conn.commit()

    # Best-effort R2 cleanup (después del commit — la DB es la fuente de verdad)
    if r2_keys:
        purge_r2(r2_keys)
    elif path:
        _delete_from_r2(path)  # fallback legacy (fotos sin media_id)

    return {"ok": True}


class FotoOrdenItem(BaseModel):
    id: int
    orden: int
    es_principal: bool


class ReorderBody(BaseModel):
    fotos: list[FotoOrdenItem]


@router.patch("/admin/estudio/fotos/orden")
def reorder_fotos(body: ReorderBody, request: Request):
    require_admin(request)

    with get_db() as conn:
        for f in body.fotos:
            conn.execute(
                "UPDATE estudio_fotos SET orden = ?, es_principal = ? "
                "WHERE id = ? AND estudio_id = 1",
                (f.orden, f.es_principal, f.id),
            )
        conn.commit()
        fotos = _get_fotos(conn)

    return {"fotos": fotos}


# ── Trabajos / producciones (galería "en acción") ────────────────────────────

def _trabajo_path(suffix: str) -> str:
    ts = int(time.time() * 1000)
    return f"estudio/trabajos/{ts}_{suffix}.webp"


@router.get("/admin/estudio/trabajos")
def admin_list_trabajos(request: Request):
    require_admin(request)
    with get_db() as conn:
        return {"trabajos": _get_trabajos(conn, solo_activos=False)}


class TrabajoCreate(BaseModel):
    titulo: str = ""
    realizador: str = ""
    realizador_instagram: Optional[str] = None
    realizador_web: Optional[str] = None
    categoria: str = ""
    descripcion: str = ""
    tipo: str = "fotos"
    youtube_url: Optional[str] = None
    activo: bool = True


@router.post("/admin/estudio/trabajos")
def admin_create_trabajo(body: TrabajoCreate, request: Request):
    require_admin(request)
    with get_db() as conn:
        cur = conn.execute(
            "SELECT COALESCE(MAX(orden), -1) + 1 AS next FROM estudio_trabajos"
        )
        orden = cur.fetchone()["next"]
        cur2 = conn.execute(
            "INSERT INTO estudio_trabajos "
            "(titulo, realizador, realizador_instagram, realizador_web, "
            "categoria, descripcion, tipo, youtube_url, orden, activo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (body.titulo, body.realizador, body.realizador_instagram, body.realizador_web,
             body.categoria, body.descripcion, body.tipo, body.youtube_url, orden, body.activo),
        )
        new_id = cur2.fetchone()["id"]
        conn.commit()
        rows = _get_trabajos(conn, solo_activos=False)
        return next(r for r in rows if r["id"] == new_id)


class TrabajoUpdate(BaseModel):
    titulo: Optional[str] = None
    realizador: Optional[str] = None
    realizador_instagram: Optional[str] = None
    realizador_web: Optional[str] = None
    categoria: Optional[str] = None
    descripcion: Optional[str] = None
    tipo: Optional[str] = None
    youtube_url: Optional[str] = None
    activo: Optional[bool] = None


@router.patch("/admin/estudio/trabajos/{trabajo_id}")
def admin_update_trabajo(trabajo_id: int, body: TrabajoUpdate, request: Request):
    require_admin(request)
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Nada que actualizar")
    with get_db() as conn:
        set_parts = [f"{k} = ?" for k in updates]
        set_parts.append("updated_at = ?")
        vals = list(updates.values()) + [datetime.now(tz=timezone.utc), trabajo_id]
        conn.execute(
            f"UPDATE estudio_trabajos SET {', '.join(set_parts)} WHERE id = ?",
            vals,
        )
        conn.commit()
        rows = _get_trabajos(conn, solo_activos=False)
        match = next((r for r in rows if r["id"] == trabajo_id), None)
        if not match:
            raise HTTPException(404, "Trabajo no encontrado")
        return match


@router.delete("/admin/estudio/trabajos/{trabajo_id}")
def admin_delete_trabajo(trabajo_id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        conn.execute("DELETE FROM estudio_trabajos WHERE id = ?", (trabajo_id,))
        conn.commit()
    return {"ok": True}


class TrabajoOrdenItem(BaseModel):
    id: int
    orden: int


class TrabajoReorderBody(BaseModel):
    trabajos: list[TrabajoOrdenItem]


@router.patch("/admin/estudio/trabajos/orden")
def admin_reorder_trabajos(body: TrabajoReorderBody, request: Request):
    require_admin(request)
    with get_db() as conn:
        for t in body.trabajos:
            conn.execute(
                "UPDATE estudio_trabajos SET orden = ? WHERE id = ?",
                (t.orden, t.id),
            )
        conn.commit()
        return {"trabajos": _get_trabajos(conn, solo_activos=False)}


@router.post("/admin/estudio/trabajos/{trabajo_id}/upload-foto")
async def admin_upload_trabajo_foto(
    trabajo_id: int, request: Request, background_tasks: BackgroundTasks
):
    require_admin(request)
    path = _trabajo_path(f"foto_{trabajo_id}")
    result = await media_http(
        request,
        background_tasks,
        path=path,
        presets=[
            DISPLAY_KEEP_ASPECT,
            DISPLAY_KEEP_ASPECT_SM,
            DISPLAY_KEEP_ASPECT_AVIF,
            DISPLAY_KEEP_ASPECT_SM_AVIF,
        ],
    )
    nueva_foto = {
        "url": result[DISPLAY_KEEP_ASPECT]["url"],
        "url_sm": result[DISPLAY_KEEP_ASPECT_SM]["url"],
        "url_avif": result[DISPLAY_KEEP_ASPECT_AVIF]["url"],
        "url_sm_avif": result[DISPLAY_KEEP_ASPECT_SM_AVIF]["url"],
        "path": path,
    }
    with get_db() as conn:
        cur = conn.execute(
            "SELECT fotos_json FROM estudio_trabajos WHERE id = ?", (trabajo_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Trabajo no encontrado")
        fotos = _parse_json_field(row["fotos_json"]) or []
        fotos.append(nueva_foto)
        conn.execute(
            "UPDATE estudio_trabajos SET fotos_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(fotos), datetime.now(tz=timezone.utc), trabajo_id),
        )
        conn.commit()
        rows = _get_trabajos(conn, solo_activos=False)
        return next(r for r in rows if r["id"] == trabajo_id)


@router.delete("/admin/estudio/trabajos/{trabajo_id}/fotos/{foto_idx}")
def admin_delete_trabajo_foto(trabajo_id: int, foto_idx: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        cur = conn.execute(
            "SELECT fotos_json FROM estudio_trabajos WHERE id = ?", (trabajo_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Trabajo no encontrado")
        fotos = _parse_json_field(row["fotos_json"]) or []
        if foto_idx < 0 or foto_idx >= len(fotos):
            raise HTTPException(400, f"Índice de foto inválido: {foto_idx}")
        fotos.pop(foto_idx)
        conn.execute(
            "UPDATE estudio_trabajos SET fotos_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(fotos), datetime.now(tz=timezone.utc), trabajo_id),
        )
        conn.commit()
        rows = _get_trabajos(conn, solo_activos=False)
        return next(r for r in rows if r["id"] == trabajo_id)


@router.post("/admin/estudio/trabajos/{trabajo_id}/upload-logo")
async def admin_upload_trabajo_logo(
    trabajo_id: int, request: Request, background_tasks: BackgroundTasks
):
    require_admin(request)
    path = _trabajo_path(f"logo_{trabajo_id}")
    result = await media_http(
        request,
        background_tasks,
        path=path,
        presets=[DISPLAY_KEEP_ASPECT, DISPLAY_KEEP_ASPECT_SM],
    )
    logo_url = result[DISPLAY_KEEP_ASPECT]["url"]
    with get_db() as conn:
        conn.execute(
            "UPDATE estudio_trabajos SET realizador_logo_url = ?, updated_at = ? WHERE id = ?",
            (logo_url, datetime.now(tz=timezone.utc), trabajo_id),
        )
        conn.commit()
        rows = _get_trabajos(conn, solo_activos=False)
        match = next((r for r in rows if r["id"] == trabajo_id), None)
        if not match:
            raise HTTPException(404, "Trabajo no encontrado")
        return match


# ── Reserva del estudio por horas (E2 / E2.1) ─────────────────────────────────
#
# REGLA SAGRADA: el motor de reservas (_check_stock / get_disponibilidad /
# _rango_con_buffer) NO se modifica ni se reusa para el espacio. La reserva del
# estudio es un pedido normal (tipo='estudio') con UN ítem: el equipo centinela
# (estudio.equipo_id, cantidad=1, recurso único).
#
# E2.1 — el solapamiento del centinela se chequea con una query DEDICADA (no vía
# _check_stock), para que el espacio use SOLO su buffer propio (estudio.buffer_horas)
# y nunca el buffer global de equipos (buffer_horas_alquiler, que es el prep de
# equipos del pack — eso es E3). Al ser stock=1, un overlap directo alcanza.


def _franja_estudio(estudio, fecha: str, start: str, horas: int) -> tuple[datetime, datetime]:
    """Valida y arma la franja [fecha_desde, fecha_hasta] de una reserva.

    - `horas` debe ser >= min_horas del estudio.
    - La franja [start, start+horas] debe caer dentro de [open_hour, close_hour].

    Devuelve (fecha_desde, fecha_hasta) como datetimes. Lanza HTTPException 400
    si algo no valida.
    """
    min_horas = estudio["min_horas"]
    if horas < min_horas:
        raise HTTPException(400, f"El mínimo de reserva es de {min_horas} horas")
    try:
        hh, mm = (int(x) for x in start.split(":"))
        dia = datetime.strptime(fecha, "%Y-%m-%d")
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(400, "Fecha u hora inválida (esperado fecha=YYYY-MM-DD, start=HH:MM)")

    inicio_min = hh * 60 + mm
    fin_min = inicio_min + horas * 60
    open_h, close_h = estudio["open_hour"], estudio["close_hour"]
    if inicio_min < open_h * 60 or fin_min > close_h * 60:
        raise HTTPException(
            400,
            f"La franja debe estar entre las {open_h:02d}:00 y las {close_h:02d}:00",
        )

    fecha_desde = dia.replace(hour=hh, minute=mm, second=0, microsecond=0)
    fecha_hasta = fecha_desde + timedelta(hours=horas)
    return fecha_desde, fecha_hasta


def _viola_anticipacion(estudio, fecha_desde) -> bool:
    """¿La franja arranca antes de la anticipación mínima exigida por el estudio?
    Solo aplica al estudio (no a equipos). anticipacion_min_horas <= 0 → sin tope."""
    horas = estudio["anticipacion_min_horas"] or 0
    if horas <= 0:
        return False
    return fecha_desde < now_ar() + timedelta(hours=horas)


def _centinela_libre(conn, equipo_id: int, fecha_desde, fecha_hasta,
                     buffer_horas: int, exclude_pedido_id: int | None = None) -> bool:
    """True si el centinela del estudio está libre en [fecha_desde, fecha_hasta],
    aplicando SOLO el buffer propio del estudio (expande el rango por
    `buffer_horas` a cada lado). Query dedicada — NO usa el motor sagrado, así
    el buffer global de equipos no interviene.

    El centinela es un recurso único (stock=1): cualquier reserva activa que se
    pise con la franja expandida (half-open: fecha_desde < hi AND fecha_hasta > lo)
    significa ocupado. `exclude_pedido_id` excluye el propio pedido en el POST.
    """
    lo = fecha_desde - timedelta(hours=max(0, buffer_horas or 0))
    hi = fecha_hasta + timedelta(hours=max(0, buffer_horas or 0))
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM alquiler_items pi
        JOIN alquileres p ON p.id = pi.pedido_id
        WHERE pi.equipo_id = ?
          AND p.estado IN {ESTADOS_RESERVADO}
          AND (? IS NULL OR p.id != ?)
          AND p.fecha_desde < ?
          AND p.fecha_hasta > ?
        """,
        (equipo_id, exclude_pedido_id, exclude_pedido_id, hi, lo),
    ).fetchone()
    return (row["cnt"] or 0) == 0


# ── Pack curado (v2-C) ──────────────────────────────────────────────────────────
#
# El pack es una lista CURADA de equipos elegidos a mano por el admin (tabla
# `estudio_pack_equipos`), no "todo lo de unas categorías". De esos equipos, en
# cada franja se ofrecen SOLO los DISPONIBLES (best-effort: un ocupado no se
# ofrece, pero tampoco bloquea la reserva). Son equipos reales → se rigen por el
# motor sagrado (get_disponibilidad / _check_stock con el buffer GLOBAL de
# equipos). Esto es distinto del espacio (centinela), que usa su propio buffer vía
# _centinela_libre. NO mezclar: espacio = query dedicada; pack = motor.


def _pack_equipo_ids(conn) -> list[int]:
    """IDs de los equipos curados del pack (tabla `estudio_pack_equipos`), en su
    orden. Excluye el centinela y los eliminados (por si quedó alguno colgado)."""
    rows = conn.execute(
        """
        SELECT e.id
        FROM estudio_pack_equipos pe
        JOIN equipos e ON e.id = pe.equipo_id
        WHERE pe.estudio_id = 1
          AND e.es_recurso_interno = FALSE
          AND e.eliminado_at IS NULL
        ORDER BY pe.orden, pe.id
        """,
    ).fetchall()
    return [r["id"] for r in rows]


def _pack_disponible(conn, fecha_desde, fecha_hasta, exclude_pedido_id: int | None = None) -> list[dict]:
    """Equipos curados del pack con >= 1 unidad disponible en la franja. La
    disponibilidad sale del motor sagrado (get_disponibilidad aplica el buffer
    global de equipos), así que lo ya reservado no aparece. Devuelve
    [{id, nombre, marca, foto_url, cantidad}]."""
    pack_ids = _pack_equipo_ids(conn)
    if not pack_ids:
        return []
    disp = get_disponibilidad(
        fecha_desde.isoformat(), fecha_hasta.isoformat(), exclude_pedido_id
    )
    libres = {eid: disp.get(str(eid), 0) for eid in pack_ids if disp.get(str(eid), 0) >= 1}
    if not libres:
        return []
    rows = conn.execute(
        f"""
        SELECT e.id, e.nombre, e.foto_url, {MARCA_SUBQUERY}
        FROM equipos e
        WHERE e.id = ANY(?)
        ORDER BY e.nombre
        """,
        (list(libres.keys()),),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "nombre": r["nombre"],
            "marca": r["marca"],
            "foto_url": r["foto_url"],
            "cantidad": libres[r["id"]],
        }
        for r in rows
    ]


def _pack_curado(conn) -> list[dict]:
    """Lista curada del pack (en orden), con nombre/marca/foto y `cantidad` =
    stock total del equipo en el Rental (lo que muestra la ficha pública como
    "5× C-stand"). Sin filtrar por disponibilidad de franja (eso es del público
    en `_pack_disponible`). Sirve al admin y a la ficha pública."""
    rows = conn.execute(
        f"""
        SELECT pe.equipo_id AS id, pe.orden, e.nombre, e.foto_url, e.cantidad,
               {MARCA_SUBQUERY}
        FROM estudio_pack_equipos pe
        JOIN equipos e ON e.id = pe.equipo_id
        WHERE pe.estudio_id = 1
          AND e.eliminado_at IS NULL
        ORDER BY pe.orden, pe.id
        """,
    ).fetchall()
    return [
        {
            "id": r["id"],
            "nombre": r["nombre"],
            "marca": r["marca"],
            "foto_url": r["foto_url"],
            "cantidad": r["cantidad"],
            "orden": r["orden"],
        }
        for r in rows
    ]


# ── Admin: CRUD del pack curado (v2-C) ──────────────────────────────────────────

@router.get("/admin/estudio/pack")
def listar_pack(request: Request):
    require_admin(request)
    with get_db() as conn:
        return {"pack": _pack_curado(conn)}


class PackEquipoCreate(BaseModel):
    equipo_id: int


@router.post("/admin/estudio/pack", status_code=201)
def agregar_pack_equipo(body: PackEquipoCreate, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            eq = conn.execute(
                "SELECT id, es_recurso_interno, eliminado_at FROM equipos WHERE id = ?",
                (body.equipo_id,),
            ).fetchone()
            if not eq or eq["eliminado_at"] is not None:
                raise HTTPException(404, "Equipo no encontrado")
            if eq["es_recurso_interno"]:
                raise HTTPException(400, "No se puede agregar un recurso interno al pack")
            orden = conn.execute(
                "SELECT COALESCE(MAX(orden), -1) + 1 AS next FROM estudio_pack_equipos WHERE estudio_id = 1"
            ).fetchone()["next"]
            conn.execute(
                "INSERT INTO estudio_pack_equipos (estudio_id, equipo_id, orden) "
                "VALUES (1, ?, ?) ON CONFLICT (estudio_id, equipo_id) DO NOTHING",
                (body.equipo_id, orden),
            )
            conn.commit()
            return {"pack": _pack_curado(conn)}
        except Exception:
            conn.rollback()
            raise


@router.delete("/admin/estudio/pack/{equipo_id}")
def quitar_pack_equipo(equipo_id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            conn.execute(
                "DELETE FROM estudio_pack_equipos WHERE estudio_id = 1 AND equipo_id = ?",
                (equipo_id,),
            )
            conn.commit()
            return {"pack": _pack_curado(conn)}
        except Exception:
            conn.rollback()
            raise


# ── Slots fijos recurrentes mensuales (E4) ─────────────────────────────────────
#
# Un slot fijo (ej. "miércoles 8-20 Filmar $X jun-dic") cumple DOS roles:
#   (a) bloquea su franja para el público mientras el rango de meses esté activo
#       → regla propia (`_slot_bloqueante`), NO usa el motor ni el centinela.
#   (b) genera un pedido por mes (tipo='estudio_fijo') para estadísticas + pagos
#       → registro de facturación, SIN ítem del centinela para no doble-bloquear
#       (el bloqueo ya lo hace (a)).


def _slot_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "cliente": row["cliente"],
        "dia_semana": row["dia_semana"],
        "hora_desde": row["hora_desde"],
        "hora_hasta": row["hora_hasta"],
        "valor_mensual": row["valor_mensual"],
        "mes_desde": row["mes_desde"],
        "mes_hasta": row["mes_hasta"],
        "activo": bool(row["activo"]),
    }


def _mes_actual_ar() -> str:
    n = now_ar()
    return f"{n.year:04d}-{n.month:02d}"


def _iter_meses(mes_desde: str, mes_hasta: str):
    """Itera (year, month) inclusive entre dos 'YYYY-MM'."""
    y0, m0 = int(mes_desde[:4]), int(mes_desde[5:7])
    y1, m1 = int(mes_hasta[:4]), int(mes_hasta[5:7])
    cur = (y0, m0)
    while cur <= (y1, m1):
        yield cur
        y, m = cur
        cur = (y + 1, 1) if m == 12 else (y, m + 1)


def _primer_dia_semana(year: int, month: int, dia_semana: int) -> datetime:
    """Primera fecha del mes cuyo weekday() == dia_semana (0=Lun..6=Dom)."""
    base = datetime(year, month, 1)
    offset = (dia_semana - base.weekday()) % 7
    return base + timedelta(days=offset)


def _slot_bloqueante(conn, fecha_desde, fecha_hasta) -> Optional[str]:
    """Si la franja cae en un slot fijo activo (mismo día de semana, dentro del
    rango de meses y con solape horario), devuelve el `cliente` del slot. Regla
    del slot — NO usa el motor de reservas."""
    dia = fecha_desde.weekday()
    mes = f"{fecha_desde.year:04d}-{fecha_desde.month:02d}"
    # Minutos relativos al día de inicio (no `.hour`): una franja que cierra a
    # medianoche tiene fecha_hasta = 00:00 del día siguiente, y `.hour` daría 0,
    # rompiendo el solape. La resta sí da 1440.
    dia_base = fecha_desde.replace(hour=0, minute=0, second=0, microsecond=0)
    ini = int((fecha_desde - dia_base).total_seconds() // 60)
    fin = int((fecha_hasta - dia_base).total_seconds() // 60)
    rows = conn.execute(
        """
        SELECT cliente, hora_desde, hora_hasta
        FROM estudio_slots_fijos
        WHERE activo = TRUE AND dia_semana = ?
          AND mes_desde <= ? AND mes_hasta >= ?
        """,
        (dia, mes, mes),
    ).fetchall()
    for r in rows:
        if ini < r["hora_hasta"] * 60 and fin > r["hora_desde"] * 60:
            return r["cliente"]
    return None


def _regenerar_pedidos_slot(conn, slot: dict) -> None:
    """(Re)genera un pedido `estudio_fijo` por mes del rango del slot. Preserva
    los pasados y los que ya tienen pagos; borra y recrea los futuros impagos.
    Fecha representativa = primer `dia_semana` del mes a [hora_desde, hora_hasta].
    SIN ítem del centinela (el bloqueo lo hace `_slot_bloqueante`)."""
    slot_id = slot["id"]
    mes_actual = _mes_actual_ar()
    existentes = conn.execute(
        "SELECT id, fecha_desde, monto_pagado FROM alquileres WHERE estudio_slot_id = ?",
        (slot_id,),
    ).fetchall()

    conservados: set[str] = set()
    for e in existentes:
        fd = to_datetime(e["fecha_desde"])
        mes_e = f"{fd.year:04d}-{fd.month:02d}"
        if mes_e < mes_actual or (e["monto_pagado"] or 0) > 0:
            conservados.add(mes_e)  # pasado o con pagos → intocable
        else:
            conn.execute("DELETE FROM alquileres WHERE id = ?", (e["id"],))

    if not slot["activo"]:
        return

    for (y, m) in _iter_meses(slot["mes_desde"], slot["mes_hasta"]):
        mes = f"{y:04d}-{m:02d}"
        if mes < mes_actual or mes in conservados:
            continue
        rep = _primer_dia_semana(y, m, slot["dia_semana"])
        # `timedelta` desde medianoche (no `.replace(hour=...)`): hora_hasta=24
        # (cierre a medianoche, válido) caería en las 00:00 del día siguiente sin
        # romper, mientras que replace(hour=24) lanza ValueError.
        base = rep.replace(hour=0, minute=0, second=0, microsecond=0)
        fd = base + timedelta(hours=slot["hora_desde"])
        fh = base + timedelta(hours=slot["hora_hasta"])
        num = _next_numero_pedido(conn)
        conn.execute(
            """
            INSERT INTO alquileres (cliente_nombre, fecha_desde, fecha_hasta, monto_total,
                                    estado, fuente, tipo, numero_pedido, estudio_slot_id)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (slot["cliente"], fd, fh, slot["valor_mensual"], "confirmado",
             "estudio", "estudio_fijo", num, slot_id),
        )


def _borrar_pedidos_futuros_impagos(conn, slot_id: int) -> None:
    """Borra los pedidos del slot que son de un mes actual-o-futuro y no tienen
    pagos. Los pasados/pagados quedan (su estudio_slot_id se va a NULL al borrar
    el slot, vía FK ON DELETE SET NULL)."""
    mes_actual = _mes_actual_ar()
    rows = conn.execute(
        "SELECT id, fecha_desde, monto_pagado FROM alquileres WHERE estudio_slot_id = ?",
        (slot_id,),
    ).fetchall()
    for e in rows:
        fd = to_datetime(e["fecha_desde"])
        mes_e = f"{fd.year:04d}-{fd.month:02d}"
        if mes_e >= mes_actual and (e["monto_pagado"] or 0) == 0:
            conn.execute("DELETE FROM alquileres WHERE id = ?", (e["id"],))


@router.get("/estudio/disponibilidad")
def estudio_disponibilidad(
    fecha: str = Query(..., description="YYYY-MM-DD"),
    start: str = Query(..., description="HH:MM"),
    horas: int = Query(..., description="Duración en horas (>= min_horas)"),
):
    """¿El estudio está libre en [fecha start, +horas]? Aplica el buffer propio
    del estudio (no el global) y la anticipación mínima. Devuelve {libre, motivo}."""
    with get_db() as conn:
        estudio = _get_estudio_row(conn)

        if not estudio["equipo_id"]:
            raise HTTPException(409, "El estudio todavía no tiene un recurso asociado")

        fecha_desde, fecha_hasta = _franja_estudio(estudio, fecha, start, horas)

        if _viola_anticipacion(estudio, fecha_desde):
            return {
                "libre": False,
                "motivo": f"Necesitás reservar con al menos {estudio['anticipacion_min_horas']} h de anticipación",
                "pack": [],
            }

        slot_cliente = _slot_bloqueante(conn, fecha_desde, fecha_hasta)
        if slot_cliente:
            return {"libre": False, "motivo": f"Reservado: {slot_cliente}", "pack": []}

        if not _centinela_libre(conn, estudio["equipo_id"], fecha_desde, fecha_hasta,
                                estudio["buffer_horas"]):
            return {"libre": False, "motivo": "Ocupado en esa franja", "pack": []}

        # Pack: equipos disponibles en la franja (solo si el pack está activo).
        pack = (
            _pack_disponible(conn, fecha_desde, fecha_hasta)
            if estudio["pack_activo"]
            else []
        )
        return {"libre": True, "motivo": None, "pack": pack}


class EstudioReservaCreate(BaseModel):
    fecha: str
    start: str
    horas: int
    con_pack: bool = False
    # Los datos del cliente NO vienen del body: salen de la sesión + tabla clientes
    # (reserva con login obligatorio, igual que el portal /api/cliente/pedidos).


def _agregar_items_pack(conn, pedido_id: int, fecha_desde, fecha_hasta, pack_ids: list[int]) -> None:
    """Inserta un alquiler_item por cada equipo del pack con stock disponible en
    la franja (cantidad = lo disponible, precio 0 — el pack es valor fijo). Asume
    que las filas de `pack_ids` ya están lockeadas (FOR UPDATE) por el caller."""
    disp = get_disponibilidad(fecha_desde.isoformat(), fecha_hasta.isoformat(), pedido_id)
    for eid in pack_ids:
        qty = disp.get(str(eid), 0)
        if qty >= 1:
            conn.execute(
                """
                INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada, subtotal)
                VALUES (?,?,?,?,?)
                """,
                (pedido_id, eid, qty, 0, 0),
            )


@router.post("/estudio/reservas", status_code=201)
def crear_reserva_estudio(body: EstudioReservaCreate, request: Request, background: BackgroundTasks):
    """Reserva real del estudio por horas. Entra como solicitud
    (estado='presupuesto'), en UNA transacción.

    Requiere CLIENTE LOGUEADO (igual que /api/cliente/pedidos): el cliente_id sale
    de la sesión y nombre/email/teléfono del registro de `clientes` — nunca del body.

    El ESPACIO (centinela) es requisito duro: se valida con _centinela_libre +
    FOR UPDATE (su buffer propio), no con el motor. Los EQUIPOS del pack son
    equipos reales: se validan con el motor sagrado (_check_stock, buffer global).
    Criterio ante race del pack: best-effort — todo lo disponible al confirmar."""
    # Import diferido (mismo motivo que `_require_cliente`): evita acoplar el
    # módulo a toda la cadena del portal en import-time y romper ciclos.
    from routes.cliente_portal import cliente_verificado, IDENTIDAD_NO_VERIFICADA_MSG

    session = _require_cliente(request)
    cliente_id = session["cliente_id"]

    with get_db() as conn:
        try:
            estudio = _get_estudio_row(conn)
            if not estudio["equipo_id"]:
                raise HTTPException(409, "El estudio todavía no tiene un recurso asociado")

            # Datos del cliente desde la cuenta (no del body), mismo formato que create_pedido.
            cli = conn.execute(
                "SELECT nombre, apellido, email, telefono FROM clientes WHERE id = ?",
                (cliente_id,),
            ).fetchone()
            if not cli:
                raise HTTPException(401, "Sesión de cliente inválida")
            # Gate de identidad: mismo criterio que /api/cliente/pedidos, vía la
            # fuente única `cliente_verificado` (no se duplica el chequeo de dni).
            if not cliente_verificado(conn, cliente_id):
                raise HTTPException(403, IDENTIDAD_NO_VERIFICADA_MSG)
            cliente_nombre = nombre_completo_cliente(cli["nombre"], cli["apellido"])
            cliente_email = cli["email"]
            cliente_telefono = cli["telefono"]

            fecha_desde, fecha_hasta = _franja_estudio(
                estudio, body.fecha, body.start, body.horas
            )
            hoy = now_ar().replace(hour=0, minute=0, second=0, microsecond=0)
            if fecha_desde < hoy:
                raise HTTPException(400, "La fecha no puede ser en el pasado")
            if _viola_anticipacion(estudio, fecha_desde):
                raise HTTPException(
                    400,
                    f"Necesitás reservar con al menos {estudio['anticipacion_min_horas']} h de anticipación",
                )

            slot_cliente = _slot_bloqueante(conn, fecha_desde, fecha_hasta)
            if slot_cliente:
                raise HTTPException(409, f"Esa franja está reservada de forma fija ({slot_cliente})")

            con_pack = bool(body.con_pack) and bool(estudio["pack_activo"])
            monto_total = (estudio["precio_hora"] or 0) * body.horas
            if con_pack:
                monto_total += estudio["pack_precio"] or 0

            next_num = _next_numero_pedido(conn)
            cur = conn.execute(
                """
                INSERT INTO alquileres (cliente_id, cliente_nombre, cliente_email, cliente_telefono,
                                        fecha_desde, fecha_hasta, monto_total, estado,
                                        fuente, tipo, estudio_con_pack, numero_pedido)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    cliente_id, cliente_nombre, cliente_email, cliente_telefono,
                    fecha_desde, fecha_hasta, monto_total, "presupuesto",
                    "estudio", "estudio", con_pack, next_num,
                ),
            )
            pedido_id = cur.lastrowid

            # ── Pack PRIMERO (antes del ítem centinela) ─────────────────────────────
            # Así _check_stock solo ve los equipos reales del pack y nunca el
            # centinela → no se mezcla el buffer global con el propio del espacio.
            if con_pack:
                pack_ids = _pack_equipo_ids(conn)
                if pack_ids:
                    # Lock de las filas del pack: serializa contra otras reservas que
                    # toquen estos equipos (su _check_stock también las lockea).
                    conn.execute("SELECT id FROM equipos WHERE id = ANY(?) FOR UPDATE", (pack_ids,))
                    _agregar_items_pack(conn, pedido_id, fecha_desde, fecha_hasta, pack_ids)
                    # Gate del motor (FOR UPDATE). Best-effort: si algo se lo llevó
                    # otro entre el snapshot y el lock, re-snapshoteamos bajo el lock
                    # (ya refleja a los competidores commiteados) en vez de fallar
                    # toda la reserva. El espacio sí es requisito duro (abajo).
                    fd_iso, fh_iso = fecha_desde.isoformat(), fecha_hasta.isoformat()
                    if _check_stock(conn, pedido_id, fd_iso, fh_iso):
                        conn.execute(
                            "DELETE FROM alquiler_items WHERE pedido_id = ? AND equipo_id = ANY(?)",
                            (pedido_id, pack_ids),
                        )
                        _agregar_items_pack(conn, pedido_id, fecha_desde, fecha_hasta, pack_ids)

            # ── Espacio (centinela): requisito DURO ─────────────────────────────────
            conn.execute(
                """
                INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada, subtotal)
                VALUES (?,?,?,?,?)
                """,
                (pedido_id, estudio["equipo_id"], 1, 0, 0),
            )
            # Lock del centinela (recurso único) + chequeo con SU buffer propio. Una
            # 2da reserva concurrente espera el lock y ve la 1ra commiteada.
            conn.execute("SELECT id FROM equipos WHERE id = ? FOR UPDATE", (estudio["equipo_id"],))
            if not _centinela_libre(conn, estudio["equipo_id"], fecha_desde, fecha_hasta,
                                    estudio["buffer_horas"], exclude_pedido_id=pedido_id):
                raise HTTPException(409, "El estudio no está disponible en esa franja")

            conn.commit()
            pedido = _get_alquiler_detail(conn, pedido_id)
        except Exception:
            conn.rollback()
            raise

    _dispatch_pedido_creado_emails(background, pedido)
    return pedido


# ── Admin: CRUD de slots fijos (E4) ────────────────────────────────────────────

class SlotFijoCreate(BaseModel):
    cliente: str
    dia_semana: int
    hora_desde: int
    hora_hasta: int
    valor_mensual: int = 0
    mes_desde: str
    mes_hasta: str
    activo: bool = True


class SlotFijoUpdate(BaseModel):
    cliente: Optional[str] = None
    dia_semana: Optional[int] = None
    hora_desde: Optional[int] = None
    hora_hasta: Optional[int] = None
    valor_mensual: Optional[int] = None
    mes_desde: Optional[str] = None
    mes_hasta: Optional[str] = None
    activo: Optional[bool] = None


_MES_RE = __import__("re").compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _validar_slot(d: dict) -> None:
    """Valida los campos de un slot (los que estén presentes). Lanza 400."""
    if "dia_semana" in d and not (0 <= d["dia_semana"] <= 6):
        raise HTTPException(400, "dia_semana debe estar entre 0 (Lun) y 6 (Dom)")
    for k in ("hora_desde", "hora_hasta"):
        if k in d and not (0 <= d[k] <= 24):
            raise HTTPException(400, f"{k} debe estar entre 0 y 24")
    if "hora_desde" in d and "hora_hasta" in d and d["hora_desde"] >= d["hora_hasta"]:
        raise HTTPException(400, "hora_hasta debe ser posterior a hora_desde")
    for k in ("mes_desde", "mes_hasta"):
        if k in d and not _MES_RE.match(d[k] or ""):
            raise HTTPException(400, f"{k} debe tener formato YYYY-MM")
    if "mes_desde" in d and "mes_hasta" in d and d["mes_desde"] > d["mes_hasta"]:
        raise HTTPException(400, "mes_hasta no puede ser anterior a mes_desde")


def _get_slot(conn, slot_id: int) -> dict:
    row = conn.execute("SELECT * FROM estudio_slots_fijos WHERE id = ?", (slot_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Slot no encontrado")
    return _slot_to_dict(row)


@router.get("/admin/estudio/slots")
def listar_slots(request: Request):
    require_admin(request)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM estudio_slots_fijos ORDER BY activo DESC, dia_semana, hora_desde"
        ).fetchall()
        return {"slots": [_slot_to_dict(r) for r in rows]}


@router.post("/admin/estudio/slots", status_code=201)
def crear_slot(body: SlotFijoCreate, request: Request):
    require_admin(request)
    data = body.dict()
    _validar_slot(data)
    with get_db() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO estudio_slots_fijos
                    (cliente, dia_semana, hora_desde, hora_hasta, valor_mensual,
                     mes_desde, mes_hasta, activo)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (data["cliente"], data["dia_semana"], data["hora_desde"], data["hora_hasta"],
                 data["valor_mensual"], data["mes_desde"], data["mes_hasta"], data["activo"]),
            )
            slot = _get_slot(conn, cur.lastrowid)
            _regenerar_pedidos_slot(conn, slot)
            conn.commit()
            return slot
        except Exception:
            conn.rollback()
            raise


@router.patch("/admin/estudio/slots/{slot_id}")
def actualizar_slot(slot_id: int, body: SlotFijoUpdate, request: Request):
    require_admin(request)
    updates = {k: v for k, v in body.dict().items() if v is not None}
    with get_db() as conn:
        try:
            actual = _get_slot(conn, slot_id)
            merged = {**actual, **updates}
            _validar_slot(merged)
            if updates:
                updates["updated_at"] = now_ar()
                set_parts = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE estudio_slots_fijos SET {set_parts} WHERE id = ?",
                    (*updates.values(), slot_id),
                )
            slot = _get_slot(conn, slot_id)
            _regenerar_pedidos_slot(conn, slot)
            conn.commit()
            return slot
        except Exception:
            conn.rollback()
            raise


@router.delete("/admin/estudio/slots/{slot_id}")
def borrar_slot(slot_id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            _get_slot(conn, slot_id)  # 404 si no existe
            # Borra los pedidos futuros impagos; los pasados/pagados quedan (su
            # estudio_slot_id pasa a NULL por la FK ON DELETE SET NULL).
            _borrar_pedidos_futuros_impagos(conn, slot_id)
            conn.execute("DELETE FROM estudio_slots_fijos WHERE id = ?", (slot_id,))
            conn.commit()
            return {"ok": True}
        except Exception:
            conn.rollback()
            raise
