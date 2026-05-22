"""
routes/cliente_portal.py — Portal de clientes (solo Google OAuth).
"""

import datetime
from math import ceil

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import Optional

from database import get_db, row_to_dict
from routes.auth import get_session, signer, COOKIE_SECURE, SESSION_MAX_AGE
from itsdangerous import BadSignature, SignatureExpired
from pdf import _pedido_html, _albaran_html, _contrato_html, _render_pdf, _pedido_filename

router = APIRouter()


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
def cliente_crear_pedido(data: PedidoClienteCreate, request: Request):
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
    return create_pedido(payload)


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
                SELECT ai.equipo_id, ai.cantidad, ai.precio_jornada, ai.subtotal,
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

class SolicitudItemIn(BaseModel):
    equipo_id: int
    cantidad:  int


class SolicitudCreate(BaseModel):
    """Payload del cliente para pedir una modificación.

    Todos los campos son opcionales: si `items` viene, representa el estado
    final deseado de los equipos (no un diff). Si `fecha_desde`/`fecha_hasta`
    vienen, reemplazan las del pedido. `mensaje` es texto libre opcional.
    Si no viene nada estructurado y solo hay `mensaje`, se acepta como
    "modificación libre" (back-compat con el shape viejo).
    """
    mensaje:     Optional[str] = None
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    items:       Optional[list[SolicitudItemIn]] = None


def _jornadas(fecha_desde: Optional[str], fecha_hasta: Optional[str]) -> int:
    if not fecha_desde or not fecha_hasta:
        return 1
    try:
        d0 = datetime.datetime.fromisoformat(fecha_desde)
        d1 = datetime.datetime.fromisoformat(fecha_hasta)
    except ValueError:
        return 1
    return max(1, ceil((d1 - d0).total_seconds() / 3600 / 24))


def _load_solicitud_full(conn, solicitud_id: int) -> dict:
    """Devuelve la solicitud + pedido_actual (fechas + items snapshot) +
    propuesta (fechas + items)."""
    row = conn.execute("""
        SELECT sm.*, c.nombre AS cliente_nombre, c.apellido AS cliente_apellido,
               c.email AS cliente_email, a.numero_pedido,
               a.fecha_desde AS pedido_fecha_desde, a.fecha_hasta AS pedido_fecha_hasta,
               a.monto_total AS pedido_monto_total, a.estado AS pedido_estado
        FROM solicitudes_modificacion sm
        JOIN clientes c ON c.id = sm.cliente_id
        JOIN alquileres a ON a.id = sm.pedido_id
        WHERE sm.id = ?
    """, (solicitud_id,)).fetchone()
    if not row:
        return None  # type: ignore[return-value]
    sm = row_to_dict(row)

    pedido_id = sm["pedido_id"]
    items_actuales = conn.execute("""
        SELECT pi.equipo_id, pi.cantidad, pi.precio_jornada,
               e.nombre, e.marca, e.modelo, e.nombre_publico, e.foto_url
        FROM alquiler_items pi
        JOIN equipos e ON e.id = pi.equipo_id
        WHERE pi.pedido_id = ?
        ORDER BY e.nombre
    """, (pedido_id,)).fetchall()

    items_propuesta = conn.execute("""
        SELECT si.equipo_id, si.cantidad, si.precio_jornada,
               e.nombre, e.marca, e.modelo, e.nombre_publico, e.foto_url
        FROM solicitud_items si
        JOIN equipos e ON e.id = si.equipo_id
        WHERE si.solicitud_id = ?
        ORDER BY e.nombre
    """, (solicitud_id,)).fetchall()

    sm["pedido_actual"] = {
        "fecha_desde": sm.pop("pedido_fecha_desde"),
        "fecha_hasta": sm.pop("pedido_fecha_hasta"),
        "monto_total": sm.pop("pedido_monto_total"),
        "estado":      sm.pop("pedido_estado"),
        "items":       [row_to_dict(r) for r in items_actuales],
    }
    fecha_desde_prop = sm.pop("fecha_desde_propuesta", None)
    fecha_hasta_prop = sm.pop("fecha_hasta_propuesta", None)
    # Si el cliente no mandó propuesta estructurada (solo `mensaje`),
    # devolvemos None para que el admin vea "modificación libre" en lugar de
    # un diff sin sentido.
    if not items_propuesta and not fecha_desde_prop and not fecha_hasta_prop:
        sm["propuesta"] = None
    else:
        sm["propuesta"] = {
            "fecha_desde": fecha_desde_prop,
            "fecha_hasta": fecha_hasta_prop,
            "items":       [row_to_dict(r) for r in items_propuesta],
        }
    return sm


@router.post("/api/cliente/pedidos/{id}/solicitar-modificacion")
def cliente_solicitar_modificacion(id: int, data: SolicitudCreate, request: Request):
    session = require_cliente(request)
    cliente_id = session["cliente_id"]

    mensaje = (data.mensaje or "").strip()
    fecha_desde = (data.fecha_desde or "").strip() or None
    fecha_hasta = (data.fecha_hasta or "").strip() or None
    items_in = data.items or []

    if not mensaje and not fecha_desde and not fecha_hasta and not items_in:
        raise HTTPException(400, "La solicitud está vacía")

    conn = get_db()
    try:
        pedido = conn.execute(
            "SELECT id, estado, fecha_desde, fecha_hasta FROM alquileres "
            "WHERE id = ? AND cliente_id = ?",
            (id, cliente_id)
        ).fetchone()
        if not pedido:
            raise HTTPException(404, "Pedido no encontrado")

        # Solo se pueden solicitar modificaciones en estados activos
        if pedido["estado"] in ("cancelado", "devuelto", "finalizado"):
            raise HTTPException(400, "No se pueden solicitar modificaciones en un pedido finalizado")

        # Evitar duplicados pendientes
        pendiente = conn.execute(
            "SELECT id FROM solicitudes_modificacion WHERE pedido_id = ? AND estado = 'pendiente'",
            (id,)
        ).fetchone()
        if pendiente:
            raise HTTPException(409, "Ya hay una solicitud pendiente para este pedido")

        # Validar fechas si vinieron
        eff_desde = fecha_desde or pedido["fecha_desde"]
        eff_hasta = fecha_hasta or pedido["fecha_hasta"]
        if eff_desde and eff_hasta:
            try:
                d0 = datetime.datetime.fromisoformat(eff_desde)
                d1 = datetime.datetime.fromisoformat(eff_hasta)
                if d1 < d0:
                    raise HTTPException(400, "fecha_hasta debe ser posterior o igual a fecha_desde")
            except ValueError:
                raise HTTPException(400, "Las fechas tienen formato inválido")

        # Validar items: equipos existen, cantidades > 0, no duplicados
        seen = set()
        items_rows: list[tuple] = []
        for it in items_in:
            if it.cantidad <= 0:
                raise HTTPException(400, "Las cantidades deben ser > 0")
            if it.equipo_id in seen:
                raise HTTPException(400, "Hay equipos duplicados en la propuesta")
            seen.add(it.equipo_id)
            eq = conn.execute(
                "SELECT id, precio_jornada FROM equipos WHERE id=?",
                (it.equipo_id,),
            ).fetchone()
            if not eq:
                raise HTTPException(404, f"Equipo {it.equipo_id} no encontrado")
            items_rows.append((it.equipo_id, it.cantidad, eq["precio_jornada"] or 0))

        row = conn.execute(
            """
            INSERT INTO solicitudes_modificacion
              (pedido_id, cliente_id, mensaje,
               fecha_desde_propuesta, fecha_hasta_propuesta)
            VALUES (?,?,?,?,?)
            RETURNING id
            """,
            (id, cliente_id, mensaje or None, fecha_desde, fecha_hasta),
        ).fetchone()
        solicitud_id = row["id"] if isinstance(row, dict) or hasattr(row, "__getitem__") else row[0]

        if items_rows:
            conn.executemany(
                "INSERT INTO solicitud_items (solicitud_id, equipo_id, cantidad, precio_jornada) "
                "VALUES (?,?,?,?)",
                [(solicitud_id, *r) for r in items_rows],
            )

        conn.commit()
        return {"ok": True, "solicitud_id": solicitud_id}
    finally:
        conn.close()


# ── Admin: ver solicitudes pendientes ─────────────────────────────────────────

@router.get("/api/admin/solicitudes")
def admin_solicitudes(request: Request):
    """Lista de solicitudes de modificación (solo admins).

    Cada item incluye el snapshot del pedido actual (fechas + items) y, si el
    cliente mandó una propuesta estructurada, la propuesta (fechas + items).
    Esto le permite al admin renderizar el diff en el back-office.
    """
    session = get_session(request)
    if not session or session.get("role") != "admin":
        raise HTTPException(401, "Acceso denegado")

    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT sm.id
            FROM solicitudes_modificacion sm
            ORDER BY sm.created_at DESC
        """).fetchall()
        return [_load_solicitud_full(conn, r["id"]) for r in rows]
    finally:
        conn.close()


class SolicitudOverride(BaseModel):
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    items:       list[SolicitudItemIn]


class SolicitudRespuesta(BaseModel):
    estado:     str                              # "aprobada" o "rechazada"
    respuesta:  str = ""
    override:   Optional[SolicitudOverride] = None


def _apply_solicitud_a_pedido(
    conn,
    pedido_id: int,
    fecha_desde: Optional[str],
    fecha_hasta: Optional[str],
    items: list[tuple[int, int]],  # (equipo_id, cantidad)
) -> None:
    """Aplica la resolución al pedido: pisa fechas + items + recalcula monto.

    Importado dinámicamente para evitar import cycle con routes.alquileres
    (que importa cosas de este módulo de forma indirecta vía routers en main).
    """
    from routes.alquileres import _aplicar_descuento

    pedido = conn.execute(
        "SELECT fecha_desde, fecha_hasta, descuento_pct FROM alquileres WHERE id=?",
        (pedido_id,),
    ).fetchone()
    if not pedido:
        raise HTTPException(404, "Pedido no encontrado")

    eff_desde = fecha_desde or pedido["fecha_desde"]
    eff_hasta = fecha_hasta or pedido["fecha_hasta"]
    if eff_desde and eff_hasta:
        try:
            d0 = datetime.datetime.fromisoformat(eff_desde)
            d1 = datetime.datetime.fromisoformat(eff_hasta)
            if d1 < d0:
                raise HTTPException(400, "fecha_hasta debe ser posterior o igual a fecha_desde")
        except ValueError:
            raise HTTPException(400, "Las fechas tienen formato inválido")
    jornadas = _jornadas(eff_desde, eff_hasta)

    bruto = 0
    rows: list[tuple] = []
    for equipo_id, cantidad in items:
        eq = conn.execute(
            "SELECT precio_jornada, nombre FROM equipos WHERE id=?", (equipo_id,)
        ).fetchone()
        if not eq:
            raise HTTPException(404, f"Equipo {equipo_id} no encontrado")
        precio = eq["precio_jornada"] or 0
        subtotal = precio * cantidad * jornadas
        bruto += subtotal
        rows.append((pedido_id, equipo_id, cantidad, precio, subtotal))

    monto_total = _aplicar_descuento(bruto, pedido["descuento_pct"] or 0)

    conn.execute("DELETE FROM alquiler_items WHERE pedido_id=?", (pedido_id,))
    if rows:
        conn.executemany(
            """INSERT INTO alquiler_items
                 (pedido_id, equipo_id, cantidad, precio_jornada, subtotal)
                 VALUES (?,?,?,?,?)""",
            rows,
        )
    conn.execute(
        "UPDATE alquileres SET fecha_desde=?, fecha_hasta=?, monto_total=?, updated_at=CURRENT_TIMESTAMP "
        "WHERE id=?",
        (eff_desde, eff_hasta, monto_total, pedido_id),
    )


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
            "SELECT id, pedido_id, estado, fecha_desde_propuesta, fecha_hasta_propuesta "
            "FROM solicitudes_modificacion WHERE id = ?",
            (id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Solicitud no encontrada")
        if row["estado"] != "pendiente":
            raise HTTPException(400, "Esta solicitud ya fue resuelta")

        applied_override = False

        if data.estado == "aprobada":
            # Resolver qué se aplica: override del admin si vino, sino la propuesta.
            if data.override is not None:
                applied_override = True
                items = [(it.equipo_id, it.cantidad) for it in data.override.items]
                _apply_solicitud_a_pedido(
                    conn,
                    row["pedido_id"],
                    data.override.fecha_desde,
                    data.override.fecha_hasta,
                    items,
                )
            else:
                # Items propuestos por el cliente
                prop_items = conn.execute(
                    "SELECT equipo_id, cantidad FROM solicitud_items WHERE solicitud_id=?",
                    (id,),
                ).fetchall()
                items = [(r["equipo_id"], r["cantidad"]) for r in prop_items]
                if items or row["fecha_desde_propuesta"] or row["fecha_hasta_propuesta"]:
                    # Si el cliente no propuso items, copiamos los actuales para no vaciar.
                    if not items:
                        actuales = conn.execute(
                            "SELECT equipo_id, cantidad FROM alquiler_items WHERE pedido_id=?",
                            (row["pedido_id"],),
                        ).fetchall()
                        items = [(r["equipo_id"], r["cantidad"]) for r in actuales]
                    _apply_solicitud_a_pedido(
                        conn,
                        row["pedido_id"],
                        row["fecha_desde_propuesta"],
                        row["fecha_hasta_propuesta"],
                        items,
                    )
                # Si la solicitud era solo `mensaje` libre, no aplicamos nada
                # automático — el admin va a editar el pedido a mano.

        conn.execute(
            """UPDATE solicitudes_modificacion
                  SET estado = ?, respuesta = ?, admin_override = ?,
                      resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
                WHERE id = ?""",
            (data.estado, data.respuesta, applied_override,
             session.get("email") or session.get("name") or "admin", id),
        )
        conn.commit()
        return {"ok": True, "applied_override": applied_override}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
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
