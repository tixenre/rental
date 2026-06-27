"""
routes/talleres.py — Workshops públicos: listing, detalle, inscripción + notificaciones.
Vista admin: conceptos de taller con ediciones anidadas, upload comprobante/foto.

Modelo de tres capas (F3):
  talleres          = concepto (datos estables: nombre, bio, programa)
  ediciones_taller  = una fila por edición (fechas, precios, cupos, freeze)
  clases_taller     = clases de cada edición (reemplaza taller_sesiones)
  interesados_taller= leads cuando no hay cupos disponibles
"""

import csv
import io
import logging
import time
import uuid
import json as _json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr

from admin_guard import require_admin
from database import get_db, now_ar
from rate_limit import limiter
from dataio.slug import slugify, slug_unico
from services.email import send_email
from services.email.service import get_admin_to
from services.media.models import DeriveSpec
from services.media.errors import MediaError
from services.media.service import store_upload, store_raw_document

logger = logging.getLogger(__name__)

router = APIRouter()

COMPROBANTE_MAX_MB = 10
FOTO_MAX_MB = 8

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


# ── Helpers de lectura ────────────────────────────────────────────────────────

def _get_edicion_row(conn, slug: str):
    """Busca una edición activa por slug. Lanza 404 si no existe."""
    row = conn.execute(
        """
        SELECT e.*, t.nombre, t.subtitulo, t.instructor_nombre,
               t.instructor_bio, t.instructor_proyectos, t.descripcion,
               t.publico_objetivo, t.programa_teorica, t.programa_practica,
               t.instructor_foto_url, t.instructor_media_id, t.notif_email,
               t.slug_base
        FROM ediciones_taller e
        JOIN talleres t ON t.id = e.taller_id
        WHERE e.slug = %s AND e.activo = TRUE
        """,
        (slug,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    return row


def _get_clases(conn, edicion_id: int) -> list:
    rows = conn.execute(
        "SELECT fecha, hora_inicio, hora_fin FROM clases_taller "
        "WHERE edicion_id = %s ORDER BY fecha, hora_inicio",
        (edicion_id,),
    ).fetchall()
    return [
        {"fecha": str(r["fecha"]), "hora_inicio": r["hora_inicio"], "hora_fin": r["hora_fin"]}
        for r in rows
    ]


def _edicion_lite(row) -> dict:
    """Datos mínimos de una edición para mostrar en el contexto de otra."""
    return {
        "slug": row["slug"],
        "numero_edicion": row["numero_edicion"],
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


def _edicion_to_public_dict(row, clases=None) -> dict:
    """Convierte edicion_row (JOIN talleres) al shape plano del API público."""
    return {
        "id": row["id"],
        "taller_id": row["taller_id"],
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
        "instructor_foto_url": row["instructor_foto_url"] or "",
        "instructor_media_id": row["instructor_media_id"],
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
        "activo": bool(row["activo"]),
        "tipo_taller": row["tipo_taller"],
        "numero_edicion": row["numero_edicion"],
        "frozen_at": row["frozen_at"].isoformat() if row["frozen_at"] else None,
        # sesiones = backward compat con el frontend (lee de clases_taller)
        "sesiones": clases if clases is not None else [],
    }


def _edicion_to_admin_dict(edicion_row, clases=None) -> dict:
    """Convierte una fila de ediciones_taller al shape de admin (anidado en concepto)."""
    return {
        "id": edicion_row["id"],
        "taller_id": edicion_row["taller_id"],
        "numero_edicion": edicion_row["numero_edicion"],
        "slug": edicion_row["slug"],
        "tipo_taller": edicion_row["tipo_taller"],
        "fecha_inicio": str(edicion_row["fecha_inicio"]),
        "fecha_fin": str(edicion_row["fecha_fin"]),
        "horario": edicion_row["horario"],
        "cupos_total": edicion_row["cupos_total"],
        "cupos_confirmados": edicion_row["cupos_confirmados"],
        "cupos_disponibles": max(0, edicion_row["cupos_total"] - edicion_row["cupos_confirmados"]),
        "precio_total": edicion_row["precio_total"],
        "precio_sena": edicion_row["precio_sena"],
        "pago_alias": edicion_row["pago_alias"],
        "pago_cbu": edicion_row["pago_cbu"],
        "pago_banco": edicion_row["pago_banco"],
        "direccion": edicion_row["direccion"],
        "activo": bool(edicion_row["activo"]),
        "frozen_at": edicion_row["frozen_at"].isoformat() if edicion_row["frozen_at"] else None,
        "clases": clases if clases is not None else [],
    }


def _concepto_to_admin_dict(taller_row, ediciones=None) -> dict:
    """Convierte una fila de talleres (concepto) al shape admin con ediciones anidadas."""
    return {
        "id": taller_row["id"],
        "slug_base": taller_row["slug_base"] or taller_row["slug"],
        "nombre": taller_row["nombre"],
        "subtitulo": taller_row["subtitulo"],
        "instructor_nombre": taller_row["instructor_nombre"],
        "instructor_bio": taller_row["instructor_bio"],
        "instructor_proyectos": taller_row["instructor_proyectos"],
        "descripcion": taller_row["descripcion"],
        "publico_objetivo": taller_row["publico_objetivo"],
        "programa_teorica": taller_row["programa_teorica"] or [],
        "programa_practica": taller_row["programa_practica"] or [],
        "instructor_foto_url": taller_row["instructor_foto_url"] or "",
        "instructor_media_id": taller_row["instructor_media_id"],
        "notif_email": taller_row["notif_email"],
        "ediciones": ediciones if ediciones is not None else [],
    }


def _validar_clases(clases: list) -> list[dict]:
    """Valida y normaliza una lista de clases. Devuelve lista de dicts. Lanza 400 si hay errores."""
    if not clases:
        raise HTTPException(400, "Debe tener al menos una clase")
    from datetime import date as _dt_date
    result = []
    seen = set()
    for s in clases:
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
            raise HTTPException(400, f"Clase duplicada: {fecha_str} {h_ini}-{h_fin}")
        seen.add(key)
        result.append({"fecha": fecha, "hora_inicio": h_ini, "hora_fin": h_fin})
    return result


def _insert_clases(conn, edicion_id: int, clases: list) -> None:
    for c in clases:
        conn.execute(
            "INSERT INTO clases_taller (edicion_id, fecha, hora_inicio, hora_fin) "
            "VALUES (%s, %s, %s, %s)",
            (edicion_id, c["fecha"], c["hora_inicio"], c["hora_fin"]),
        )


# ── Endpoints públicos ────────────────────────────────────────────────────────

@router.get("/talleres")
def list_talleres():
    """Lista todas las ediciones activas de talleres (una card por edición)."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT e.*, t.nombre, t.subtitulo, t.instructor_nombre,
                   t.instructor_bio, t.instructor_proyectos, t.descripcion,
                   t.publico_objetivo, t.programa_teorica, t.programa_practica,
                   t.instructor_foto_url, t.instructor_media_id, t.notif_email,
                   t.slug_base
            FROM ediciones_taller e
            JOIN talleres t ON t.id = e.taller_id
            WHERE e.activo = TRUE
            ORDER BY e.fecha_inicio
            """,
        ).fetchall()
        return [
            _edicion_to_public_dict(r, _get_clases(conn, r["id"]))
            for r in rows
        ]


@router.get("/talleres/{slug}")
def get_taller(slug: str):
    """Detalle de una edición de taller. Incluye proxima_edicion y edicion_anterior."""
    with get_db() as conn:
        row = _get_edicion_row(conn, slug)
        d = _edicion_to_public_dict(row, _get_clases(conn, row["id"]))

        # Próxima edición: misma concepto (taller_id), numero_edicion mayor
        pr = conn.execute(
            """
            SELECT * FROM ediciones_taller
            WHERE taller_id = %s AND numero_edicion > %s AND activo = TRUE
            ORDER BY numero_edicion ASC LIMIT 1
            """,
            (row["taller_id"], row["numero_edicion"]),
        ).fetchone()
        d["proxima_edicion"] = _edicion_lite(pr) if pr else None

        # Edición anterior: mismo concepto, numero_edicion menor
        ant = conn.execute(
            """
            SELECT * FROM ediciones_taller
            WHERE taller_id = %s AND numero_edicion < %s
            ORDER BY numero_edicion DESC LIMIT 1
            """,
            (row["taller_id"], row["numero_edicion"]),
        ).fetchone()
        d["edicion_anterior"] = _edicion_lite(ant) if ant else None
    return d


@router.post("/talleres/{slug}/upload-comprobante")
@limiter.limit("20/minute")
async def upload_comprobante(slug: str, request: Request):
    """Recibe el comprobante de pago (multipart, campo 'file') y lo sube a R2 privado."""
    with get_db() as conn:
        _get_edicion_row(conn, slug)

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
    if key:
        try:
            from services.media.storage import presigned_url as _presigned
            return _presigned(key, expires_seconds=86400, private=True)
        except Exception as e:
            logger.warning("_comprobante_url_para_email: no se pudo generar presigned: %s", e)
    return fallback_url or ""


@router.post("/talleres/{slug}/inscripcion")
@limiter.limit("10/minute")
def crear_inscripcion(slug: str, body: InscripcionBody, request: Request):
    """Crea una inscripción a una edición de taller. Cupos llenos → lista de espera."""
    nombre = body.nombre.strip()
    email = body.email.strip().lower()
    telefono = body.telefono.strip()
    if not nombre or not email or not telefono:
        raise HTTPException(400, "Nombre, email y teléfono son obligatorios")

    with get_db() as conn:
        try:
            edicion_row = _get_edicion_row(conn, slug)
            edicion_id = edicion_row["id"]
            taller_id = edicion_row["taller_id"]

            # FOR UPDATE serializa el conteo de cupos de esta edición
            locked = conn.execute(
                "SELECT cupos_total, cupos_confirmados FROM ediciones_taller "
                "WHERE id = %s FOR UPDATE",
                (edicion_id,),
            ).fetchone()
            en_lista = locked["cupos_confirmados"] >= locked["cupos_total"]
            estado = "en_espera" if en_lista else "pendiente_sena"

            cur = conn.execute(
                """
                INSERT INTO taller_inscripciones
                    (taller_id, edicion_id, nombre, email, telefono, experiencia,
                     comprobante_url, comprobante_key, en_lista_espera, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    taller_id,
                    edicion_id,
                    nombre, email, telefono,
                    body.experiencia or None,
                    body.comprobante_url or None,
                    body.comprobante_key or None,
                    en_lista,
                    estado,
                ),
            )
            row = cur.fetchone()
            inscripcion_id = row["id"]

            if not en_lista:
                conn.execute(
                    "UPDATE ediciones_taller "
                    "SET cupos_confirmados = cupos_confirmados + 1, updated_at = NOW() "
                    "WHERE id = %s",
                    (edicion_id,),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    nombre_pila = nombre.split()[0]
    fecha_str = now_ar().strftime("%-d de %B de %Y, %H:%M hs")
    admin_to = edicion_row["notif_email"] or get_admin_to()

    ctx_admin = {
        "taller_nombre": edicion_row["nombre"],
        "nombre": nombre,
        "email": email,
        "telefono": telefono,
        "experiencia": body.experiencia or "",
        "comprobante_url": _comprobante_url_para_email(body.comprobante_key, body.comprobante_url),
        "en_lista_espera": en_lista,
        "fecha": fecha_str,
    }
    ctx_cliente = {
        "taller_nombre": edicion_row["nombre"],
        "nombre_pila": nombre_pila,
        "en_lista_espera": en_lista,
        "fecha_inicio_str": _fmt_fecha_es(edicion_row["fecha_inicio"]),
        "fecha_fin_str": _fmt_fecha_es(edicion_row["fecha_fin"]),
        "horario": edicion_row["horario"],
        "direccion": edicion_row["direccion"],
        "precio_sena_str": _fmt_pesos(edicion_row["precio_sena"]),
        "pago_alias": edicion_row["pago_alias"],
        "pago_cbu": edicion_row["pago_cbu"],
        "pago_banco": edicion_row["pago_banco"],
    }

    if admin_to:
        send_email("taller_inscripcion_admin", admin_to, ctx_admin)
    send_email("taller_inscripcion_cliente", email, ctx_cliente)

    cupos_disponibles = max(0, locked["cupos_total"] - locked["cupos_confirmados"] - (0 if en_lista else 1))
    return {
        "id": inscripcion_id,
        "en_lista_espera": en_lista,
        "cupos_disponibles": cupos_disponibles,
    }


class InteresadoBody(BaseModel):
    nombre: str
    email: EmailStr
    telefono: str = ""


@router.post("/talleres/{slug}/interesado", status_code=201)
@limiter.limit("5/minute")
def crear_interesado(slug: str, body: InteresadoBody, request: Request):
    """Registra un interesado en el workshop cuando no hay cupos disponibles."""
    nombre = body.nombre.strip()
    email = body.email.strip().lower()
    if not nombre or not email:
        raise HTTPException(400, "Nombre y email son obligatorios")

    with get_db() as conn:
        edicion_row = _get_edicion_row(conn, slug)
        taller_id = edicion_row["taller_id"]
        try:
            conn.execute(
                """
                INSERT INTO interesados_taller (taller_id, nombre, email, telefono)
                VALUES (%s, %s, %s, %s)
                """,
                (taller_id, nombre, email, body.telefono.strip()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {"ok": True}


# ── Endpoints admin ───────────────────────────────────────────────────────────

class ClaseBody(BaseModel):
    fecha: str  # YYYY-MM-DD
    hora_inicio: int
    hora_fin: int


# Body usado en POST /admin/talleres y POST /admin/talleres/{id}/ediciones
class EdicionCreateBody(BaseModel):
    tipo_taller: str = "intensivo"
    clases: list[ClaseBody]
    cupos_total: int = 12
    precio_total: int = 0
    precio_sena: int = 0
    horario: str = ""
    pago_alias: str = ""
    pago_cbu: str = ""
    pago_banco: str = ""
    direccion: str = ""
    activo: bool = True
    numero_edicion: int = 1


class TallerConceptoCreateBody(BaseModel):
    nombre: str
    instructor_nombre: str
    subtitulo: str = ""
    descripcion: str = ""
    publico_objetivo: str = ""
    instructor_bio: str = ""
    instructor_proyectos: str = ""
    notif_email: str = ""
    # Primera edición (requerida al crear el concepto)
    edicion: EdicionCreateBody


class TallerConceptoUpdateBody(BaseModel):
    nombre: str | None = None
    subtitulo: str | None = None
    descripcion: str | None = None
    publico_objetivo: str | None = None
    instructor_nombre: str | None = None
    instructor_bio: str | None = None
    instructor_proyectos: str | None = None
    programa_teorica: list[str] | None = None
    programa_practica: list[str] | None = None
    notif_email: str | None = None


class EdicionUpdateBody(BaseModel):
    tipo_taller: str | None = None
    horario: str | None = None
    precio_total: int | None = None
    precio_sena: int | None = None
    cupos_total: int | None = None
    pago_alias: str | None = None
    pago_cbu: str | None = None
    pago_banco: str | None = None
    direccion: str | None = None
    activo: bool | None = None
    clases: list[ClaseBody] | None = None


@router.get("/admin/talleres")
def admin_list_talleres(request: Request):
    """Lista todos los conceptos de taller con sus ediciones y clases anidadas."""
    require_admin(request)
    with get_db() as conn:
        # Conceptos: talleres que tienen al menos una edición
        conceptos = conn.execute(
            """
            SELECT DISTINCT t.*
            FROM talleres t
            JOIN ediciones_taller e ON e.taller_id = t.id
            ORDER BY t.id DESC
            """
        ).fetchall()

        result = []
        for t in conceptos:
            edicion_rows = conn.execute(
                "SELECT * FROM ediciones_taller WHERE taller_id = %s ORDER BY numero_edicion",
                (t["id"],),
            ).fetchall()
            ediciones = [
                _edicion_to_admin_dict(e, _get_clases(conn, e["id"]))
                for e in edicion_rows
            ]
            result.append(_concepto_to_admin_dict(t, ediciones))
    return result


@router.post("/admin/talleres", status_code=201)
def admin_create_taller(body: TallerConceptoCreateBody, request: Request):
    """Crea un nuevo concepto de taller con su primera edición."""
    require_admin(request)
    ed = body.edicion
    clases = _validar_clases(ed.clases)
    if ed.precio_sena > ed.precio_total:
        raise HTTPException(400, "La seña no puede superar el precio total")
    if ed.cupos_total < 1:
        raise HTTPException(400, "cupos_total debe ser al menos 1")
    if ed.tipo_taller not in ("intensivo", "semanal"):
        raise HTTPException(400, "tipo_taller debe ser 'intensivo' o 'semanal'")

    from routes.estudio import verificar_sesiones_disponibles, _get_estudio_row, _ADVISORY_NS_ESTUDIO

    with get_db() as conn:
        try:
            # Slug base del concepto (único en talleres)
            nombre_base = body.nombre.strip()
            ocupados_t = {r["slug"] for r in conn.execute("SELECT slug FROM talleres").fetchall()}
            slug_base = slug_unico(slugify(nombre_base), ocupados_t)

            # Slug de la primera edición (único en ediciones_taller)
            ocupados_e = {r["slug"] for r in conn.execute("SELECT slug FROM ediciones_taller").fetchall()}
            ed_numero = max(1, ed.numero_edicion)
            slug_edicion = slug_unico(slug_base, ocupados_e) if ed_numero == 1 else slug_unico(
                f"{slug_base}-{ed_numero}", ocupados_e
            )

            estudio = _get_estudio_row(conn)
            if estudio["equipo_id"]:
                conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_ADVISORY_NS_ESTUDIO, 1))
                verificar_sesiones_disponibles(conn, estudio, clases)

            fechas = [c["fecha"] for c in clases]
            fecha_inicio = min(fechas)
            fecha_fin = max(fechas)

            # Crear concepto en talleres
            cur = conn.execute(
                """
                INSERT INTO talleres (
                    slug, nombre, subtitulo,
                    instructor_nombre, instructor_bio, instructor_proyectos,
                    descripcion, publico_objetivo,
                    programa_teorica, programa_practica,
                    fecha_inicio, fecha_fin, horario,
                    cupos_total, precio_total, precio_sena,
                    pago_alias, pago_cbu, pago_banco,
                    direccion, notif_email, activo,
                    tipo_taller, numero_edicion, slug_base
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                ) RETURNING id
                """,
                (
                    slug_base, nombre_base, body.subtitulo.strip(),
                    body.instructor_nombre.strip(), body.instructor_bio.strip(),
                    body.instructor_proyectos.strip(),
                    body.descripcion.strip(), body.publico_objetivo.strip(),
                    _json.dumps([], ensure_ascii=False), _json.dumps([], ensure_ascii=False),
                    fecha_inicio, fecha_fin, ed.horario.strip(),
                    ed.cupos_total, ed.precio_total, ed.precio_sena,
                    ed.pago_alias.strip(), ed.pago_cbu.strip(), ed.pago_banco.strip(),
                    ed.direccion.strip(), body.notif_email.strip(), ed.activo,
                    ed.tipo_taller, ed_numero, slug_base,
                ),
            )
            taller_id = cur.fetchone()["id"]

            # Crear primera edición en ediciones_taller
            cur2 = conn.execute(
                """
                INSERT INTO ediciones_taller (
                    taller_id, numero_edicion, slug, tipo_taller,
                    fecha_inicio, fecha_fin, horario,
                    cupos_total, precio_total, precio_sena,
                    pago_alias, pago_cbu, pago_banco,
                    direccion, activo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    taller_id, ed_numero, slug_edicion, ed.tipo_taller,
                    fecha_inicio, fecha_fin, ed.horario.strip(),
                    ed.cupos_total, ed.precio_total, ed.precio_sena,
                    ed.pago_alias.strip(), ed.pago_cbu.strip(), ed.pago_banco.strip(),
                    ed.direccion.strip(), ed.activo,
                ),
            )
            edicion_id = cur2.fetchone()["id"]
            _insert_clases(conn, edicion_id, clases)
            conn.commit()

            t_row = conn.execute("SELECT * FROM talleres WHERE id = %s", (taller_id,)).fetchone()
            e_row = conn.execute("SELECT * FROM ediciones_taller WHERE id = %s", (edicion_id,)).fetchone()
        except Exception:
            conn.rollback()
            raise

    return _concepto_to_admin_dict(t_row, [
        _edicion_to_admin_dict(e_row, [
            {"fecha": str(c["fecha"]), "hora_inicio": c["hora_inicio"], "hora_fin": c["hora_fin"]}
            for c in clases
        ])
    ])


@router.post("/admin/talleres/{taller_id}/ediciones", status_code=201)
def admin_create_edicion(taller_id: int, body: EdicionCreateBody, request: Request):
    """Agrega una nueva edición a un concepto de taller existente."""
    require_admin(request)
    clases = _validar_clases(body.clases)
    if body.precio_sena > body.precio_total:
        raise HTTPException(400, "La seña no puede superar el precio total")
    if body.cupos_total < 1:
        raise HTTPException(400, "cupos_total debe ser al menos 1")
    if body.tipo_taller not in ("intensivo", "semanal"):
        raise HTTPException(400, "tipo_taller debe ser 'intensivo' o 'semanal'")

    from routes.estudio import verificar_sesiones_disponibles, _get_estudio_row, _ADVISORY_NS_ESTUDIO

    with get_db() as conn:
        try:
            t_row = conn.execute(
                "SELECT * FROM talleres WHERE id = %s", (taller_id,)
            ).fetchone()
            if t_row is None:
                raise HTTPException(404, "Taller no encontrado")

            slug_base = t_row["slug_base"] or t_row["slug"]
            ed_numero = max(1, body.numero_edicion)

            # Verificar que el numero_edicion no está tomado
            existing = conn.execute(
                "SELECT id FROM ediciones_taller WHERE taller_id = %s AND numero_edicion = %s",
                (taller_id, ed_numero),
            ).fetchone()
            if existing:
                raise HTTPException(409, f"Ya existe la edición #{ed_numero} de este taller")

            # Slug único para la edición
            ocupados = {r["slug"] for r in conn.execute("SELECT slug FROM ediciones_taller").fetchall()}
            slug_edicion = slug_unico(
                slug_base if ed_numero == 1 else f"{slug_base}-{ed_numero}",
                ocupados,
            )

            estudio = _get_estudio_row(conn)
            if estudio["equipo_id"]:
                conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_ADVISORY_NS_ESTUDIO, 1))
                verificar_sesiones_disponibles(conn, estudio, clases)

            fechas = [c["fecha"] for c in clases]
            fecha_inicio = min(fechas)
            fecha_fin = max(fechas)

            cur = conn.execute(
                """
                INSERT INTO ediciones_taller (
                    taller_id, numero_edicion, slug, tipo_taller,
                    fecha_inicio, fecha_fin, horario,
                    cupos_total, precio_total, precio_sena,
                    pago_alias, pago_cbu, pago_banco,
                    direccion, activo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    taller_id, ed_numero, slug_edicion, body.tipo_taller,
                    fecha_inicio, fecha_fin, body.horario.strip(),
                    body.cupos_total, body.precio_total, body.precio_sena,
                    body.pago_alias.strip(), body.pago_cbu.strip(), body.pago_banco.strip(),
                    body.direccion.strip(), body.activo,
                ),
            )
            edicion_id = cur.fetchone()["id"]
            _insert_clases(conn, edicion_id, clases)
            conn.commit()
            e_row = conn.execute("SELECT * FROM ediciones_taller WHERE id = %s", (edicion_id,)).fetchone()
        except Exception:
            conn.rollback()
            raise

    return _edicion_to_admin_dict(e_row, [
        {"fecha": str(c["fecha"]), "hora_inicio": c["hora_inicio"], "hora_fin": c["hora_fin"]}
        for c in clases
    ])


@router.patch("/admin/talleres/{taller_id}")
def admin_update_concepto(taller_id: int, body: TallerConceptoUpdateBody, request: Request):
    """Actualiza los campos estables del concepto (nombre, bio, programa, etc.)."""
    require_admin(request)
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
    if body.notif_email is not None:
        sets.append("notif_email = %s"); params.append(body.notif_email.strip())

    if not sets:
        raise HTTPException(400, "No hay campos para actualizar")

    with get_db() as conn:
        try:
            existing = conn.execute("SELECT id FROM talleres WHERE id = %s", (taller_id,)).fetchone()
            if existing is None:
                raise HTTPException(404, "Taller no encontrado")
            sets.append("updated_at = NOW()")
            params.append(taller_id)
            conn.execute(f"UPDATE talleres SET {', '.join(sets)} WHERE id = %s", params)
            conn.commit()
            t_row = conn.execute("SELECT * FROM talleres WHERE id = %s", (taller_id,)).fetchone()
            edicion_rows = conn.execute(
                "SELECT * FROM ediciones_taller WHERE taller_id = %s ORDER BY numero_edicion",
                (taller_id,),
            ).fetchall()
            ediciones = [
                _edicion_to_admin_dict(e, _get_clases(conn, e["id"]))
                for e in edicion_rows
            ]
        except Exception:
            conn.rollback()
            raise
    return _concepto_to_admin_dict(t_row, ediciones)


@router.patch("/admin/ediciones/{edicion_id}")
def admin_update_edicion(edicion_id: int, body: EdicionUpdateBody, request: Request):
    """Actualiza campos de una edición específica (fechas, precios, cupos, clases)."""
    require_admin(request)
    from routes.estudio import verificar_sesiones_disponibles, _get_estudio_row, _ADVISORY_NS_ESTUDIO

    sets = []
    params: list = []
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
    if body.activo is not None:
        sets.append("activo = %s"); params.append(body.activo)

    new_clases = None
    if body.clases is not None:
        new_clases = _validar_clases(body.clases)

    if not sets and new_clases is None:
        raise HTTPException(400, "No hay campos para actualizar")

    with get_db() as conn:
        try:
            existing = conn.execute(
                "SELECT cupos_total, cupos_confirmados FROM ediciones_taller "
                "WHERE id = %s FOR UPDATE",
                (edicion_id,),
            ).fetchone()
            if existing is None:
                raise HTTPException(404, "Edición no encontrada")

            new_cupos = body.cupos_total if body.cupos_total is not None else existing["cupos_total"]
            if new_cupos < existing["cupos_confirmados"]:
                raise HTTPException(
                    400,
                    f"No se puede bajar cupos a {new_cupos}: hay {existing['cupos_confirmados']} confirmados",
                )

            if new_clases is not None:
                estudio = _get_estudio_row(conn)
                if estudio["equipo_id"]:
                    conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_ADVISORY_NS_ESTUDIO, 1))
                    # Excluir esta edición del chequeo de disponibilidad del estudio
                    verificar_sesiones_disponibles(
                        conn, estudio, new_clases,
                        exclude_taller_id=conn.execute(
                            "SELECT taller_id FROM ediciones_taller WHERE id = %s", (edicion_id,)
                        ).fetchone()["taller_id"],
                    )
                conn.execute("DELETE FROM clases_taller WHERE edicion_id = %s", (edicion_id,))
                fechas = [c["fecha"] for c in new_clases]
                sets.append("fecha_inicio = %s"); params.append(min(fechas))
                sets.append("fecha_fin = %s"); params.append(max(fechas))
                _insert_clases(conn, edicion_id, new_clases)

            if sets:
                sets.append("updated_at = NOW()")
                params.append(edicion_id)
                conn.execute(
                    f"UPDATE ediciones_taller SET {', '.join(sets)} WHERE id = %s",
                    params,
                )

            conn.commit()
            e_row = conn.execute(
                "SELECT * FROM ediciones_taller WHERE id = %s", (edicion_id,)
            ).fetchone()
        except Exception:
            conn.rollback()
            raise
    return _edicion_to_admin_dict(e_row, _get_clases(conn, edicion_id))


@router.delete("/admin/talleres/{taller_id}", status_code=200)
def admin_delete_taller(taller_id: int, request: Request):
    """Elimina un concepto y todas sus ediciones. Falla si hay inscriptos confirmados."""
    require_admin(request)
    with get_db() as conn:
        try:
            row = conn.execute(
                "SELECT id FROM talleres WHERE id = %s", (taller_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Taller no encontrado")

            # Verificar que no haya inscripciones confirmadas en ninguna edición
            confirmed = conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM taller_inscripciones ti
                JOIN ediciones_taller e ON e.id = ti.edicion_id
                WHERE e.taller_id = %s AND ti.en_lista_espera = FALSE
                """,
                (taller_id,),
            ).fetchone()["cnt"]
            if confirmed > 0:
                raise HTTPException(
                    409,
                    f"No se puede eliminar: hay {confirmed} inscripto(s) confirmado(s) en sus ediciones",
                )
            # CASCADE borra ediciones_taller, clases_taller, taller_inscripciones
            conn.execute("DELETE FROM talleres WHERE id = %s", (taller_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {"ok": True}


@router.delete("/admin/ediciones/{edicion_id}", status_code=200)
def admin_delete_edicion(edicion_id: int, request: Request):
    """Elimina una edición específica. Falla si hay inscriptos confirmados."""
    require_admin(request)
    with get_db() as conn:
        try:
            edicion = conn.execute(
                "SELECT id, cupos_confirmados FROM ediciones_taller WHERE id = %s",
                (edicion_id,),
            ).fetchone()
            if edicion is None:
                raise HTTPException(404, "Edición no encontrada")
            if edicion["cupos_confirmados"] > 0:
                raise HTTPException(
                    409,
                    f"No se puede eliminar: hay {edicion['cupos_confirmados']} inscripto(s) confirmado(s)",
                )
            conn.execute("DELETE FROM ediciones_taller WHERE id = %s", (edicion_id,))
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
        row = conn.execute("SELECT id FROM talleres WHERE id = %s", (taller_id,)).fetchone()
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
                "UPDATE talleres SET instructor_media_id = %s, instructor_foto_url = %s, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (asset.id, url, taller_id),
            )
            conn.commit()
    except MediaError as e:
        raise HTTPException(e.status, e.detail)
    except Exception as e:
        logger.error("upload_foto_instructor: error inesperado: %s", e, exc_info=True)
        raise HTTPException(502, "No se pudo subir la foto. Intentá de nuevo.")

    return {"ok": True, "url": url, "media_id": asset.id}


# ── Inscripciones (admin) ─────────────────────────────────────────────────────

@router.get("/admin/talleres/{taller_id}/inscripciones")
def admin_list_inscripciones(taller_id: int, request: Request):
    """Lista todas las inscripciones del concepto (todas sus ediciones)."""
    require_admin(request)
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT ti.*, e.numero_edicion, e.slug AS edicion_slug
            FROM taller_inscripciones ti
            LEFT JOIN ediciones_taller e ON e.id = ti.edicion_id
            WHERE ti.taller_id = %s
            ORDER BY ti.en_lista_espera, ti.created_at
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
            "estado": r["estado"],
            "edicion_id": r["edicion_id"],
            "numero_edicion": r["numero_edicion"],
            "edicion_slug": r["edicion_slug"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@router.get("/admin/talleres/{taller_id}/inscripciones/export-csv")
def admin_export_inscripciones_csv(taller_id: int, request: Request):
    """Descarga CSV de inscriptos de un concepto de taller."""
    require_admin(request)
    with get_db() as conn:
        taller_row = conn.execute(
            "SELECT nombre, slug_base FROM talleres WHERE id = %s", (taller_id,)
        ).fetchone()
        if taller_row is None:
            raise HTTPException(404, "Taller no encontrado")
        rows = conn.execute(
            """
            SELECT ti.nombre, ti.email, ti.telefono, ti.experiencia,
                   ti.en_lista_espera, ti.created_at, e.numero_edicion
            FROM taller_inscripciones ti
            LEFT JOIN ediciones_taller e ON e.id = ti.edicion_id
            WHERE ti.taller_id = %s
            ORDER BY ti.en_lista_espera, ti.created_at
            """,
            (taller_id,),
        ).fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["nombre", "email", "telefono", "experiencia", "edicion", "estado", "inscripto_at"])
    for r in rows:
        estado = "lista espera" if r["en_lista_espera"] else "confirmado"
        w.writerow([
            r["nombre"], r["email"], r["telefono"],
            r["experiencia"] or "",
            r["numero_edicion"] or "",
            estado,
            r["created_at"].isoformat() if r["created_at"] else "",
        ])
    csv_bytes = buf.getvalue().encode("utf-8-sig")
    filename = f"inscriptos-{taller_row['slug_base'] or 'taller'}.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/admin/talleres/{taller_id}/inscripciones/{ins_id}", status_code=200)
def admin_delete_inscripcion(taller_id: int, ins_id: int, request: Request):
    """Elimina una inscripción. Si era confirmada, decrementa cupos en la edición."""
    require_admin(request)
    with get_db() as conn:
        try:
            ins = conn.execute(
                "SELECT id, en_lista_espera, edicion_id FROM taller_inscripciones "
                "WHERE id = %s AND taller_id = %s",
                (ins_id, taller_id),
            ).fetchone()
            if ins is None:
                raise HTTPException(404, "Inscripción no encontrada")
            conn.execute("DELETE FROM taller_inscripciones WHERE id = %s", (ins_id,))
            if not ins["en_lista_espera"] and ins["edicion_id"]:
                conn.execute(
                    "UPDATE ediciones_taller "
                    "SET cupos_confirmados = GREATEST(0, cupos_confirmados - 1), updated_at = NOW() "
                    "WHERE id = %s",
                    (ins["edicion_id"],),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {"ok": True}


@router.post("/admin/talleres/{taller_id}/inscripciones/{ins_id}/confirmar", status_code=200)
def admin_confirmar_inscripcion(taller_id: int, ins_id: int, request: Request):
    """Pasa una inscripción de lista de espera a confirmada."""
    require_admin(request)
    with get_db() as conn:
        try:
            ins = conn.execute(
                "SELECT id, en_lista_espera, edicion_id FROM taller_inscripciones "
                "WHERE id = %s AND taller_id = %s",
                (ins_id, taller_id),
            ).fetchone()
            if ins is None:
                raise HTTPException(404, "Inscripción no encontrada")
            if not ins["en_lista_espera"]:
                raise HTTPException(400, "La inscripción ya está confirmada")

            if ins["edicion_id"]:
                edicion = conn.execute(
                    "SELECT cupos_total, cupos_confirmados FROM ediciones_taller "
                    "WHERE id = %s FOR UPDATE",
                    (ins["edicion_id"],),
                ).fetchone()
                if edicion["cupos_confirmados"] >= edicion["cupos_total"]:
                    raise HTTPException(400, "No hay cupos disponibles para confirmar")
                conn.execute(
                    "UPDATE ediciones_taller "
                    "SET cupos_confirmados = cupos_confirmados + 1, updated_at = NOW() "
                    "WHERE id = %s",
                    (ins["edicion_id"],),
                )

            conn.execute(
                "UPDATE taller_inscripciones "
                "SET en_lista_espera = FALSE, estado = 'pendiente_sena', confirmed_at = NOW() "
                "WHERE id = %s",
                (ins_id,),
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
    """Envía email de cambios a todos los inscriptos confirmados del concepto."""
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
