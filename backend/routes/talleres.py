"""
routes/talleres.py — Workshops públicos: listing, detalle, upload comprobante,
inscripción + notificaciones por email. Vista admin: inscripciones + edición de contenido.
"""

import csv
import io
import logging
import time
import uuid
from datetime import date as _date

import json as _json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr

from admin_guard import require_admin
from database import get_db, now_ar
from dataio.slug import slugify, slug_unico
from services.email import send_email
from services.email.service import get_admin_to
from services.media.models import DeriveSpec
from services.media.errors import MediaError
from services.media.service import store_upload, store_raw_document

logger = logging.getLogger(__name__)

router = APIRouter()

COMPROBANTE_MAX_MB = 10

_DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fmt_fecha_es(d) -> str:
    """datetime.date → 'sábado 11 de julio'"""
    from datetime import date
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return f"{_DIAS_ES[d.weekday()]} {d.day} de {_MESES_ES[d.month - 1]}"


def _fmt_pesos(n: int) -> str:
    return "$" + f"{n:,}".replace(",", ".")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_taller(conn, slug: str):
    row = conn.execute(
        "SELECT * FROM talleres WHERE slug = %s AND activo = TRUE", (slug,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    return row


def _edicion_lite(row) -> dict:
    """Datos mínimos de una edición para mostrar en la página de otra edición."""
    keys = row.keys()
    return {
        "slug": row["slug"],
        "numero_edicion": row["numero_edicion"] if "numero_edicion" in keys else 1,
        "fecha_inicio": str(row["fecha_inicio"]),
        "fecha_fin": str(row["fecha_fin"]),
        "horario": row["horario"],
        "cupos_total": row["cupos_total"],
        "cupos_confirmados": row["cupos_confirmados"],
        "cupos_disponibles": max(0, row["cupos_total"] - row["cupos_confirmados"]),
        "precio_total": row["precio_total"],
        "precio_sena": row["precio_sena"],
        "pago_alias": row["pago_alias"],
        "pago_cbu": row["pago_cbu"],
        "pago_banco": row["pago_banco"],
        "direccion": row["direccion"],
    }


def _get_sesiones(conn, taller_id: int) -> list:
    rows = conn.execute(
        "SELECT fecha, hora_inicio, hora_fin FROM taller_sesiones "
        "WHERE taller_id = %s ORDER BY fecha, hora_inicio",
        (taller_id,),
    ).fetchall()
    return [
        {"fecha": str(r["fecha"]), "hora_inicio": r["hora_inicio"], "hora_fin": r["hora_fin"]}
        for r in rows
    ]


def _taller_to_dict(row, sesiones=None) -> dict:
    keys = row.keys()
    return {
        "id": row["id"],
        "slug": row["slug"],
        "nombre": row["nombre"],
        "subtitulo": row["subtitulo"],
        "instructor_nombre": row["instructor_nombre"],
        "instructor_bio": row["instructor_bio"],
        "instructor_proyectos": row["instructor_proyectos"],
        "descripcion": row["descripcion"],
        "publico_objetivo": row["publico_objetivo"],
        "programa_teorica": row["programa_teorica"] or [],
        "programa_practica": row["programa_practica"] or [],
        "fecha_inicio": str(row["fecha_inicio"]),
        "fecha_fin": str(row["fecha_fin"]),
        "horario": row["horario"],
        "cupos_total": row["cupos_total"],
        "cupos_confirmados": row["cupos_confirmados"],
        "cupos_disponibles": max(0, row["cupos_total"] - row["cupos_confirmados"]),
        "precio_total": row["precio_total"],
        "precio_sena": row["precio_sena"],
        "pago_alias": row["pago_alias"],
        "pago_cbu": row["pago_cbu"],
        "pago_banco": row["pago_banco"],
        "direccion": row["direccion"],
        "activo": bool(row["activo"]) if "activo" in keys else True,
        "tipo_taller": row["tipo_taller"] if "tipo_taller" in keys else "intensivo",
        "notif_email": row["notif_email"] if "notif_email" in keys else "",
        "instructor_foto_url": row["instructor_foto_url"] if "instructor_foto_url" in keys else "",
        "instructor_media_id": row["instructor_media_id"] if "instructor_media_id" in keys else None,
        "numero_edicion": row["numero_edicion"] if "numero_edicion" in keys else 1,
        "proxima_edicion_slug": row["proxima_edicion_slug"] if "proxima_edicion_slug" in keys else "",
        "sesiones": sesiones if sesiones is not None else [],
    }


# ── Endpoints públicos ────────────────────────────────────────────────────────

@router.get("/talleres")
def list_talleres():
    """Lista todos los talleres activos."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM talleres WHERE activo = TRUE ORDER BY fecha_inicio"
        ).fetchall()
        return [_taller_to_dict(r, _get_sesiones(conn, r["id"])) for r in rows]


@router.get("/talleres/{slug}")
def get_taller(slug: str):
    """Detalle de un taller. Incluye proxima_edicion y edicion_anterior si existen."""
    with get_db() as conn:
        row = _get_taller(conn, slug)
        d = _taller_to_dict(row, _get_sesiones(conn, row["id"]))
        # Proxima edicion
        if d["proxima_edicion_slug"]:
            pr = conn.execute(
                "SELECT * FROM talleres WHERE slug = %s AND activo = TRUE",
                (d["proxima_edicion_slug"],),
            ).fetchone()
            d["proxima_edicion"] = _edicion_lite(pr) if pr else None
        else:
            d["proxima_edicion"] = None
        # Edicion anterior (cualquier taller que apunte a este slug como proxima)
        ant = conn.execute(
            "SELECT * FROM talleres WHERE proxima_edicion_slug = %s AND activo = TRUE LIMIT 1",
            (slug,),
        ).fetchone()
        d["edicion_anterior"] = _edicion_lite(ant) if ant else None
    return d


@router.post("/talleres/{slug}/upload-comprobante")
async def upload_comprobante(slug: str, request: Request):
    """Recibe el comprobante de pago (multipart, campo 'file') y lo sube a R2 privado.
    Devuelve URL prefirmada (24h) + key. No requiere auth — parte del flujo de inscripción."""
    with get_db() as conn:
        _get_taller(conn, slug)

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file' en el form-data")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Archivo vacío")
    if len(raw) > COMPROBANTE_MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"Archivo muy grande (máx {COMPROBANTE_MAX_MB} MB)")

    content_type = getattr(file, "content_type", None) or "application/octet-stream"
    ts = int(time.time() * 1000)
    uid = uuid.uuid4().hex[:8]
    ref = f"{slug}-{ts}-{uid}"

    try:
        key, url = store_raw_document(raw, kind="comprobante-taller", ref=ref, content_type=content_type)
    except MediaError as e:
        raise HTTPException(e.status, e.detail)
    except Exception as e:
        logger.error("upload_comprobante: error inesperado: %s", e, exc_info=True)
        raise HTTPException(502, "No se pudo subir el archivo. Intentá de nuevo.")

    return {"url": url, "key": key}


class InscripcionBody(BaseModel):
    nombre: str
    email: EmailStr
    telefono: str
    experiencia: str | None = None
    comprobante_url: str | None = None
    comprobante_key: str | None = None


def _comprobante_url_para_email(key: str | None, fallback_url: str | None) -> str:
    """Genera URL de acceso al comprobante para incluir en el email del admin.
    Si hay key (privado), genera presigned URL de 24h. Si solo hay url legacy, la usa."""
    if key:
        try:
            from services.media.storage import presigned_url as _presigned
            return _presigned(key, expires_seconds=86400, private=True)
        except Exception as e:
            logger.warning("_comprobante_url_para_email: no se pudo generar presigned: %s", e)
    return fallback_url or ""


@router.post("/talleres/{slug}/inscripcion")
def crear_inscripcion(slug: str, body: InscripcionBody):
    """Crea una inscripción al taller. Si los cupos están completos, queda en lista de espera.
    Envía email al admin y al inscripto."""
    nombre = body.nombre.strip()
    email = body.email.strip().lower()
    telefono = body.telefono.strip()
    if not nombre or not email or not telefono:
        raise HTTPException(400, "Nombre, email y teléfono son obligatorios")

    with get_db() as conn:
        try:
            taller = _get_taller(conn, slug)
            taller_id = taller["id"]
            # FOR UPDATE serializa el conteo de cupos (evita sobreventa en inscripciones concurrentes).
            locked = conn.execute(
                "SELECT cupos_total, cupos_confirmados FROM talleres WHERE id = %s FOR UPDATE",
                (taller_id,),
            ).fetchone()
            en_lista = locked["cupos_confirmados"] >= locked["cupos_total"]

            cur = conn.execute(
                """
                INSERT INTO taller_inscripciones
                    (taller_id, nombre, email, telefono, experiencia,
                     comprobante_url, comprobante_key, en_lista_espera)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    taller_id,
                    nombre,
                    email,
                    telefono,
                    body.experiencia or None,
                    body.comprobante_url or None,
                    body.comprobante_key or None,
                    en_lista,
                ),
            )
            row = cur.fetchone()
            inscripcion_id = row["id"]

            if not en_lista:
                conn.execute(
                    "UPDATE talleres SET cupos_confirmados = cupos_confirmados + 1 WHERE id = %s",
                    (taller_id,),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    nombre_pila = nombre.split()[0]
    fecha_str = now_ar().strftime("%-d de %B de %Y, %H:%M hs")
    admin_to = taller["notif_email"] or get_admin_to()

    ctx_admin = {
        "taller_nombre": taller["nombre"],
        "nombre": nombre,
        "email": email,
        "telefono": telefono,
        "experiencia": body.experiencia or "",
        "comprobante_url": _comprobante_url_para_email(body.comprobante_key, body.comprobante_url),
        "en_lista_espera": en_lista,
        "fecha": fecha_str,
    }
    ctx_cliente = {
        "taller_nombre": taller["nombre"],
        "nombre_pila": nombre_pila,
        "en_lista_espera": en_lista,
        "fecha_inicio_str": _fmt_fecha_es(taller["fecha_inicio"]),
        "fecha_fin_str": _fmt_fecha_es(taller["fecha_fin"]),
        "horario": taller["horario"],
        "direccion": taller["direccion"],
        "precio_sena_str": _fmt_pesos(taller["precio_sena"]),
        "pago_alias": taller["pago_alias"],
        "pago_cbu": taller["pago_cbu"],
        "pago_banco": taller["pago_banco"],
    }

    if admin_to:
        send_email("taller_inscripcion_admin", admin_to, ctx_admin)
    send_email("taller_inscripcion_cliente", email, ctx_cliente)

    return {
        "id": inscripcion_id,
        "en_lista_espera": en_lista,
        "cupos_disponibles": max(0, taller["cupos_total"] - taller["cupos_confirmados"] - (0 if en_lista else 1)),
    }


# ── Endpoints admin ───────────────────────────────────────────────────────────

FOTO_MAX_MB = 8


class SesionBody(BaseModel):
    fecha: str  # YYYY-MM-DD
    hora_inicio: int
    hora_fin: int


class TallerCreateBody(BaseModel):
    nombre: str
    tipo_taller: str = "intensivo"
    instructor_nombre: str
    sesiones: list[SesionBody]
    cupos_total: int = 12
    precio_total: int = 0
    precio_sena: int = 0
    subtitulo: str = ""
    descripcion: str = ""
    publico_objetivo: str = ""
    instructor_bio: str = ""
    instructor_proyectos: str = ""
    horario: str = ""
    pago_alias: str = ""
    pago_cbu: str = ""
    pago_banco: str = ""
    direccion: str = ""
    notif_email: str = ""
    activo: bool = True


class TallerUpdateBody(BaseModel):
    nombre: str | None = None
    subtitulo: str | None = None
    descripcion: str | None = None
    publico_objetivo: str | None = None
    instructor_nombre: str | None = None
    instructor_bio: str | None = None
    instructor_proyectos: str | None = None
    programa_teorica: list[str] | None = None
    programa_practica: list[str] | None = None
    tipo_taller: str | None = None
    horario: str | None = None
    precio_total: int | None = None
    precio_sena: int | None = None
    cupos_total: int | None = None
    pago_alias: str | None = None
    pago_cbu: str | None = None
    pago_banco: str | None = None
    direccion: str | None = None
    notif_email: str | None = None
    activo: bool | None = None
    proxima_edicion_slug: str | None = None
    sesiones: list[SesionBody] | None = None


def _validar_sesiones(sesiones: list) -> list[dict]:
    """Valida y normaliza una lista de SesionBody/dicts. Devuelve lista de dicts con
    `fecha` como date object. Lanza 400 si hay errores."""
    if not sesiones:
        raise HTTPException(400, "Debe tener al menos una sesión")
    from datetime import date as _dt_date
    result = []
    seen = set()
    for s in sesiones:
        fecha_str = s.fecha if hasattr(s, "fecha") else s["fecha"]
        h_ini = s.hora_inicio if hasattr(s, "hora_inicio") else s["hora_inicio"]
        h_fin = s.hora_fin if hasattr(s, "hora_fin") else s["hora_fin"]
        try:
            fecha = _dt_date.fromisoformat(fecha_str)
        except (ValueError, TypeError):
            raise HTTPException(400, f"Fecha inválida: {fecha_str}")
        if not (0 <= h_ini < h_fin <= 24):
            raise HTTPException(400, f"Horas inválidas en {fecha_str}: {h_ini}-{h_fin}")
        key = (fecha, h_ini, h_fin)
        if key in seen:
            raise HTTPException(400, f"Sesión duplicada: {fecha_str} {h_ini}-{h_fin}")
        seen.add(key)
        result.append({"fecha": fecha, "hora_inicio": h_ini, "hora_fin": h_fin})
    return result


@router.get("/admin/talleres")
def admin_list_talleres(request: Request):
    """Lista todos los talleres (admin), incluyendo inactivos y sesiones."""
    require_admin(request)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM talleres ORDER BY fecha_inicio DESC"
        ).fetchall()
        return [_taller_to_dict(r, _get_sesiones(conn, r["id"])) for r in rows]


@router.post("/admin/talleres", status_code=201)
def admin_create_taller(body: TallerCreateBody, request: Request):
    """Crea un nuevo taller con sus sesiones. Valida disponibilidad del estudio."""
    require_admin(request)
    sesiones = _validar_sesiones(body.sesiones)
    if body.precio_sena > body.precio_total:
        raise HTTPException(400, "La seña no puede superar el precio total")
    if body.cupos_total < 1:
        raise HTTPException(400, "cupos_total debe ser al menos 1")
    if body.tipo_taller not in ("intensivo", "semanal"):
        raise HTTPException(400, "tipo_taller debe ser 'intensivo' o 'semanal'")

    from routes.estudio import verificar_sesiones_disponibles, _get_estudio_row, _ADVISORY_NS_ESTUDIO

    with get_db() as conn:
        try:
            # Slug único
            base_slug = slugify(body.nombre)
            ocupados = {r["slug"] for r in conn.execute("SELECT slug FROM talleres").fetchall()}
            slug = slug_unico(base_slug, ocupados)

            estudio = _get_estudio_row(conn)
            if estudio["equipo_id"]:
                conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_ADVISORY_NS_ESTUDIO, 1))
                verificar_sesiones_disponibles(conn, estudio, sesiones)

            fechas = [s["fecha"] for s in sesiones]
            fecha_inicio = min(fechas)
            fecha_fin = max(fechas)

            cur = conn.execute(
                """
                INSERT INTO talleres (
                    slug, nombre, subtitulo, tipo_taller,
                    instructor_nombre, instructor_bio, instructor_proyectos,
                    descripcion, publico_objetivo,
                    programa_teorica, programa_practica,
                    fecha_inicio, fecha_fin, horario,
                    cupos_total, precio_total, precio_sena,
                    pago_alias, pago_cbu, pago_banco,
                    direccion, notif_email, activo
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
                """,
                (
                    slug, body.nombre.strip(), body.subtitulo.strip(), body.tipo_taller,
                    body.instructor_nombre.strip(), body.instructor_bio.strip(),
                    body.instructor_proyectos.strip(),
                    body.descripcion.strip(), body.publico_objetivo.strip(),
                    _json.dumps([], ensure_ascii=False), _json.dumps([], ensure_ascii=False),
                    fecha_inicio, fecha_fin, body.horario.strip(),
                    body.cupos_total, body.precio_total, body.precio_sena,
                    body.pago_alias.strip(), body.pago_cbu.strip(), body.pago_banco.strip(),
                    body.direccion.strip(), body.notif_email.strip(), body.activo,
                ),
            )
            taller_id = cur.fetchone()["id"]

            for s in sesiones:
                conn.execute(
                    "INSERT INTO taller_sesiones (taller_id, fecha, hora_inicio, hora_fin) "
                    "VALUES (%s, %s, %s, %s)",
                    (taller_id, s["fecha"], s["hora_inicio"], s["hora_fin"]),
                )
            conn.commit()
            row = conn.execute("SELECT * FROM talleres WHERE id = %s", (taller_id,)).fetchone()
        except Exception:
            conn.rollback()
            raise
    return _taller_to_dict(row, [
        {"fecha": str(s["fecha"]), "hora_inicio": s["hora_inicio"], "hora_fin": s["hora_fin"]}
        for s in sesiones
    ])


@router.patch("/admin/talleres/{taller_id}")
def admin_update_taller(taller_id: int, body: TallerUpdateBody, request: Request):
    """Actualiza campos del taller. Si vienen sesiones, reemplaza todas y revalida disponibilidad."""
    require_admin(request)
    from routes.estudio import verificar_sesiones_disponibles, _get_estudio_row, _ADVISORY_NS_ESTUDIO

    sets = []
    params: list = []
    if body.nombre is not None:
        sets.append("nombre = %s"); params.append(body.nombre.strip())
    if body.subtitulo is not None:
        sets.append("subtitulo = %s"); params.append(body.subtitulo.strip())
    if body.descripcion is not None:
        sets.append("descripcion = %s"); params.append(body.descripcion.strip())
    if body.publico_objetivo is not None:
        sets.append("publico_objetivo = %s"); params.append(body.publico_objetivo.strip())
    if body.instructor_nombre is not None:
        sets.append("instructor_nombre = %s"); params.append(body.instructor_nombre.strip())
    if body.instructor_bio is not None:
        sets.append("instructor_bio = %s"); params.append(body.instructor_bio.strip())
    if body.instructor_proyectos is not None:
        sets.append("instructor_proyectos = %s"); params.append(body.instructor_proyectos.strip())
    if body.programa_teorica is not None:
        sets.append("programa_teorica = %s::jsonb")
        params.append(_json.dumps(body.programa_teorica, ensure_ascii=False))
    if body.programa_practica is not None:
        sets.append("programa_practica = %s::jsonb")
        params.append(_json.dumps(body.programa_practica, ensure_ascii=False))
    if body.tipo_taller is not None:
        if body.tipo_taller not in ("intensivo", "semanal"):
            raise HTTPException(400, "tipo_taller debe ser 'intensivo' o 'semanal'")
        sets.append("tipo_taller = %s"); params.append(body.tipo_taller)
    if body.horario is not None:
        sets.append("horario = %s"); params.append(body.horario.strip())
    if body.precio_total is not None:
        sets.append("precio_total = %s"); params.append(body.precio_total)
    if body.precio_sena is not None:
        sets.append("precio_sena = %s"); params.append(body.precio_sena)
    if body.cupos_total is not None:
        sets.append("cupos_total = %s"); params.append(body.cupos_total)
    if body.pago_alias is not None:
        sets.append("pago_alias = %s"); params.append(body.pago_alias.strip())
    if body.pago_cbu is not None:
        sets.append("pago_cbu = %s"); params.append(body.pago_cbu.strip())
    if body.pago_banco is not None:
        sets.append("pago_banco = %s"); params.append(body.pago_banco.strip())
    if body.direccion is not None:
        sets.append("direccion = %s"); params.append(body.direccion.strip())
    if body.notif_email is not None:
        sets.append("notif_email = %s"); params.append(body.notif_email.strip())
    if body.activo is not None:
        sets.append("activo = %s"); params.append(body.activo)
    if body.proxima_edicion_slug is not None:
        val = body.proxima_edicion_slug.strip()
        if val:
            # Validar que exista y no sea autoreferencia
            row_check = conn_check = None
            with get_db() as _c:
                me = _c.execute("SELECT slug FROM talleres WHERE id = %s", (taller_id,)).fetchone()
                if me and me["slug"] == val:
                    raise HTTPException(400, "proxima_edicion_slug no puede apuntar al mismo taller")
                ref = _c.execute("SELECT id FROM talleres WHERE slug = %s", (val,)).fetchone()
                if not ref:
                    raise HTTPException(400, f"El taller '{val}' no existe")
        sets.append("proxima_edicion_slug = %s"); params.append(val)

    new_sesiones = None
    if body.sesiones is not None:
        new_sesiones = _validar_sesiones(body.sesiones)

    if not sets and new_sesiones is None:
        raise HTTPException(400, "No hay campos para actualizar")

    with get_db() as conn:
        try:
            existing = conn.execute(
                "SELECT cupos_total, cupos_confirmados FROM talleres WHERE id = %s FOR UPDATE",
                (taller_id,),
            ).fetchone()
            if existing is None:
                raise HTTPException(404, "Taller no encontrado")

            # Validar cupos si se baja
            new_cupos = body.cupos_total if body.cupos_total is not None else existing["cupos_total"]
            if new_cupos < existing["cupos_confirmados"]:
                raise HTTPException(
                    400,
                    f"No se puede bajar cupos a {new_cupos}: hay {existing['cupos_confirmados']} confirmados",
                )

            if new_sesiones is not None:
                estudio = _get_estudio_row(conn)
                if estudio["equipo_id"]:
                    conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_ADVISORY_NS_ESTUDIO, 1))
                    verificar_sesiones_disponibles(
                        conn, estudio, new_sesiones, exclude_taller_id=taller_id
                    )
                conn.execute("DELETE FROM taller_sesiones WHERE taller_id = %s", (taller_id,))
                fechas = [s["fecha"] for s in new_sesiones]
                sets.append("fecha_inicio = %s"); params.append(min(fechas))
                sets.append("fecha_fin = %s"); params.append(max(fechas))
                for s in new_sesiones:
                    conn.execute(
                        "INSERT INTO taller_sesiones (taller_id, fecha, hora_inicio, hora_fin) "
                        "VALUES (%s, %s, %s, %s)",
                        (taller_id, s["fecha"], s["hora_inicio"], s["hora_fin"]),
                    )

            if sets:
                sets.append("updated_at = NOW()")
                params.append(taller_id)
                conn.execute(
                    f"UPDATE talleres SET {', '.join(sets)} WHERE id = %s",
                    params,
                )

            conn.commit()
            row = conn.execute("SELECT * FROM talleres WHERE id = %s", (taller_id,)).fetchone()
        except Exception:
            conn.rollback()
            raise
    return _taller_to_dict(row, _get_sesiones(conn, taller_id))


@router.delete("/admin/talleres/{taller_id}", status_code=200)
def admin_delete_taller(taller_id: int, request: Request):
    """Elimina un taller. Falla con 409 si hay inscriptos confirmados."""
    require_admin(request)
    with get_db() as conn:
        try:
            row = conn.execute(
                "SELECT slug, cupos_confirmados FROM talleres WHERE id = %s", (taller_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Taller no encontrado")
            if row["cupos_confirmados"] > 0:
                raise HTTPException(
                    409,
                    f"No se puede eliminar: hay {row['cupos_confirmados']} inscripto(s) confirmado(s)",
                )
            slug = row["slug"]
            conn.execute("DELETE FROM talleres WHERE id = %s", (taller_id,))
            # Limpiar referencias de proxima_edicion_slug que apuntaban a este taller
            conn.execute(
                "UPDATE talleres SET proxima_edicion_slug = '' "
                "WHERE proxima_edicion_slug = %s",
                (slug,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {"ok": True}


_INSTRUCTOR_SPECS = [
    DeriveSpec(name="display", square=False, max_width=400),
    DeriveSpec(name="display-sm", square=False, max_width=200),
]


@router.post("/admin/talleres/{taller_id}/upload-foto-instructor")
async def admin_upload_foto_instructor(taller_id: int, request: Request):
    """Sube la foto del instructor a R2 vía el motor de media y actualiza talleres."""
    require_admin(request)
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM talleres WHERE id = ?", (taller_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Taller no encontrado")

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file' en el form-data")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Archivo vacío")
    if len(raw) > FOTO_MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"Archivo muy grande (máx {FOTO_MAX_MB} MB)")

    try:
        with get_db() as conn:
            asset = store_upload(raw, kind="instructor", derive_specs=_INSTRUCTOR_SPECS, conn=conn)
            display = asset.variant("display") or (asset.variants[0] if asset.variants else None)
            url = display.url if display else ""
            conn.execute(
                "UPDATE talleres SET instructor_media_id = ?, instructor_foto_url = ?, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (asset.id, url, taller_id),
            )
            conn.commit()
    except MediaError as e:
        raise HTTPException(e.status, e.detail)
    except Exception as e:
        logger.error("upload_foto_instructor: error inesperado: %s", e, exc_info=True)
        raise HTTPException(502, "No se pudo subir la foto. Intentá de nuevo.")

    return {"ok": True, "url": url, "media_id": asset.id}


@router.get("/admin/talleres/{taller_id}/inscripciones")
def admin_list_inscripciones(taller_id: int, request: Request):
    """Lista inscripciones de un taller (admin)."""
    require_admin(request)
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM taller_inscripciones
            WHERE taller_id = %s
            ORDER BY en_lista_espera, created_at
            """,
            (taller_id,),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "nombre": r["nombre"],
            "email": r["email"],
            "telefono": r["telefono"],
            "experiencia": r["experiencia"],
            "comprobante_url": r["comprobante_url"],
            "en_lista_espera": r["en_lista_espera"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@router.get("/admin/talleres/{taller_id}/inscripciones/export-csv")
def admin_export_inscripciones_csv(taller_id: int, request: Request):
    """Descarga CSV de inscriptos de un taller."""
    require_admin(request)
    with get_db() as conn:
        taller_row = conn.execute(
            "SELECT nombre, slug FROM talleres WHERE id = %s", (taller_id,)
        ).fetchone()
        if taller_row is None:
            raise HTTPException(404, "Taller no encontrado")
        rows = conn.execute(
            """
            SELECT nombre, email, telefono, experiencia,
                   en_lista_espera, created_at
            FROM taller_inscripciones
            WHERE taller_id = %s
            ORDER BY en_lista_espera, created_at
            """,
            (taller_id,),
        ).fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["nombre", "email", "telefono", "experiencia", "estado", "inscripto_at"])
    for r in rows:
        estado = "lista espera" if r["en_lista_espera"] else "confirmado"
        w.writerow([
            r["nombre"], r["email"], r["telefono"],
            r["experiencia"] or "",
            estado,
            r["created_at"].isoformat() if r["created_at"] else "",
        ])
    csv_bytes = buf.getvalue().encode("utf-8-sig")
    filename = f"inscriptos-{taller_row['slug']}.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/admin/talleres/{taller_id}/inscripciones/{ins_id}", status_code=200)
def admin_delete_inscripcion(taller_id: int, ins_id: int, request: Request):
    """Elimina una inscripción. Si era confirmada, decrementa cupos_confirmados."""
    require_admin(request)
    with get_db() as conn:
        try:
            ins = conn.execute(
                "SELECT id, en_lista_espera FROM taller_inscripciones "
                "WHERE id = %s AND taller_id = %s",
                (ins_id, taller_id),
            ).fetchone()
            if ins is None:
                raise HTTPException(404, "Inscripción no encontrada")
            conn.execute("DELETE FROM taller_inscripciones WHERE id = %s", (ins_id,))
            if not ins["en_lista_espera"]:
                conn.execute(
                    "UPDATE talleres SET cupos_confirmados = GREATEST(0, cupos_confirmados - 1) "
                    "WHERE id = %s",
                    (taller_id,),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {"ok": True}


@router.post("/admin/talleres/{taller_id}/inscripciones/{ins_id}/confirmar", status_code=200)
def admin_confirmar_inscripcion(taller_id: int, ins_id: int, request: Request):
    """Pasa una inscripción de lista de espera a confirmada. Falla con 400 si no hay cupo."""
    require_admin(request)
    with get_db() as conn:
        try:
            taller = conn.execute(
                "SELECT cupos_total, cupos_confirmados FROM talleres WHERE id = %s FOR UPDATE",
                (taller_id,),
            ).fetchone()
            if taller is None:
                raise HTTPException(404, "Taller no encontrado")
            if taller["cupos_confirmados"] >= taller["cupos_total"]:
                raise HTTPException(400, "No hay cupos disponibles para confirmar")
            ins = conn.execute(
                "SELECT id, en_lista_espera FROM taller_inscripciones "
                "WHERE id = %s AND taller_id = %s",
                (ins_id, taller_id),
            ).fetchone()
            if ins is None:
                raise HTTPException(404, "Inscripción no encontrada")
            if not ins["en_lista_espera"]:
                raise HTTPException(400, "La inscripción ya está confirmada")
            conn.execute(
                "UPDATE taller_inscripciones SET en_lista_espera = FALSE WHERE id = %s",
                (ins_id,),
            )
            conn.execute(
                "UPDATE talleres SET cupos_confirmados = cupos_confirmados + 1 WHERE id = %s",
                (taller_id,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {"ok": True}


class NotificarCambiosBody(BaseModel):
    mensaje: str | None = None


@router.post("/admin/talleres/{taller_id}/notificar-cambios", status_code=200)
def admin_notificar_cambios(taller_id: int, body: NotificarCambiosBody, request: Request):
    """Envía email de cambios a todos los inscriptos confirmados del taller."""
    require_admin(request)
    with get_db() as conn:
        taller = conn.execute(
            "SELECT nombre FROM talleres WHERE id = %s", (taller_id,)
        ).fetchone()
        if taller is None:
            raise HTTPException(404, "Taller no encontrado")
        inscriptos = conn.execute(
            "SELECT nombre, email FROM taller_inscripciones "
            "WHERE taller_id = %s AND en_lista_espera = FALSE",
            (taller_id,),
        ).fetchall()

    enviados, fallidos = [], []
    for ins in inscriptos:
        nombre_pila = ins["nombre"].split()[0]
        ctx = {
            "taller_nombre": taller["nombre"],
            "nombre_pila": nombre_pila,
            "mensaje": body.mensaje or "",
        }
        try:
            send_email("taller_cambio_datos", ins["email"], ctx)
            enviados.append(ins["email"])
        except Exception as e:
            logger.warning("notificar_cambios: error enviando a %s: %s", ins["email"], e)
            fallidos.append(ins["email"])

    return {"enviados": len(enviados), "fallidos": len(fallidos)}
