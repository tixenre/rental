"""
routes/talleres.py — Workshops públicos: listing, detalle, upload comprobante,
inscripción + notificaciones por email. Vista admin (read-only) de inscripciones.
"""

import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from admin_guard import require_admin
from database import get_db, now_ar
from services.email import send_email
from services.email.service import get_admin_to
from services.media.storage import put as _r2_put

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


def _taller_to_dict(row) -> dict:
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
    }


# ── Endpoints públicos ────────────────────────────────────────────────────────

@router.get("/talleres")
def list_talleres():
    """Lista todos los talleres activos."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM talleres WHERE activo = TRUE ORDER BY fecha_inicio"
        ).fetchall()
    return [_taller_to_dict(r) for r in rows]


@router.get("/talleres/{slug}")
def get_taller(slug: str):
    """Detalle de un taller."""
    with get_db() as conn:
        row = _get_taller(conn, slug)
    return _taller_to_dict(row)


@router.post("/talleres/{slug}/upload-comprobante")
async def upload_comprobante(slug: str, request: Request):
    """Recibe el comprobante de pago (multipart, campo 'file') y lo sube a R2.
    Devuelve la URL pública. No requiere auth — es parte del flujo de inscripción."""
    # Verificar que el taller existe
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
    # Determinar extensión según content type
    ext_map = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/heic": "heic",
        "application/pdf": "pdf",
    }
    ext = ext_map.get(content_type, "bin")

    ts = int(time.time() * 1000)
    uid = uuid.uuid4().hex[:8]
    key = f"talleres/{slug}/comprobante-{ts}-{uid}.{ext}"

    try:
        url = _r2_put(key, raw, content_type)
    except Exception as e:
        logger.error("upload_comprobante: R2 error: %s", e)
        raise HTTPException(502, "No se pudo subir el archivo. Intentá de nuevo.")

    return {"url": url, "key": key}


class InscripcionBody(BaseModel):
    nombre: str
    email: EmailStr
    telefono: str
    experiencia: str | None = None
    comprobante_url: str | None = None


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
        taller = _get_taller(conn, slug)

        en_lista = taller["cupos_confirmados"] >= taller["cupos_total"]

        cur = conn.execute(
            """
            INSERT INTO taller_inscripciones
                (taller_id, nombre, email, telefono, experiencia, comprobante_url, en_lista_espera)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (
                taller["id"],
                nombre,
                email,
                telefono,
                body.experiencia or None,
                body.comprobante_url or None,
                en_lista,
            ),
        )
        row = cur.fetchone()
        inscripcion_id = row["id"]

        if not en_lista:
            conn.execute(
                "UPDATE talleres SET cupos_confirmados = cupos_confirmados + 1 WHERE id = %s",
                (taller["id"],),
            )

    nombre_pila = nombre.split()[0]
    fecha_str = now_ar().strftime("%-d de %B de %Y, %H:%M hs")
    admin_to = taller["notif_email"] or get_admin_to()

    ctx_admin = {
        "taller_nombre": taller["nombre"],
        "nombre": nombre,
        "email": email,
        "telefono": telefono,
        "experiencia": body.experiencia or "",
        "comprobante_url": body.comprobante_url or "",
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

@router.get("/admin/talleres")
def admin_list_talleres(request: Request):
    """Lista todos los talleres (admin)."""
    require_admin(request)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM talleres ORDER BY fecha_inicio DESC"
        ).fetchall()
    return [_taller_to_dict(r) for r in rows]


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
