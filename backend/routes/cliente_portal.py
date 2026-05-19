"""
routes/cliente_portal.py — Portal de clientes (solo Google OAuth).
"""

import datetime
import json
import logging
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import Optional

from database import get_db, row_to_dict
from routes.auth import get_session, signer, COOKIE_SECURE, SESSION_MAX_AGE
from itsdangerous import BadSignature, SignatureExpired
from pdf import _pedido_html, _albaran_html, _contrato_html, _render_pdf, _pedido_filename

logger = logging.getLogger(__name__)
router = APIRouter()


ESTADOS_MODIFICABLES = {"presupuesto", "confirmado"}


def _modificacion_ventana_horas(conn) -> int:
    """Devuelve la ventana de corte (en horas) configurada en app_settings."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'modificacion_ventana_horas'"
    ).fetchone()
    try:
        return int(row["value"]) if row else 24
    except (TypeError, ValueError):
        return 24


def _ventana_cumple(fecha_desde: Optional[str], ventana_horas: int) -> bool:
    """True si todavía estamos a >= ventana_horas del retiro (o si no hay fecha)."""
    if not fecha_desde:
        return True
    try:
        d0 = datetime.datetime.fromisoformat(fecha_desde)
    except ValueError:
        return True
    return (d0 - datetime.datetime.now()).total_seconds() >= ventana_horas * 3600


# ── Documentos disponibles según estado del pedido ───────────────────────────

def _documentos_disponibles(estado: str) -> dict:
    """Devuelve qué PDFs puede descargar el cliente según el estado del pedido."""
    e = (estado or "").lower()
    confirmado_o_mas = e in ("confirmado", "entregado", "devuelto", "finalizado")
    return {
        "remito": confirmado_o_mas,
        "contrato": confirmado_o_mas,
        "albaran": e in ("entregado", "devuelto", "finalizado"),
    }


# ── Auth helper ───────────────────────────────────────────────────────────────

def require_cliente(request: Request) -> dict:
    """Devuelve la sesión del cliente (cookie). 401 si no hay sesión válida."""
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


class PerfilUpdate(BaseModel):
    nombre:    Optional[str] = None
    apellido:  Optional[str] = None
    telefono:  Optional[str] = None
    direccion: Optional[str] = None
    cuit:      Optional[str] = None


@router.patch("/api/cliente/me")
def cliente_update_me(data: PerfilUpdate, request: Request):
    """Permite al cliente actualizar sus datos personales.
    NO se permite cambiar email (clave de identidad OAuth) ni descuento."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]

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

    if not sets:
        raise HTTPException(400, "Sin cambios")

    conn = get_db()
    try:
        vals.append(cliente_id)
        conn.execute(f"UPDATE clientes SET {', '.join(sets)} WHERE id = ?", tuple(vals))
        conn.commit()
        row = conn.execute(
            "SELECT id, nombre, apellido, email, telefono, direccion, cuit, perfil_impuestos, descuento, direccion_maps_url FROM clientes WHERE id = ?",
            (cliente_id,),
        ).fetchone()
        return row_to_dict(row) if row else {}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"Error al actualizar perfil: {e}")
    finally:
        conn.close()


# ── Crear / cancelar pedido ───────────────────────────────────────────────────

class CartItemIn(BaseModel):
    equipo_id:      int
    cantidad:       int
    precio_jornada: int = 0


class PedidoClienteCreate(BaseModel):
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    notas:       Optional[str] = None
    items:       list[CartItemIn] = []


@router.post("/api/cliente/pedidos", status_code=201)
def cliente_crear_pedido(
    data: PedidoClienteCreate, request: Request, background: BackgroundTasks,
):
    """Crea un pedido (estado 'presupuesto') ligado al cliente autenticado."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]

    if not data.items:
        raise HTTPException(400, "El pedido debe tener al menos un ítem")

    # Reusamos la lógica de creación del back-office para mantener una sola fuente.
    from routes.alquileres import create_pedido, PedidoCreate, PedidoItem

    payload = PedidoCreate(
        cliente_id=cliente_id,
        fecha_desde=data.fecha_desde,
        fecha_hasta=data.fecha_hasta,
        notas=data.notas,
        estado="presupuesto",
        items=[
            PedidoItem(
                equipo_id=i.equipo_id,
                cantidad=i.cantidad,
                precio_jornada=i.precio_jornada,
            )
            for i in data.items
        ],
    )
    return create_pedido(payload, background=background)


@router.patch("/api/cliente/pedidos/{id}/cancelar")
def cliente_cancelar_pedido(id: int, request: Request):
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    conn = get_db()
    try:
        p = conn.execute(
            "SELECT estado FROM alquileres WHERE id = ? AND cliente_id = ?",
            (id, cliente_id),
        ).fetchone()
        if not p:
            raise HTTPException(404, "Pedido no encontrado")
        if p["estado"] not in ("borrador", "presupuesto", "solicitado"):
            raise HTTPException(400, "Este pedido ya no se puede cancelar")
        conn.execute("UPDATE alquileres SET estado = 'cancelado' WHERE id = ?", (id,))
        conn.commit()
        return {"ok": True}
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
            ORDER BY created_at DESC NULLS LAST, numero_pedido DESC
        """, (cliente_id,)).fetchall()

        result = []
        for p in pedidos:
            d = row_to_dict(p)
            items = conn.execute("""
                SELECT ai.cantidad, ai.precio_jornada, ai.subtotal,
                       e.nombre, e.marca, e.modelo, e.foto_url,
                       e.nombre_publico, e.nombre_publico_largo
                FROM alquiler_items ai
                JOIN equipos e ON e.id = ai.equipo_id
                WHERE ai.pedido_id = ?
            """, (p["id"],)).fetchall()
            d["items"] = [row_to_dict(i) for i in items]

            pagos = conn.execute("""
                SELECT monto, concepto, fecha
                FROM alquiler_pagos
                WHERE pedido_id = ?
                ORDER BY fecha
            """, (p["id"],)).fetchall()
            d["pagos"] = [row_to_dict(pg) for pg in pagos]

            # Solicitudes de modificación pendientes
            solic = conn.execute("""
                SELECT id, mensaje, estado, respuesta, created_at
                FROM solicitudes_modificacion
                WHERE pedido_id = ?
                ORDER BY created_at DESC
            """, (p["id"],)).fetchall()
            d["solicitudes"] = [row_to_dict(s) for s in solic]

            d["documentos_disponibles"] = _documentos_disponibles(d.get("estado", ""))

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
                   e.id AS equipo_id, e.nombre, e.marca, e.foto_url,
                   e.nombre_publico, e.nombre_publico_largo
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

        d["documentos_disponibles"] = _documentos_disponibles(d.get("estado", ""))

        return d
    finally:
        conn.close()


# ── Solicitud de modificación ─────────────────────────────────────────────────

class ModificacionItemIn(BaseModel):
    equipo_id: int
    cantidad:  int


class ModificacionIn(BaseModel):
    """Cambio que el cliente propone aplicar al pedido.

    Si el pedido está en `presupuesto`, los cambios se aplican directo.
    Si está en `confirmado`, se guarda como propuesta pendiente de aprobación.
    """
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    items:       list[ModificacionItemIn]
    mensaje:     Optional[str] = None  # comentario opcional del cliente


def _validar_modificacion_estado(estado: str) -> None:
    if estado not in ESTADOS_MODIFICABLES:
        raise HTTPException(
            400,
            f"Este pedido no se puede modificar en estado '{estado}'. "
            "Solo se pueden modificar pedidos en presupuesto o confirmado."
        )


def _validar_ventana_corte(conn, fecha_desde_actual: Optional[str]) -> int:
    """Valida ventana de corte. Retorna las horas configuradas (para mensajes)."""
    ventana = _modificacion_ventana_horas(conn)
    if not _ventana_cumple(fecha_desde_actual, ventana):
        raise HTTPException(
            400,
            f"No se puede modificar a menos de {ventana} h del retiro. "
            "Contactanos directamente para coordinar."
        )
    return ventana


def _check_solicitud_pendiente(conn, pedido_id: int) -> None:
    pendiente = conn.execute(
        "SELECT id FROM solicitudes_modificacion WHERE pedido_id = ? AND estado = 'pendiente'",
        (pedido_id,)
    ).fetchone()
    if pendiente:
        raise HTTPException(409, "Ya hay una solicitud pendiente para este pedido")


def _items_payload_to_pedido_items(items: list[ModificacionItemIn], precios: dict[int, int]) -> list:
    """Convierte items del cliente a `PedidoItem` (rellenando precio_jornada
    desde el pedido actual / equipo: el cliente nunca decide el precio)."""
    from routes.alquileres import PedidoItem
    return [
        PedidoItem(
            equipo_id=it.equipo_id,
            cantidad=it.cantidad,
            precio_jornada=precios.get(it.equipo_id, 0),
        )
        for it in items
    ]


def _precios_actuales(conn, pedido_id: int) -> dict[int, int]:
    """Mapa equipo_id → precio_jornada usado actualmente en el pedido.

    Para equipos nuevos que no estaban en el pedido, devuelve el `precio_jornada`
    del catálogo (`equipos.precio_jornada`) como fallback.
    """
    rows = conn.execute(
        "SELECT equipo_id, precio_jornada FROM alquiler_items WHERE pedido_id=?",
        (pedido_id,)
    ).fetchall()
    return {r["equipo_id"]: r["precio_jornada"] for r in rows}


def _equipo_precio_catalogo(conn, equipo_id: int) -> int:
    row = conn.execute(
        "SELECT precio_jornada FROM equipos WHERE id=?", (equipo_id,)
    ).fetchone()
    return int(row["precio_jornada"] or 0) if row else 0


@router.post("/api/cliente/pedidos/{id}/modificacion")
def cliente_modificar_pedido(
    id: int, data: ModificacionIn, request: Request, background: BackgroundTasks,
):
    """Aplica una modificación (directo o como propuesta de aprobación).

    - En `presupuesto`: aplica al pedido (valida stock, fechas, ventana).
    - En `confirmado`: guarda `solicitudes_modificacion` con `cambios_json`
      y dispara email al admin. El pedido no se toca.
    """
    from routes.alquileres import (
        PedidoDatos, _apply_pedido_datos, _apply_pedido_items, _check_stock,
        _get_alquiler_detail,
    )

    session = require_cliente(request)
    cliente_id = session["cliente_id"]

    if not data.items:
        raise HTTPException(400, "El pedido debe tener al menos un ítem")

    conn = get_db()
    try:
        pedido = conn.execute(
            "SELECT * FROM alquileres WHERE id = ? AND cliente_id = ?",
            (id, cliente_id)
        ).fetchone()
        if not pedido:
            raise HTTPException(404, "Pedido no encontrado")

        _validar_modificacion_estado(pedido["estado"])
        _validar_ventana_corte(conn, pedido["fecha_desde"])
        _check_solicitud_pendiente(conn, id)

        # Rellenar precios desde el pedido actual o catálogo (el cliente no
        # puede definir precios).
        precios = _precios_actuales(conn, id)
        for it in data.items:
            if it.equipo_id not in precios:
                precios[it.equipo_id] = _equipo_precio_catalogo(conn, it.equipo_id)

        # ── Caso `presupuesto`: aplicar directo ──────────────────────────
        if pedido["estado"] == "presupuesto":
            # Sólo enviamos fechas si vinieron en el payload (evita pisar a null).
            datos_kwargs = {}
            if data.fecha_desde is not None:
                datos_kwargs["fecha_desde"] = data.fecha_desde
            if data.fecha_hasta is not None:
                datos_kwargs["fecha_hasta"] = data.fecha_hasta
            if datos_kwargs:
                _apply_pedido_datos(conn, id, PedidoDatos(**datos_kwargs))

            pedido_items = _items_payload_to_pedido_items(data.items, precios)
            _apply_pedido_items(conn, id, pedido_items)

            # Re-validar stock con el rango nuevo
            p2 = conn.execute("SELECT fecha_desde, fecha_hasta FROM alquileres WHERE id=?", (id,)).fetchone()
            if p2["fecha_desde"] and p2["fecha_hasta"]:
                problemas = _check_stock(conn, id, p2["fecha_desde"], p2["fecha_hasta"])
                if problemas:
                    raise HTTPException(409, "Sin stock: " + "; ".join(problemas))

            # Auditoría: registramos la modificación directa.
            conn.execute(
                """INSERT INTO solicitudes_modificacion
                   (pedido_id, cliente_id, mensaje, cambios_json, tipo, estado, resolved_at, resolved_by)
                   VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP,?)""",
                (id, cliente_id, data.mensaje, json.dumps(data.model_dump()),
                 "directo", "aprobada", session.get("email") or "cliente")
            )
            conn.commit()

            pedido_actualizado = _get_alquiler_detail(conn, id)
            return {"ok": True, "tipo": "directo", "pedido": pedido_actualizado}

        # ── Caso `confirmado`: guardar propuesta ─────────────────────────
        conn.execute(
            """INSERT INTO solicitudes_modificacion
               (pedido_id, cliente_id, mensaje, cambios_json, tipo, estado)
               VALUES (?,?,?,?,?,'pendiente')""",
            (id, cliente_id, data.mensaje, json.dumps(data.model_dump()),
             "aprobacion")
        )
        conn.commit()

        background.add_task(_enviar_email_solicitud_admin, id, data.model_dump())

        return {"ok": True, "tipo": "aprobacion"}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        logger.error("Error en modificación cliente pedido %s", id, exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/api/cliente/pedidos/{id}/modificacion/{sm_id}")
def cliente_cancelar_solicitud(id: int, sm_id: int, request: Request):
    """El cliente cancela su propia solicitud pendiente."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    conn = get_db()
    try:
        sm = conn.execute(
            """SELECT id, estado FROM solicitudes_modificacion
               WHERE id = ? AND pedido_id = ? AND cliente_id = ?""",
            (sm_id, id, cliente_id)
        ).fetchone()
        if not sm:
            raise HTTPException(404, "Solicitud no encontrada")
        if sm["estado"] != "pendiente":
            raise HTTPException(400, "Esta solicitud ya fue resuelta")
        conn.execute(
            """UPDATE solicitudes_modificacion
               SET estado = 'cancelada', resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
               WHERE id = ?""",
            (session.get("email") or "cliente", sm_id)
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/api/cliente/pedidos/{id}/disponibilidad")
def cliente_disponibilidad(
    id: int, request: Request, fecha_desde: str, fecha_hasta: str,
):
    """Wrapper de /api/disponibilidad con validación de ownership y
    `exclude_pedido_id` automático."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    conn = get_db()
    try:
        owned = conn.execute(
            "SELECT id FROM alquileres WHERE id = ? AND cliente_id = ?",
            (id, cliente_id)
        ).fetchone()
        if not owned:
            raise HTTPException(404, "Pedido no encontrado")
    finally:
        conn.close()
    from routes.alquileres import get_disponibilidad
    return get_disponibilidad(
        fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, exclude_pedido_id=id,
    )


@router.get("/api/cliente/modificacion-config")
def cliente_modificacion_config(request: Request):
    """Devuelve la ventana de corte para que el frontend pueda mostrar/ocultar
    el botón de modificar sin tener que tocar settings."""
    require_cliente(request)
    conn = get_db()
    try:
        return {"ventana_horas": _modificacion_ventana_horas(conn)}
    finally:
        conn.close()


# ── Emails de solicitud/resolución ────────────────────────────────────────────

def _build_diff_payload(pedido_actual: dict, cambios: dict) -> dict:
    """Arma un dict con 'antes vs después' para los templates de email."""
    items_actuales = pedido_actual.get("items") or []
    nombres = {it["equipo_id"]: it.get("nombre") or "—" for it in items_actuales}
    actual_qty = {it["equipo_id"]: it.get("cantidad", 0) for it in items_actuales}
    propuesta_qty = {it["equipo_id"]: it["cantidad"] for it in cambios.get("items") or []}

    todos = set(actual_qty.keys()) | set(propuesta_qty.keys())
    lineas_html, lineas_text = [], []
    for eq_id in todos:
        a = actual_qty.get(eq_id, 0)
        b = propuesta_qty.get(eq_id, 0)
        if a == b:
            continue
        nombre = nombres.get(eq_id, f"equipo #{eq_id}")
        flecha = f"{a} → {b}"
        lineas_html.append(f"<li>{nombre}: {flecha}</li>")
        lineas_text.append(f"  - {nombre}: {flecha}")

    return {
        "fecha_desde_actual":   pedido_actual.get("fecha_desde") or "—",
        "fecha_hasta_actual":   pedido_actual.get("fecha_hasta") or "—",
        "fecha_desde_propuesta": cambios.get("fecha_desde") or "—",
        "fecha_hasta_propuesta": cambios.get("fecha_hasta") or "—",
        "total_actual": pedido_actual.get("monto_total") or 0,
        "diff_html": "<ul>" + "".join(lineas_html) + "</ul>" if lineas_html else "<p>Sin cambios de equipos.</p>",
        "diff_text": "\n".join(lineas_text) if lineas_text else "  (sin cambios de equipos)",
        "mensaje": cambios.get("mensaje") or "",
    }


def _enviar_email_solicitud_admin(pedido_id: int, cambios: dict) -> None:
    """Background task: notifica al admin de una nueva solicitud."""
    from services.email import send_email
    from services.email.service import get_admin_to
    from routes.alquileres import _get_alquiler_detail

    admin_to = get_admin_to()
    if not admin_to:
        return

    conn = get_db()
    try:
        pedido = _get_alquiler_detail(conn, pedido_id)
    except Exception:
        conn.close()
        return
    finally:
        conn.close()

    ctx = {
        "cliente_nombre":  pedido.get("cliente_nombre") or "",
        "cliente_email":   pedido.get("cliente_email") or "",
        "numero_pedido":   pedido.get("numero_pedido") or pedido_id,
        "admin_url":       f"/admin/pedidos/{pedido_id}",
        **_build_diff_payload(pedido, cambios),
    }
    send_email("modificacion_solicitada_admin", admin_to, ctx, pedido_id)


def _enviar_email_resolucion_cliente(
    pedido_id: int, cliente_email: str, cliente_nombre: str,
    numero_pedido, estado: str, respuesta: str,
) -> None:
    """Background task: notifica al cliente cuando se resuelve su solicitud."""
    from services.email import send_email
    estado_label = "aprobada" if estado == "aprobada" else "rechazada"
    ctx = {
        "cliente_nombre": cliente_nombre or "",
        "numero_pedido":  numero_pedido or pedido_id,
        "estado":         estado,
        "estado_label":   estado_label,
        "respuesta":      respuesta or "",
    }
    send_email("modificacion_resuelta_cliente", cliente_email, ctx, pedido_id)


# ── Admin: ver solicitudes y resolverlas ─────────────────────────────────────

@router.get("/api/admin/solicitudes")
def admin_solicitudes(request: Request):
    """Lista de solicitudes de modificación (solo admins)."""
    session = get_session(request)
    if not session or session.get("role") != "admin":
        raise HTTPException(401, "Acceso denegado")

    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT sm.id, sm.pedido_id, sm.mensaje, sm.estado, sm.respuesta,
                   sm.cambios_json, sm.tipo, sm.resolved_at, sm.resolved_by,
                   sm.created_at,
                   c.nombre AS cliente_nombre, c.apellido AS cliente_apellido,
                   c.email AS cliente_email,
                   a.numero_pedido, a.fecha_desde AS pedido_fecha_desde,
                   a.fecha_hasta AS pedido_fecha_hasta, a.monto_total
            FROM solicitudes_modificacion sm
            JOIN clientes c ON c.id = sm.cliente_id
            JOIN alquileres a ON a.id = sm.pedido_id
            ORDER BY
              CASE WHEN sm.estado = 'pendiente' THEN 0 ELSE 1 END,
              sm.created_at DESC
        """).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


class SolicitudRespuesta(BaseModel):
    estado: str     # aprobada / rechazada
    respuesta: str = ""


@router.patch("/api/admin/solicitudes/{id}")
def admin_responder_solicitud(
    id: int, data: SolicitudRespuesta, request: Request, background: BackgroundTasks,
):
    """Resuelve una solicitud de modificación.

    - Si `estado='aprobada'` y la solicitud tiene `cambios_json` (`tipo='aprobacion'`),
      aplica los cambios al pedido reusando los helpers de `routes/alquileres`.
    - Si `estado='rechazada'`, sólo marca y notifica.
    """
    from routes.alquileres import (
        PedidoDatos, _apply_pedido_datos, _apply_pedido_items, _check_stock,
    )

    session = get_session(request)
    if not session or session.get("role") != "admin":
        raise HTTPException(401, "Acceso denegado")
    if data.estado not in ("aprobada", "rechazada"):
        raise HTTPException(400, "Estado debe ser 'aprobada' o 'rechazada'")

    conn = get_db()
    try:
        sm = conn.execute(
            """SELECT sm.*, a.cliente_id, a.fecha_desde, a.estado AS pedido_estado,
                      a.numero_pedido, c.email AS cliente_email,
                      c.nombre AS cliente_nombre
               FROM solicitudes_modificacion sm
               JOIN alquileres a ON a.id = sm.pedido_id
               JOIN clientes c ON c.id = sm.cliente_id
               WHERE sm.id = ?""",
            (id,)
        ).fetchone()
        if not sm:
            raise HTTPException(404, "Solicitud no encontrada")
        if sm["estado"] != "pendiente":
            raise HTTPException(400, "Esta solicitud ya fue resuelta")

        if data.estado == "aprobada" and sm["tipo"] == "aprobacion":
            if sm["pedido_estado"] not in ESTADOS_MODIFICABLES:
                raise HTTPException(
                    400, f"El pedido está en estado '{sm['pedido_estado']}' y ya no admite cambios"
                )
            _validar_ventana_corte(conn, sm["fecha_desde"])

            cambios = sm["cambios_json"] or {}
            if isinstance(cambios, str):
                cambios = json.loads(cambios)

            precios = _precios_actuales(conn, sm["pedido_id"])
            for it in cambios.get("items") or []:
                eq_id = it["equipo_id"]
                if eq_id not in precios:
                    precios[eq_id] = _equipo_precio_catalogo(conn, eq_id)

            datos_kwargs = {}
            if cambios.get("fecha_desde") is not None:
                datos_kwargs["fecha_desde"] = cambios["fecha_desde"]
            if cambios.get("fecha_hasta") is not None:
                datos_kwargs["fecha_hasta"] = cambios["fecha_hasta"]
            if datos_kwargs:
                _apply_pedido_datos(conn, sm["pedido_id"], PedidoDatos(**datos_kwargs))

            pedido_items = _items_payload_to_pedido_items(
                [ModificacionItemIn(**it) for it in cambios.get("items") or []],
                precios,
            )
            _apply_pedido_items(conn, sm["pedido_id"], pedido_items)

            # Re-validar stock con el rango nuevo
            p2 = conn.execute(
                "SELECT fecha_desde, fecha_hasta FROM alquileres WHERE id=?",
                (sm["pedido_id"],)
            ).fetchone()
            if p2["fecha_desde"] and p2["fecha_hasta"]:
                problemas = _check_stock(conn, sm["pedido_id"], p2["fecha_desde"], p2["fecha_hasta"])
                if problemas:
                    raise HTTPException(409, "Sin stock: " + "; ".join(problemas))

        conn.execute(
            """UPDATE solicitudes_modificacion
               SET estado = ?, respuesta = ?,
                   resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
               WHERE id = ?""",
            (data.estado, data.respuesta, session.get("email") or "admin", id)
        )
        conn.commit()

        if sm["cliente_email"]:
            background.add_task(
                _enviar_email_resolucion_cliente,
                sm["pedido_id"], sm["cliente_email"], sm["cliente_nombre"],
                sm["numero_pedido"], data.estado, data.respuesta or "",
            )
        return {"ok": True}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        logger.error("Error resolviendo solicitud %s", id, exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Documentos PDF (cliente) ──────────────────────────────────────────────────

def _load_pedido_para_pdf(conn, pedido_id: int, cliente_id: int) -> dict:
    """Carga el pedido validando ownership y rellena items + componentes."""
    row = conn.execute(
        "SELECT * FROM alquileres WHERE id = ? AND cliente_id = ?",
        (pedido_id, cliente_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Pedido no encontrado")
    pedido = row_to_dict(row)

    items = conn.execute("""
        SELECT pi.cantidad, e.id AS equipo_id, e.nombre, e.marca, e.modelo,
               e.serie, e.valor_reposicion, e.foto_url, pi.precio_jornada, pi.subtotal,
               e.nombre_publico, e.nombre_publico_largo
        FROM alquiler_items pi
        JOIN equipos e ON e.id = pi.equipo_id
        WHERE pi.pedido_id = ?
        ORDER BY e.nombre
    """, (pedido_id,)).fetchall()
    pedido["items"] = [row_to_dict(i) for i in items]

    for item in pedido["items"]:
        comp_rows = conn.execute("""
            SELECT ec.nombre, ec.marca, ec.modelo, ec.serie, ec.valor_reposicion,
                   ec.nombre_publico, ec.nombre_publico_largo, kc.cantidad
            FROM kit_componentes kc
            JOIN equipos ec ON ec.id = kc.componente_id
            WHERE kc.equipo_id = ?
        """, (item['equipo_id'],)).fetchall()
        item['componentes'] = [row_to_dict(c) for c in comp_rows]

    # Datos del cliente para el contrato
    cli = conn.execute(
        "SELECT nombre, apellido, email, telefono, direccion, cuit, perfil_impuestos FROM clientes WHERE id = ?",
        (cliente_id,),
    ).fetchone()
    if cli:
        c = row_to_dict(cli)
        pedido["cliente_nombre"] = f"{c.get('nombre','')} {c.get('apellido','')}".strip()
        pedido["cliente_email"] = c.get("email")
        pedido["cliente_telefono"] = c.get("telefono")
        pedido["cliente_direccion"] = c.get("direccion")
        pedido["cliente_cuit"] = c.get("cuit")
        pedido["cliente_perfil_impuestos"] = c.get("perfil_impuestos")

    return pedido


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def _doc_response(
    html_str: str,
    pdf_filename: str,
    format: str,
):
    """Devuelve HTML inline (preview) o PDF (download) según `format`.

    Issue #106: el cliente puede previsualizar el documento antes de
    descargar el PDF. HTML es más liviano y mejor UX mobile.
    """
    if format == "html":
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_str)
    return None  # caller sigue con PDF


async def _doc_response_or_pdf(html_str: str, pdf_filename: str, format: str):
    preview = _doc_response(html_str, pdf_filename, format)
    if preview is not None:
        return preview
    pdf_bytes = await _render_pdf(html_str)
    from fastapi.responses import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{pdf_filename}"'},
    )


@router.get("/api/cliente/pedidos/{id}/remito.pdf")
@router.get("/api/cliente/pedidos/{id}/remito")
async def cliente_pedido_remito(id: int, request: Request, format: str = "pdf"):
    """Remito del pedido. format=pdf (default, download) o html (preview)."""
    session = require_cliente(request)
    conn = get_db()
    try:
        pedido = _load_pedido_para_pdf(conn, id, session["cliente_id"])
    finally:
        conn.close()
    if not _documentos_disponibles(pedido.get("estado", ""))["remito"]:
        raise HTTPException(403, "El remito estará disponible cuando confirmemos el pedido.")
    return await _doc_response_or_pdf(
        _pedido_html(pedido), _pedido_filename(pedido), format
    )


@router.get("/api/cliente/pedidos/{id}/contrato.pdf")
@router.get("/api/cliente/pedidos/{id}/contrato")
async def cliente_pedido_contrato(id: int, request: Request, format: str = "pdf"):
    """Contrato del pedido. format=pdf (default) o html (preview)."""
    session = require_cliente(request)
    conn = get_db()
    try:
        pedido = _load_pedido_para_pdf(conn, id, session["cliente_id"])
    finally:
        conn.close()
    if not _documentos_disponibles(pedido.get("estado", ""))["contrato"]:
        raise HTTPException(403, "El contrato estará disponible cuando confirmemos el pedido.")
    return await _doc_response_or_pdf(
        _contrato_html(pedido), _pedido_filename(pedido, suffix="contrato"), format
    )


@router.get("/api/cliente/pedidos/{id}/albaran.pdf")
@router.get("/api/cliente/pedidos/{id}/albaran")
async def cliente_pedido_albaran(id: int, request: Request, format: str = "pdf"):
    """Albarán del pedido. format=pdf (default) o html (preview)."""
    session = require_cliente(request)
    conn = get_db()
    try:
        pedido = _load_pedido_para_pdf(conn, id, session["cliente_id"])
    finally:
        conn.close()
    if not _documentos_disponibles(pedido.get("estado", ""))["albaran"]:
        raise HTTPException(403, "El albarán estará disponible al momento de la entrega.")
    return await _doc_response_or_pdf(
        _albaran_html(pedido), _pedido_filename(pedido, suffix="albaran"), format
    )
