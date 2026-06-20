"""Cuenta del cliente: registro + perfil (#501 — extraído del god-module
`routes/cliente_portal.py`).

Alta del cliente (registro vía token de invitación, mintea la sesión) y perfil
(ver / editar datos personales y fiscales). Registra sus rutas en el router
compartido del paquete `routes.cliente_portal`. `require_cliente` (guard) vive en
`core`.
"""
import logging
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from itsdangerous import BadSignature, SignatureExpired

from database import get_db, row_to_dict
from routes.auth import signer, COOKIE_SECURE, SESSION_MAX_AGE
from services.precios import es_responsable_inscripto
from rate_limit import limiter
from routes.cliente_portal.core import router, require_cliente, cliente_verificado

logger = logging.getLogger(__name__)


# ── Registro ─────────────────────────────────────────────────────────────────

class RegistroCreate(BaseModel):
    token:    str
    nombre:   str
    apellido: str
    telefono: str
    direccion: str
    cuit:     str
    perfil_impuestos:   Optional[str] = "consumidor_final"
    direccion_maps_url: Optional[str] = None
    # Datos para Factura A — sólo relevantes si perfil = responsable_inscripto.
    razon_social:       Optional[str] = None
    domicilio_fiscal:   Optional[str] = None
    email_facturacion:  Optional[str] = None


@router.get("/api/cliente/registro-info")
@limiter.limit("5/minute")
def cliente_registro_info(request: Request, t: str):
    """Valida el token de registro y devuelve email/nombre. Solo lectura."""
    try:
        payload = signer.loads(t, max_age=1800)
    except (SignatureExpired, BadSignature):
        raise HTTPException(400, "Token inválido o expirado")
    if payload.get("tipo") != "registro":
        raise HTTPException(400, "Token inválido")
    return {"email": payload["email"], "name": payload["name"]}


@router.post("/api/cliente/registro")
@limiter.limit("5/minute")
def cliente_registro(request: Request, data: RegistroCreate):
    # Validar token de registro (firmado por Google callback, max 30 min)
    try:
        payload = signer.loads(data.token, max_age=1800)
    except SignatureExpired:
        raise HTTPException(400, "El enlace de registro expiró. Volvé a ingresar con Google.")
    except BadSignature:
        raise HTTPException(400, "Token de registro inválido.")

    if payload.get("tipo") != "registro":
        raise HTTPException(400, "Token inválido.")

    email = payload["email"]
    name  = payload["name"]

    if not data.nombre.strip() or not data.apellido.strip() or not data.telefono.strip():
        raise HTTPException(400, "Nombre, apellido y teléfono son obligatorios.")

    with get_db() as conn:
        # Verificar que no se haya registrado ya (doble submit)
        existente = conn.execute(
            "SELECT id FROM clientes WHERE LOWER(email) = LOWER(?)", (email,)
        ).fetchone()
        if existente:
            cliente_id = existente["id"]
        else:
            # Sólo guardamos datos de Factura A si el perfil es responsable
            # inscripto — el resto los puede tener vacíos en DB.
            perfil = data.perfil_impuestos or "consumidor_final"
            es_ri = es_responsable_inscripto(perfil)
            conn.execute("""
                INSERT INTO clientes (
                    nombre, apellido, email, telefono, direccion, cuit,
                    perfil_impuestos, direccion_maps_url,
                    razon_social, domicilio_fiscal, email_facturacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.nombre.strip(),
                data.apellido.strip(),
                email,
                data.telefono.strip(),
                data.direccion.strip() or "-",
                data.cuit.strip() or "-",
                perfil,
                data.direccion_maps_url or None,
                (data.razon_social or "").strip() or None if es_ri else None,
                (data.domicilio_fiscal or "").strip() or None if es_ri else None,
                (data.email_facturacion or "").strip().lower() or None if es_ri else None,
            ))
            conn.commit()
            cliente_id = conn.execute(
                "SELECT id FROM clientes WHERE LOWER(email) = LOWER(?)", (email,)
            ).fetchone()["id"]

        session_data = {"email": email, "name": name, "role": "cliente", "cliente_id": cliente_id}
        token = signer.dumps(session_data)
        res = JSONResponse({"ok": True})
        res.set_cookie("session", token, httponly=True, samesite="lax",
                       secure=COOKIE_SECURE, max_age=SESSION_MAX_AGE)
        return res


# ── Perfil ────────────────────────────────────────────────────────────────────

@router.get("/api/cliente/me")
def cliente_me(request: Request):
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        # `created_at` lo usa el drawer del portal para mostrar "Cliente desde
        # [año]" — no es opcional, el cliente espera verlo en su perfil.
        row = conn.execute(
            """SELECT id, nombre, apellido, email, telefono, direccion, cuit,
                      perfil_impuestos, descuento, direccion_maps_url,
                      razon_social, domicilio_fiscal, email_facturacion,
                      created_at,
                      dni, cuil, dni_validado_at,
                      nombre_renaper, apellido_renaper, fecha_nacimiento_renaper,
                      direccion_renaper, apodo
               FROM clientes WHERE id = ?""",
            (cliente_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Cliente no encontrado")
        return row_to_dict(row)


class PerfilUpdate(BaseModel):
    nombre:    Optional[str] = None
    apellido:  Optional[str] = None
    telefono:  Optional[str] = None
    direccion: Optional[str] = None
    cuit:      Optional[str] = None
    apodo:     Optional[str] = None
    # Datos fiscales (cliente puede actualizar para Factura A).
    perfil_impuestos:  Optional[str] = None
    razon_social:      Optional[str] = None
    domicilio_fiscal:  Optional[str] = None
    email_facturacion: Optional[str] = None


@router.patch("/api/cliente/me")
def cliente_update_me(data: PerfilUpdate, request: Request):
    """Permite al cliente actualizar sus datos personales.

    Tras verificar identidad (dni_validado_at IS NOT NULL) solo `telefono` y
    `apodo` son editables — el resto queda bloqueado (los datos legales los
    certifica RENAPER). NO se permite cambiar email (clave de identidad OAuth)
    ni descuento.
    """
    session = require_cliente(request)
    cliente_id = session["cliente_id"]

    with get_db() as conn:
        verificado = cliente_verificado(conn, cliente_id)

    # Campos bloqueados post-verificación (datos que certifica RENAPER).
    _BLOQUEADOS = ("nombre", "apellido", "direccion", "cuit",
                   "perfil_impuestos", "razon_social", "domicilio_fiscal", "email_facturacion")
    if verificado:
        for campo in _BLOQUEADOS:
            if getattr(data, campo, None) is not None:
                raise HTTPException(
                    403,
                    "Los datos personales no pueden modificarse tras la verificación de identidad. "
                    "Solo podés editar teléfono y apodo.",
                )

    sets, vals = [], []
    if data.nombre is not None:
        n = data.nombre.strip()
        if not n:
            raise HTTPException(400, "El nombre no puede estar vacío")
        sets.append("nombre = ?"); vals.append(n)
    if data.apellido is not None:
        sets.append("apellido = ?"); vals.append(data.apellido.strip())
    if data.telefono is not None:
        sets.append("telefono = ?"); vals.append(data.telefono.strip())
    if data.direccion is not None:
        sets.append("direccion = ?"); vals.append(data.direccion.strip())
    if data.cuit is not None:
        sets.append("cuit = ?"); vals.append(data.cuit.strip() or None)
    if data.apodo is not None:
        sets.append("apodo = ?"); vals.append(data.apodo.strip() or None)
    if data.perfil_impuestos is not None:
        p = data.perfil_impuestos.strip()
        if p not in ("consumidor_final", "responsable_inscripto", "monotributo", "exento"):
            raise HTTPException(400, "Perfil impositivo inválido")
        sets.append("perfil_impuestos = ?"); vals.append(p)
    if data.razon_social is not None:
        sets.append("razon_social = ?"); vals.append(data.razon_social.strip() or None)
    if data.domicilio_fiscal is not None:
        sets.append("domicilio_fiscal = ?"); vals.append(data.domicilio_fiscal.strip() or None)
    if data.email_facturacion is not None:
        sets.append("email_facturacion = ?")
        vals.append(data.email_facturacion.strip().lower() or None)

    if not sets:
        raise HTTPException(400, "Sin cambios")

    with get_db() as conn:
        try:
            vals.append(cliente_id)
            conn.execute(f"UPDATE clientes SET {', '.join(sets)} WHERE id = ?", tuple(vals))
            conn.commit()
            row = conn.execute(
                """SELECT id, nombre, apellido, email, telefono, direccion, cuit,
                          perfil_impuestos, descuento, direccion_maps_url,
                          razon_social, domicilio_fiscal, email_facturacion,
                          dni, cuil, dni_validado_at,
                          nombre_renaper, apellido_renaper, fecha_nacimiento_renaper,
                          direccion_renaper, apodo
                   FROM clientes WHERE id = ?""",
                (cliente_id,),
            ).fetchone()
            return row_to_dict(row) if row else {}
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            logger.exception("Error al actualizar el perfil del cliente")
            raise HTTPException(500, "No se pudo actualizar el perfil")
