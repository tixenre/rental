"""
routes/cliente_portal.py — Portal de clientes (solo Google OAuth).
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from database import get_db, row_to_dict
from routes.auth import get_session, signer, COOKIE_SECURE, SESSION_MAX_AGE
from supabase_auth import upsert_cliente_from_claims
from itsdangerous import BadSignature, SignatureExpired

router = APIRouter()


# ── Auth helper ───────────────────────────────────────────────────────────────

def require_cliente(request: Request) -> dict:
    """
    Devuelve `{cliente_id, email, name, role}` aceptando dos métodos:
      1. JWT de Supabase Auth (frontend Lovable) — se hace upsert en `clientes`.
      2. Cookie de sesión clásica (portal cliente con login propio).
    """
    claims = getattr(request.state, "supabase_claims", None)
    if claims:
        cliente = upsert_cliente_from_claims(claims)
        return {
            "cliente_id": cliente["id"],
            "email": cliente.get("email"),
            "name": cliente.get("nombre"),
            "role": "cliente",
        }
    session = get_session(request)
    if not session or session.get("role") != "cliente":
        raise HTTPException(401, "Sesión de cliente requerida")
    return session


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


@router.get("/api/cliente/registro-info")
def cliente_registro_info(t: str):
    """Valida el token de registro y devuelve email/nombre. Solo lectura."""
    try:
        payload = signer.loads(t, max_age=1800)
    except (SignatureExpired, BadSignature):
        raise HTTPException(400, "Token inválido o expirado")
    if payload.get("tipo") != "registro":
        raise HTTPException(400, "Token inválido")
    return {"email": payload["email"], "name": payload["name"]}


@router.post("/api/cliente/registro")
def cliente_registro(data: RegistroCreate):
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

    conn = get_db()
    try:
        # Verificar que no se haya registrado ya (doble submit)
        existente = conn.execute(
            "SELECT id FROM clientes WHERE LOWER(email) = LOWER(?)", (email,)
        ).fetchone()
        if existente:
            cliente_id = existente["id"]
        else:
            conn.execute("""
                INSERT INTO clientes (nombre, apellido, email, telefono, direccion, cuit, perfil_impuestos, direccion_maps_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.nombre.strip(),
                data.apellido.strip(),
                email,
                data.telefono.strip(),
                data.direccion.strip() or "-",
                data.cuit.strip() or "-",
                data.perfil_impuestos or "consumidor_final",
                data.direccion_maps_url or None,
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
    finally:
        conn.close()


# ── Perfil ────────────────────────────────────────────────────────────────────

@router.get("/api/cliente/me")
def cliente_me(request: Request):
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, nombre, apellido, email, telefono, direccion, cuit, perfil_impuestos, descuento, direccion_maps_url FROM clientes WHERE id = ?",
            (cliente_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Cliente no encontrado")
        return row_to_dict(row)
    finally:
        conn.close()


# ── Pedidos ───────────────────────────────────────────────────────────────────

@router.get("/api/cliente/pedidos")
def cliente_pedidos(request: Request):
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    conn = get_db()
    try:
        pedidos = conn.execute("""
            SELECT id, numero_pedido, estado, fecha_desde, fecha_hasta,
                   monto_total, monto_pagado, descuento_pct, notas, created_at
            FROM alquileres
            WHERE cliente_id = ?
            ORDER BY created_at DESC
        """, (cliente_id,)).fetchall()

        result = []
        for p in pedidos:
            d = row_to_dict(p)
            items = conn.execute("""
                SELECT ai.cantidad, ai.precio_jornada, ai.subtotal,
                       e.nombre, e.marca, e.foto_url
                FROM alquiler_items ai
                JOIN equipos e ON e.id = ai.equipo_id
                WHERE ai.pedido_id = ?
            """, (p["id"],)).fetchall()
            d["items"] = [row_to_dict(i) for i in items]

            # Solicitudes de modificación pendientes
            solic = conn.execute("""
                SELECT id, mensaje, estado, respuesta, created_at
                FROM solicitudes_modificacion
                WHERE pedido_id = ?
                ORDER BY created_at DESC
            """, (p["id"],)).fetchall()
            d["solicitudes"] = [row_to_dict(s) for s in solic]

            result.append(d)
        return result
    finally:
        conn.close()


@router.get("/api/cliente/pedidos/{id}")
def cliente_pedido_detalle(id: int, request: Request):
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    conn = get_db()
    try:
        pedido = conn.execute("""
            SELECT id, numero_pedido, estado, fecha_desde, fecha_hasta,
                   monto_total, monto_pagado, descuento_pct, notas, created_at
            FROM alquileres
            WHERE id = ? AND cliente_id = ?
        """, (id, cliente_id)).fetchone()
        if not pedido:
            raise HTTPException(404, "Pedido no encontrado")

        d = row_to_dict(pedido)

        items = conn.execute("""
            SELECT ai.cantidad, ai.precio_jornada, ai.subtotal,
                   e.id AS equipo_id, e.nombre, e.marca, e.foto_url
            FROM alquiler_items ai
            JOIN equipos e ON e.id = ai.equipo_id
            WHERE ai.pedido_id = ?
        """, (id,)).fetchall()
        d["items"] = [row_to_dict(i) for i in items]

        pagos = conn.execute("""
            SELECT monto, concepto, fecha FROM alquiler_pagos
            WHERE pedido_id = ? ORDER BY fecha
        """, (id,)).fetchall()
        d["pagos"] = [row_to_dict(p) for p in pagos]

        solicitudes = conn.execute("""
            SELECT id, mensaje, estado, respuesta, created_at
            FROM solicitudes_modificacion
            WHERE pedido_id = ? ORDER BY created_at DESC
        """, (id,)).fetchall()
        d["solicitudes"] = [row_to_dict(s) for s in solicitudes]

        return d
    finally:
        conn.close()


# ── Solicitud de modificación ─────────────────────────────────────────────────

class SolicitudCreate(BaseModel):
    mensaje: str


@router.post("/api/cliente/pedidos/{id}/solicitar-modificacion")
def cliente_solicitar_modificacion(id: int, data: SolicitudCreate, request: Request):
    session = require_cliente(request)
    cliente_id = session["cliente_id"]

    if not data.mensaje.strip():
        raise HTTPException(400, "El mensaje no puede estar vacío")

    conn = get_db()
    try:
        pedido = conn.execute(
            "SELECT id, estado FROM alquileres WHERE id = ? AND cliente_id = ?",
            (id, cliente_id)
        ).fetchone()
        if not pedido:
            raise HTTPException(404, "Pedido no encontrado")

        # Solo se pueden solicitar modificaciones en estados activos
        if pedido["estado"] in ("cancelado", "devuelto"):
            raise HTTPException(400, "No se pueden solicitar modificaciones en un pedido finalizado")

        # Evitar duplicados pendientes
        pendiente = conn.execute(
            "SELECT id FROM solicitudes_modificacion WHERE pedido_id = ? AND estado = 'pendiente'",
            (id,)
        ).fetchone()
        if pendiente:
            raise HTTPException(409, "Ya hay una solicitud pendiente para este pedido")

        conn.execute(
            "INSERT INTO solicitudes_modificacion (pedido_id, cliente_id, mensaje) VALUES (?,?,?)",
            (id, cliente_id, data.mensaje.strip())
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ── Admin: ver solicitudes pendientes ─────────────────────────────────────────

@router.get("/api/admin/solicitudes")
def admin_solicitudes(request: Request):
    """Lista de solicitudes de modificación (solo admins)."""
    session = get_session(request)
    if not session or session.get("role") != "admin":
        raise HTTPException(401, "Acceso denegado")

    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT sm.id, sm.pedido_id, sm.mensaje, sm.estado, sm.respuesta, sm.created_at,
                   c.nombre AS cliente_nombre, c.apellido AS cliente_apellido,
                   a.numero_pedido
            FROM solicitudes_modificacion sm
            JOIN clientes c ON c.id = sm.cliente_id
            JOIN alquileres a ON a.id = sm.pedido_id
            ORDER BY sm.created_at DESC
        """).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


class SolicitudRespuesta(BaseModel):
    estado: str     # aprobada / rechazada
    respuesta: str = ""


@router.patch("/api/admin/solicitudes/{id}")
def admin_responder_solicitud(id: int, data: SolicitudRespuesta, request: Request):
    session = get_session(request)
    if not session or session.get("role") != "admin":
        raise HTTPException(401, "Acceso denegado")
    if data.estado not in ("aprobada", "rechazada"):
        raise HTTPException(400, "Estado debe ser 'aprobada' o 'rechazada'")

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM solicitudes_modificacion WHERE id = ?", (id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Solicitud no encontrada")
        conn.execute(
            "UPDATE solicitudes_modificacion SET estado = ?, respuesta = ? WHERE id = ?",
            (data.estado, data.respuesta, id)
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
