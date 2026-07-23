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
from pydantic import BaseModel, EmailStr, Field

from auth.guards import require_admin
from database import get_db, now_ar
from rate_limit import limiter
from dataio.slug import slugify, slug_unico
from services.email import send_email
from services.fechas import fmt_hhmm as _fmt_hhmm
from services.email.service import get_admin_to
from services.media.models import DeriveSpec
from services.media.errors import MediaError
from services.media.service import store_upload, store_raw_document
from services import telefono as telefono_svc

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

_EDICION_JOIN_SELECT = """
    SELECT e.*, t.nombre, t.subtitulo, t.instructor_nombre,
           t.instructor_bio, t.instructor_proyectos, t.descripcion,
           t.publico_objetivo, t.programa_teorica, t.programa_practica,
           t.instructor_foto_url, t.instructor_media_id, t.notif_email,
           t.slug_base, t.terminos, t.beneficios, t.pregunta_experiencia,
           t.mensaje_confirmacion
    FROM ediciones_taller e
    JOIN talleres t ON t.id = e.taller_id
"""


def _get_edicion_row(conn, slug: str, incluir_borrador: bool = False):
    """Busca una edición activa por slug. Lanza 404 si no existe.
    `incluir_borrador=True` (SOLO preview admin, F2): también sirve ediciones
    despublicadas — el caller es responsable de haber verificado la sesión."""
    filtro_activo = "" if incluir_borrador else "AND e.activo = TRUE"
    row = conn.execute(
        f"{_EDICION_JOIN_SELECT} WHERE e.slug = %s {filtro_activo}",
        (slug,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    return row


def _row_get(c, key, default=None):
    """Lectura tolerante: row de DB o dict normalizado pueden no traer el campo."""
    try:
        v = c[key]
        return default if v is None else v
    except (KeyError, IndexError):
        return default


def _clase_dict(c) -> dict:
    """Serialización única de una clase (row de DB o dict normalizado de
    _validar_clases): minutos crudos + strings \"HH:MM\" resueltos acá +
    el contenido rico (F2: titulo/descripcion/nota/portada)."""
    return {
        "id": _row_get(c, "id"),
        "fecha": str(c["fecha"]),
        "hora_inicio_min": c["hora_inicio_min"],
        "hora_fin_min": c["hora_fin_min"],
        "hora_inicio_str": _fmt_hhmm(c["hora_inicio_min"]),
        "hora_fin_str": _fmt_hhmm(c["hora_fin_min"]),
        "titulo": _row_get(c, "titulo", ""),
        "descripcion": _row_get(c, "descripcion", ""),
        "nota": _row_get(c, "nota", ""),
        "portada_media_id": _row_get(c, "portada_media_id"),
        "portada_url": _row_get(c, "portada_url", ""),
    }


def _get_clases(conn, edicion_id: int) -> list:
    rows = conn.execute(
        "SELECT id, fecha, hora_inicio_min, hora_fin_min, titulo, descripcion, "
        "nota, portada_media_id, portada_url FROM clases_taller "
        "WHERE edicion_id = %s ORDER BY fecha, hora_inicio_min",
        (edicion_id,),
    ).fetchall()
    return [_clase_dict(r) for r in rows]


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
        # F2: textos del concepto que consume la landing/form
        "terminos": _row_get(row, "terminos", ""),
        "beneficios": _row_get(row, "beneficios", ""),
        "pregunta_experiencia": _row_get(row, "pregunta_experiencia", ""),
        "mensaje_confirmacion": _row_get(row, "mensaje_confirmacion", ""),
        # F2 preview admin: True cuando se sirve una edición despublicada
        "borrador": not bool(row["activo"]),
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
        "terminos": _row_get(taller_row, "terminos", ""),
        "beneficios": _row_get(taller_row, "beneficios", ""),
        "pregunta_experiencia": _row_get(taller_row, "pregunta_experiencia", ""),
        "mensaje_confirmacion": _row_get(taller_row, "mensaje_confirmacion", ""),
        "ediciones": ediciones if ediciones is not None else [],
    }


def _validar_clases(clases: list) -> list[dict]:
    """Valida y normaliza una lista de clases (horas en MINUTOS desde medianoche,
    múltiplo de 15 — la UI ofrece pasos de 30, 15 da margen sin granularidad
    arbitraria). Devuelve lista de dicts. Lanza 400 si hay errores."""
    if not clases:
        raise HTTPException(400, "Debe tener al menos una clase")
    from datetime import date as _dt_date
    result = []
    seen = set()
    for s in clases:
        fecha_str = s.fecha if hasattr(s, "fecha") else s["fecha"]
        h_ini = s.hora_inicio_min if hasattr(s, "hora_inicio_min") else s["hora_inicio_min"]
        h_fin = s.hora_fin_min if hasattr(s, "hora_fin_min") else s["hora_fin_min"]
        try:
            fecha = _dt_date.fromisoformat(fecha_str)
        except (ValueError, TypeError):
            raise HTTPException(400, f"Fecha inválida: {fecha_str}")
        if not (0 <= h_ini < h_fin <= 1440):
            raise HTTPException(
                400, f"Horario inválido en {fecha_str}: {_fmt_hhmm(h_ini)}-{_fmt_hhmm(h_fin)}"
            )
        if h_ini % 15 or h_fin % 15:
            raise HTTPException(
                400, f"El horario debe ser múltiplo de 15 minutos ({fecha_str})"
            )
        titulo = str(_row_get(s, "titulo", "") if isinstance(s, dict) else getattr(s, "titulo", "")).strip()
        # La key de duplicado incluye el título: "Clase 11 y 12 se dictan juntas"
        # (caso Filmar) = 2 clases con la misma fecha/franja y títulos distintos.
        key = (fecha, h_ini, h_fin, titulo)
        if key in seen:
            raise HTTPException(
                400, f"Clase duplicada: {fecha_str} {_fmt_hhmm(h_ini)}-{_fmt_hhmm(h_fin)}"
            )
        seen.add(key)

        def _campo(nombre: str, default=""):
            return _row_get(s, nombre, default) if isinstance(s, dict) else getattr(s, nombre, default)

        result.append({
            "id": _campo("id", None),
            "fecha": fecha,
            "hora_inicio_min": h_ini,
            "hora_fin_min": h_fin,
            "titulo": titulo,
            "descripcion": str(_campo("descripcion") or "").strip(),
            "nota": str(_campo("nota") or "").strip(),
            "portada_media_id": _campo("portada_media_id", None),
            "portada_url": str(_campo("portada_url") or ""),
        })
    return result


def _insert_clases(conn, edicion_id: int, clases: list) -> None:
    for c in clases:
        conn.execute(
            "INSERT INTO clases_taller (edicion_id, fecha, hora_inicio_min, hora_fin_min, "
            "titulo, descripcion, nota, portada_media_id, portada_url) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                edicion_id, c["fecha"], c["hora_inicio_min"], c["hora_fin_min"],
                c.get("titulo", ""), c.get("descripcion", ""), c.get("nota", ""),
                c.get("portada_media_id"), c.get("portada_url", ""),
            ),
        )


def _upsert_clases(conn, edicion_id: int, clases: list) -> None:
    """Sincroniza las clases de una edición SIN el delete+insert ciego de antes:
    - con `id` (y perteneciente a la edición) → UPDATE de fecha/horario/contenido
      — la PORTADA no se toca (solo cambia vía sus endpoints de upload/delete);
    - sin `id` → INSERT (acá sí puede traer portada_* — caso "copiar clases");
    - ids existentes que no vienen en la lista → DELETE.
    Preserva `portada_media_id` al reordenar/editar (el delete+insert la perdía)."""
    existentes = {
        r["id"]
        for r in conn.execute(
            "SELECT id FROM clases_taller WHERE edicion_id = %s", (edicion_id,)
        ).fetchall()
    }
    vistos: set[int] = set()
    for c in clases:
        cid = c.get("id")
        if cid and cid in existentes:
            conn.execute(
                "UPDATE clases_taller SET fecha = %s, hora_inicio_min = %s, "
                "hora_fin_min = %s, titulo = %s, descripcion = %s, nota = %s "
                "WHERE id = %s AND edicion_id = %s",
                (
                    c["fecha"], c["hora_inicio_min"], c["hora_fin_min"],
                    c.get("titulo", ""), c.get("descripcion", ""), c.get("nota", ""),
                    cid, edicion_id,
                ),
            )
            vistos.add(cid)
        else:
            _insert_clases(conn, edicion_id, [c])
    sobrantes = existentes - vistos
    for cid in sobrantes:
        conn.execute(
            "DELETE FROM clases_taller WHERE id = %s AND edicion_id = %s",
            (cid, edicion_id),
        )


# ── Endpoints públicos ────────────────────────────────────────────────────────

@router.get("/talleres")
def list_talleres():
    """Lista todas las ediciones activas de talleres (una card por edición)."""
    with get_db() as conn:
        rows = conn.execute(
            f"{_EDICION_JOIN_SELECT} WHERE e.activo = TRUE ORDER BY e.fecha_inicio",
        ).fetchall()
        return [
            _edicion_to_public_dict(r, _get_clases(conn, r["id"]))
            for r in rows
        ]


@router.get("/talleres/{slug}")
def get_taller(slug: str, request: Request):
    """Detalle de una edición de taller. Incluye proxima_edicion y edicion_anterior.

    F2 borradores: una edición despublicada da 404 al público, pero se sirve a
    una SESIÓN ADMIN (preview del "ver en web" mientras se arma el taller) con
    `borrador: true` — el front muestra el banner "solo visible para vos"."""
    from auth.guards import is_admin_email
    from auth.session import dev_bypass_enabled, get_session

    session = get_session(request)
    es_admin = dev_bypass_enabled() or bool(session and is_admin_email(session.get("email")))
    with get_db() as conn:
        row = _get_edicion_row(conn, slug, incluir_borrador=es_admin)
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
            WHERE taller_id = %s AND numero_edicion < %s AND activo = TRUE
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
    # F2: checkbox "Acepto los términos" del form v2. CABLEADO-APAGADO: se
    # registra si viene, pero NO se exige hasta que el form nuevo (F5) mande
    # el campo — exigirlo hoy rompería el form actual (patrón #1125/#1126).
    acepta_terminos: bool = False


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
    telefono_raw = body.telefono.strip()
    if not nombre or not email or not telefono_raw:
        raise HTTPException(400, "Nombre, email y teléfono son obligatorios")
    # Teléfono normalizado a E.164 (puerta única services.telefono → listo para
    # WhatsApp). Si no parsea, conservamos lo que cargó la persona: no bloqueamos
    # la inscripción por un formato raro.
    telefono = telefono_svc.formatear_para_guardar(telefono_raw) or telefono_raw

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

            # Dedup: una persona no se inscribe dos veces a la MISMA edición. La
            # clave es el email (ya normalizado a lowercase). Corre bajo el
            # FOR UPDATE de la edición → race-safe (dos envíos concurrentes del
            # mismo email quedan serializados, el segundo ve al primero).
            ya_inscripto = conn.execute(
                "SELECT 1 FROM taller_inscripciones "
                "WHERE edicion_id = %s AND LOWER(email) = %s LIMIT 1",
                (edicion_id, email),
            ).fetchone()
            if ya_inscripto:
                raise HTTPException(
                    409,
                    "Ya hay una inscripción con ese email para esta edición del taller.",
                )

            cur = conn.execute(
                """
                INSERT INTO taller_inscripciones
                    (taller_id, edicion_id, nombre, email, telefono, experiencia,
                     comprobante_url, comprobante_key, en_lista_espera, estado,
                     tyc_aceptado_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        CASE WHEN %s THEN NOW() ELSE NULL END)
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
                    body.acepta_terminos,
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
    # Teléfono (opcional) normalizado a E.164 por la misma puerta única; vacío queda "".
    telefono = telefono_svc.formatear_para_guardar(body.telefono) or body.telefono.strip()

    with get_db() as conn:
        edicion_row = _get_edicion_row(conn, slug)
        taller_id = edicion_row["taller_id"]
        try:
            conn.execute(
                """
                INSERT INTO interesados_taller (taller_id, nombre, email, telefono)
                VALUES (%s, %s, %s, %s)
                """,
                (taller_id, nombre, email, telefono),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {"ok": True}


# ── Endpoints admin ───────────────────────────────────────────────────────────

class ClaseBody(BaseModel):
    fecha: str  # YYYY-MM-DD
    hora_inicio_min: int = Field(..., ge=0, le=1440)  # minutos desde medianoche (510 = 8:30)
    hora_fin_min: int = Field(..., ge=0, le=1440)
    # Contenido rico (F2). `id` presente = actualizar esa clase (preserva su
    # portada); ausente = clase nueva. `portada_*` solo se honra en INSERT
    # (caso "copiar clases de otra edición") — el cambio de portada de una
    # clase existente va por sus endpoints dedicados.
    id: int | None = None
    titulo: str = ""
    descripcion: str = ""
    nota: str = ""
    portada_media_id: int | None = None
    portada_url: str = ""


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
    # F2 borradores: una edición NACE despublicada ("ir armándolo sin que esté
    # en la web") — el Switch "Publicado" del admin es la puerta. Publicar
    # re-verifica la disponibilidad del estudio.
    activo: bool = False
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
    terminos: str = ""
    beneficios: str = ""
    pregunta_experiencia: str = ""
    mensaje_confirmacion: str = ""
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
    terminos: str | None = None
    beneficios: str | None = None
    pregunta_experiencia: str | None = None
    mensaje_confirmacion: str | None = None


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

            # F2 borradores: un borrador no bloquea el estudio (fix e.activo de
            # F1), así que solo se verifica disponibilidad si nace PUBLICADA.
            # El chequeo de un borrador corre al publicarlo (PATCH activo=true).
            if ed.activo:
                estudio = _get_estudio_row(conn)
                if estudio["equipo_id"]:
                    conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_ADVISORY_NS_ESTUDIO, 1))
                    verificar_sesiones_disponibles(conn, estudio, clases)

            fechas = [c["fecha"] for c in clases]
            fecha_inicio = min(fechas)
            fecha_fin = max(fechas)

            # Crear concepto en talleres. OJO: `activo` del CONCEPTO queda TRUE
            # (kill-switch general, no la puerta de publicación) — la puerta es
            # el `activo` de la EDICIÓN: sin edición activa no aparece nada
            # público, así el concepto se arma en borrador igual.
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
                    tipo_taller, numero_edicion, slug_base,
                    terminos, beneficios, pregunta_experiencia, mensaje_confirmacion
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, TRUE, %s, %s, %s,
                    %s, %s, %s, %s
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
                    ed.direccion.strip(), body.notif_email.strip(),
                    ed.tipo_taller, ed_numero, slug_base,
                    body.terminos.strip(), body.beneficios.strip(),
                    body.pregunta_experiencia.strip(), body.mensaje_confirmacion.strip(),
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
            # Re-leer de la DB: las clases recién insertadas tienen id (el admin
            # lo necesita para subir portadas / upsert sin refetch). DEBE ir
            # DENTRO del `with` — usar `conn` después de que el context manager
            # lo devuelve al pool deja una transacción implícita abierta que
            # bloquea el próximo `ALTER TABLE`/lock de otra sesión (candado:
            # test_talleres_f2_db.py, se colgaba justo por esto).
            clases_out = _get_clases(conn, e_row["id"])
        except Exception:
            conn.rollback()
            raise

    return _concepto_to_admin_dict(t_row, [_edicion_to_admin_dict(e_row, clases_out)])


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

            # F2 borradores: solo verificar el estudio si nace PUBLICADA (el
            # chequeo de un borrador corre al publicar).
            if body.activo:
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
            # Re-leer de la DB: las clases recién insertadas tienen id (el admin
            # lo necesita para subir portadas / upsert sin refetch). DENTRO del
            # `with` — ver comentario gemelo en admin_create_taller.
            clases_out = _get_clases(conn, edicion_id)
        except Exception:
            conn.rollback()
            raise

    return _edicion_to_admin_dict(e_row, clases_out)


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
    if body.terminos is not None:
        sets.append("terminos = %s"); params.append(body.terminos.strip())
    if body.beneficios is not None:
        sets.append("beneficios = %s"); params.append(body.beneficios.strip())
    if body.pregunta_experiencia is not None:
        sets.append("pregunta_experiencia = %s"); params.append(body.pregunta_experiencia.strip())
    if body.mensaje_confirmacion is not None:
        sets.append("mensaje_confirmacion = %s"); params.append(body.mensaje_confirmacion.strip())

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
                "SELECT taller_id, cupos_total, cupos_confirmados, activo "
                "FROM ediciones_taller WHERE id = %s FOR UPDATE",
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

            # F2 borradores: el estudio se verifica cuando el estado RESULTANTE
            # es publicado — al editar clases de una edición activa, o al
            # PUBLICAR (activo false→true; un borrador no bloqueó su franja, así
            # que puede haber aparecido una reserva → 409 claro acá, no choque
            # silencioso). Editar un borrador no chequea nada.
            resultara_activa = body.activo if body.activo is not None else existing["activo"]
            publicando = bool(body.activo) and not existing["activo"]
            clases_a_verificar = new_clases
            if publicando and clases_a_verificar is None:
                from datetime import date as _dt_date
                clases_a_verificar = [
                    {"fecha": _dt_date.fromisoformat(c["fecha"]),
                     "hora_inicio_min": c["hora_inicio_min"],
                     "hora_fin_min": c["hora_fin_min"]}
                    for c in _get_clases(conn, edicion_id)
                ]
            if resultara_activa and clases_a_verificar and (new_clases is not None or publicando):
                estudio = _get_estudio_row(conn)
                if estudio["equipo_id"]:
                    conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_ADVISORY_NS_ESTUDIO, 1))
                    # Excluir este taller del chequeo (sus propias clases activas)
                    verificar_sesiones_disponibles(
                        conn, estudio, clases_a_verificar,
                        exclude_taller_id=existing["taller_id"],
                    )

            if new_clases is not None:
                fechas = [c["fecha"] for c in new_clases]
                sets.append("fecha_inicio = %s"); params.append(min(fechas))
                sets.append("fecha_fin = %s"); params.append(max(fechas))
                # Upsert (F2): preserva la portada de las clases existentes —
                # el delete+insert ciego de antes la perdía en cada edición.
                _upsert_clases(conn, edicion_id, new_clases)

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
            # DENTRO del `with` — ver comentario gemelo en admin_create_taller.
            clases_out = _get_clases(conn, edicion_id)
        except Exception:
            conn.rollback()
            raise
    return _edicion_to_admin_dict(e_row, clases_out)


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


# ── Portada por clase (F2) ────────────────────────────────────────────────────
# La portada es la imagen de marketing de una clase (se ve en la card colapsable
# de la landing). Solo clases YA GUARDADAS (necesitan id); el upsert de clases
# NO la toca — cambia únicamente por estos dos endpoints.

_PORTADA_SPECS = [
    DeriveSpec(name="display", square=False, max_width=1200),
    DeriveSpec(name="display-sm", square=False, max_width=480),
]


@router.post("/admin/clases/{clase_id}/portada")
@limiter.limit("20/minute")
async def admin_upload_portada_clase(clase_id: int, request: Request):
    """Sube la portada de una clase a R2 vía el motor de media."""
    require_admin(request)
    with get_db() as conn:
        row = conn.execute("SELECT id FROM clases_taller WHERE id = %s", (clase_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Clase no encontrada")

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
            asset = store_upload(raw, kind="taller", derive_specs=_PORTADA_SPECS, conn=conn)
            display = asset.variant("display") or (asset.variants[0] if asset.variants else None)
            url = display.url if display else ""
            conn.execute(
                "UPDATE clases_taller SET portada_media_id = %s, portada_url = %s WHERE id = %s",
                (asset.id, url, clase_id),
            )
            conn.commit()
    except MediaError as e:
        raise HTTPException(e.status, e.detail)
    except Exception as e:
        logger.error("upload_portada_clase: error inesperado: %s", e, exc_info=True)
        raise HTTPException(502, "No se pudo subir la portada. Intentá de nuevo.")

    return {"ok": True, "url": url, "media_id": asset.id}


@router.delete("/admin/clases/{clase_id}/portada")
@limiter.limit("30/minute")
def admin_delete_portada_clase(clase_id: int, request: Request):
    """Quita la portada de una clase (el asset queda en media_assets; el
    SET NULL del FK lo desengancha — no se purga R2 acá, mismo criterio que
    la foto de instructor)."""
    require_admin(request)
    with get_db() as conn:
        row = conn.execute("SELECT id FROM clases_taller WHERE id = %s", (clase_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Clase no encontrada")
        conn.execute(
            "UPDATE clases_taller SET portada_media_id = NULL, portada_url = '' WHERE id = %s",
            (clase_id,),
        )
        conn.commit()
    return {"ok": True}


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


@router.get("/admin/ediciones/{edicion_id}/inscripciones")
def admin_list_inscripciones_edicion(edicion_id: int, request: Request):
    """Lista inscripciones de una edición específica."""
    require_admin(request)
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT ti.*, e.numero_edicion, e.slug AS edicion_slug
            FROM taller_inscripciones ti
            LEFT JOIN ediciones_taller e ON e.id = ti.edicion_id
            WHERE ti.edicion_id = %s
            ORDER BY ti.en_lista_espera, ti.created_at
            """,
            (edicion_id,),
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
