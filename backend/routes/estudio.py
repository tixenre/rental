"""
routes/estudio.py — CRUD del Estudio (singleton) + galería de fotos (E1).
"""

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel

from admin_guard import require_admin
from database import get_db, now_ar
from routes.alquileres import (
    ESTADOS_RESERVADO,
    _dispatch_pedido_creado_emails,
    _get_alquiler_detail,
    _next_numero_pedido,
)
from routes.equipos import (
    _download_image_bytes,
    _ext_from_ctype,
    _optimize_image,
    _upload_to_r2,
    _validate_ssrf_only,
)

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


def _get_fotos(conn) -> list:
    cur = conn.execute(
        "SELECT id, url, path, orden, es_principal, created_at "
        "FROM estudio_fotos WHERE estudio_id = 1 ORDER BY orden, id",
        (),
    )
    rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "url": r["url"],
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
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "fotos": fotos,
    }


def _insert_foto(conn, url: str, path: str) -> dict:
    cur = conn.execute(
        "SELECT COALESCE(MAX(orden), -1) + 1 AS next_orden FROM estudio_fotos WHERE estudio_id = 1",
        (),
    )
    orden = cur.fetchone()["next_orden"]

    cur2 = conn.execute("SELECT COUNT(*) AS cnt FROM estudio_fotos WHERE estudio_id = 1", ())
    is_first = cur2.fetchone()["cnt"] == 0

    conn.execute(
        "INSERT INTO estudio_fotos (estudio_id, url, path, orden, es_principal) "
        "VALUES (?, ?, ?, ?, ?)",
        (1, url, path, orden, is_first),
    )
    conn.commit()

    cur3 = conn.execute(
        "SELECT id, url, path, orden, es_principal, created_at FROM estudio_fotos "
        "WHERE path = ? AND estudio_id = 1",
        (path,),
    )
    r = cur3.fetchone()
    return {
        "id": r["id"],
        "url": r["url"],
        "path": r["path"],
        "orden": r["orden"],
        "es_principal": bool(r["es_principal"]),
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    }


# ── Endpoint público ─────────────────────────────────────────────────────────

@router.get("/estudio")
def get_estudio():
    """Devuelve la configuración pública del estudio + fotos ordenadas."""
    conn = get_db()
    try:
        row = _get_estudio_row(conn)
        fotos = _get_fotos(conn)
        return _build_response(row, fotos)
    finally:
        conn.close()


# ── Endpoints admin ──────────────────────────────────────────────────────────

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


@router.patch("/admin/estudio")
def patch_estudio(body: EstudioUpdate, request: Request):
    require_admin(request)

    updates = {k: v for k, v in body.dict().items() if v is not None}
    conn = get_db()
    try:
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
    finally:
        conn.close()


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

    content, ctype, w, h = _optimize_image(raw)
    ext = _ext_from_ctype(ctype)
    path = _foto_path_estudio()
    url = _upload_to_r2(path, content, ctype)

    conn = get_db()
    try:
        foto = _insert_foto(conn, url, path)
    finally:
        conn.close()

    return {
        "id": foto["id"],
        "public_url": url,
        "path": path,
        "size": len(content),
        "size_original": len(raw),
        "content_type": ctype,
        "width": w or None,
        "height": h or None,
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

    _validate_ssrf_only(url)

    raw, raw_ctype = _download_image_bytes(url)
    content, ctype, w, h = _optimize_image(raw)
    ext = _ext_from_ctype(ctype)
    path = _foto_path_estudio()
    public_url = _upload_to_r2(path, content, ctype)

    conn = get_db()
    try:
        foto = _insert_foto(conn, public_url, path)
    finally:
        conn.close()

    return {
        "id": foto["id"],
        "public_url": public_url,
        "path": path,
        "size": len(content),
        "size_original": len(raw),
        "content_type": ctype,
        "width": w or None,
        "height": h or None,
    }


@router.delete("/admin/estudio/fotos/{foto_id}")
def delete_foto(foto_id: int, request: Request):
    require_admin(request)

    conn = get_db()
    try:
        cur = conn.execute(
            "SELECT id FROM estudio_fotos WHERE id = ? AND estudio_id = 1",
            (foto_id,),
        )
        if not cur.fetchone():
            raise HTTPException(404, "Foto no encontrada")
        conn.execute("DELETE FROM estudio_fotos WHERE id = ?", (foto_id,))
        conn.commit()
    finally:
        conn.close()

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

    conn = get_db()
    try:
        for f in body.fotos:
            conn.execute(
                "UPDATE estudio_fotos SET orden = ?, es_principal = ? "
                "WHERE id = ? AND estudio_id = 1",
                (f.orden, f.es_principal, f.id),
            )
        conn.commit()
        fotos = _get_fotos(conn)
    finally:
        conn.close()

    return {"fotos": fotos}


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


@router.get("/estudio/disponibilidad")
def estudio_disponibilidad(
    fecha: str = Query(..., description="YYYY-MM-DD"),
    start: str = Query(..., description="HH:MM"),
    horas: int = Query(..., description="Duración en horas (>= min_horas)"),
):
    """¿El estudio está libre en [fecha start, +horas]? Aplica el buffer propio
    del estudio (no el global) y la anticipación mínima. Devuelve {libre, motivo}."""
    conn = get_db()
    try:
        estudio = _get_estudio_row(conn)

        if not estudio["equipo_id"]:
            raise HTTPException(409, "El estudio todavía no tiene un recurso asociado")

        fecha_desde, fecha_hasta = _franja_estudio(estudio, fecha, start, horas)

        if _viola_anticipacion(estudio, fecha_desde):
            return {
                "libre": False,
                "motivo": f"Necesitás reservar con al menos {estudio['anticipacion_min_horas']} h de anticipación",
            }

        if not _centinela_libre(conn, estudio["equipo_id"], fecha_desde, fecha_hasta,
                                estudio["buffer_horas"]):
            return {"libre": False, "motivo": "Ocupado en esa franja"}

        return {"libre": True, "motivo": None}
    finally:
        conn.close()


class EstudioReservaCreate(BaseModel):
    fecha: str
    start: str
    horas: int
    cliente_nombre: str
    cliente_email: Optional[str] = None
    cliente_telefono: Optional[str] = None


@router.post("/estudio/reservas", status_code=201)
def crear_reserva_estudio(body: EstudioReservaCreate, background: BackgroundTasks):
    """Reserva real del estudio por horas. Entra como solicitud
    (estado='presupuesto'). Espejo de create_pedido, en UNA transacción, reusando
    el motor de stock/overlap SAGRADO."""
    conn = get_db()
    try:
        estudio = _get_estudio_row(conn)
        if not estudio["equipo_id"]:
            raise HTTPException(409, "El estudio todavía no tiene un recurso asociado")

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

        monto_total = (estudio["precio_hora"] or 0) * body.horas
        next_num = _next_numero_pedido(conn)
        cur = conn.execute(
            """
            INSERT INTO alquileres (cliente_nombre, cliente_email, cliente_telefono,
                                    fecha_desde, fecha_hasta, monto_total, estado,
                                    fuente, tipo, estudio_con_pack, numero_pedido)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                body.cliente_nombre, body.cliente_email, body.cliente_telefono,
                fecha_desde, fecha_hasta, monto_total, "presupuesto",
                "estudio", "estudio", False, next_num,
            ),
        )
        pedido_id = cur.lastrowid

        conn.execute(
            """
            INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada, subtotal)
            VALUES (?,?,?,?,?)
            """,
            (pedido_id, estudio["equipo_id"], 1, 0, 0),
        )

        # Chequeo final bajo FOR UPDATE para cerrar la race de doble-booking:
        # lockeamos la fila del centinela (recurso único) y recién ahí contamos
        # overlaps. Una 2da reserva concurrente espera el lock y ve la 1ra ya
        # commiteada. Usa SOLO el buffer propio del estudio.
        conn.execute("SELECT id FROM equipos WHERE id = ? FOR UPDATE", (estudio["equipo_id"],))
        if not _centinela_libre(conn, estudio["equipo_id"], fecha_desde, fecha_hasta,
                                estudio["buffer_horas"], exclude_pedido_id=pedido_id):
            raise HTTPException(409, "El estudio no está disponible en esa franja")

        conn.commit()
        pedido = _get_alquiler_detail(conn, pedido_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    _dispatch_pedido_creado_emails(background, pedido)
    return pedido
