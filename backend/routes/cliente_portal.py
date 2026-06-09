"""
routes/cliente_portal.py — Portal de clientes (solo Google OAuth).
"""

import json
import logging
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator
from typing import Optional

from database import get_db, row_to_dict, to_datetime, now_ar
from routes.auth import get_session, signer, COOKIE_SECURE, SESSION_MAX_AGE
from admin_guard import require_admin
from itsdangerous import BadSignature, SignatureExpired
from pdf import _pedido_html, _albaran_html, _contrato_html, _render_pdf, _pedido_filename
from services.precios import es_responsable_inscripto
from rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter()


ESTADOS_MODIFICABLES = {"presupuesto", "confirmado"}

# ── Items: fuente única + proyección por superficie ──────────────────────────
# El portal lee los items de un pedido vía los helpers canónicos de
# routes/alquileres (`_get_alquiler_items` / `_batch_get_alquiler_items` —
# misma query y mismo batch de componentes que el admin) y PROYECTA solo
# estos campos: al cliente no se le expone `pi.*` completo ni stock interno.
_ITEM_CAMPOS_PORTAL = (
    "cantidad", "precio_jornada", "subtotal", "equipo_id", "nombre", "marca",
    "modelo", "foto_url", "nombre_publico", "nombre_publico_largo",
)
# Los documentos (contrato/remito) suman los campos de identificación del equipo.
_ITEM_CAMPOS_DOC = _ITEM_CAMPOS_PORTAL + ("serie", "valor_reposicion")
_COMP_CAMPOS_DOC = (
    "cantidad", "nombre", "marca", "modelo", "serie", "valor_reposicion",
    "nombre_publico", "nombre_publico_largo",
)


def _proyectar(item: dict, campos: tuple) -> dict:
    return {k: item.get(k) for k in campos}


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
        d0 = to_datetime(fecha_desde)
    except ValueError:
        return True
    if d0 is None:
        return True
    return (d0 - now_ar()).total_seconds() >= ventana_horas * 3600


# ── Documentos disponibles según estado del pedido ───────────────────────────

def _documentos_disponibles(estado: str) -> dict:
    """Devuelve qué PDFs puede descargar el cliente según el estado del pedido."""
    e = (estado or "").lower()
    confirmado_o_mas = e in ("confirmado", "retirado", "devuelto", "finalizado")
    return {
        "remito": confirmado_o_mas,
        "contrato": confirmado_o_mas,
        "albaran": e in ("retirado", "devuelto", "finalizado"),
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
        row_actual = conn.execute(
            "SELECT dni_validado_at FROM clientes WHERE id = ?", (cliente_id,)
        ).fetchone()
    verificado = bool(row_actual and row_actual["dni_validado_at"])

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
        except Exception as e:
            conn.rollback()
            raise HTTPException(500, f"Error al actualizar perfil: {e}")


# ── Crear / cancelar pedido ───────────────────────────────────────────────────

class CartItemIn(BaseModel):
    equipo_id:      int
    cantidad:       int
    # `precio_jornada` se acepta por compatibilidad con clientes ya
    # cacheados, pero el server lo IGNORA y resuelve el precio desde
    # `equipos.precio_jornada`. El cliente nunca decide el precio
    # (ver `cliente_crear_pedido`).
    precio_jornada: int = 0


class PedidoClienteCreate(BaseModel):
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    notas:       Optional[str] = None
    items:       list[CartItemIn] = []

    @field_validator("fecha_desde", "fecha_hasta")
    @classmethod
    def _v_fechas(cls, v):
        from routes.alquileres import _validar_fecha_iso
        return _validar_fecha_iso(v)


@router.post("/api/cliente/pedidos", status_code=201)
def cliente_crear_pedido(
    data: PedidoClienteCreate, request: Request, background: BackgroundTasks,
):
    """Crea un pedido (estado 'presupuesto') ligado al cliente autenticado."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]

    with get_db() as conn:
        row_cli = conn.execute(
            "SELECT id FROM clientes WHERE id = ?", (cliente_id,)
        ).fetchone()
    if not row_cli:
        raise HTTPException(404, "Cliente no encontrado.")

    if not data.items:
        raise HTTPException(400, "El pedido debe tener al menos un ítem")
    if not data.fecha_desde or not data.fecha_hasta:
        raise HTTPException(400, "Elegí la fecha de retiro y de devolución")

    # Horas habilitadas de retiro/devolución (setting `horarios_retiro`).
    from routes.alquileres import _validar_horarios_habilitados
    with get_db() as _conn:
        _validar_horarios_habilitados(_conn, data.fecha_desde, data.fecha_hasta)

    # Reusamos la lógica de creación del back-office para mantener una sola fuente.
    from routes.alquileres import create_pedido, PedidoCreate, PedidoItem

    # SEGURIDAD: el cliente nunca decide el precio. Resolvemos cada
    # `precio_jornada` desde `equipos.precio_jornada` y descartamos lo
    # que vino en el body. Si un equipo no existe en el catálogo,
    # devolvemos 404 (no creamos pedidos con equipos fantasma).
    # (Mismo patrón que `cliente_modificar_pedido` —
    # `_items_payload_to_pedido_items`.)
    with get_db() as conn:
        precios: dict[int, int] = {}
        for it in data.items:
            if it.equipo_id in precios:
                continue
            row = conn.execute(
                "SELECT precio_jornada FROM equipos WHERE id = ?",
                (it.equipo_id,),
            ).fetchone()
            if not row:
                raise HTTPException(404, f"Equipo {it.equipo_id} no encontrado")
            precios[it.equipo_id] = int(row["precio_jornada"] or 0)

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
                precio_jornada=precios[i.equipo_id],
            )
            for i in data.items
        ],
    )
    return create_pedido(payload, background=background)


@router.patch("/api/cliente/pedidos/{id}/cancelar")
def cliente_cancelar_pedido(id: int, request: Request):
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        p = conn.execute(
            "SELECT estado FROM alquileres WHERE id = ? AND cliente_id = ?",
            (id, cliente_id),
        ).fetchone()
        if not p:
            raise HTTPException(404, "Pedido no encontrado")
        if p["estado"] not in ("borrador", "presupuesto"):
            raise HTTPException(400, "Este pedido ya no se puede cancelar")
        conn.execute("UPDATE alquileres SET estado = 'cancelado' WHERE id = ?", (id,))
        # Si había alguna solicitud pendiente, cancelarla también para no
        # dejarla huérfana.
        _cancelar_solicitudes_pendientes(
            conn, id, motivo="El pedido fue cancelado.",
            actor=session.get("email") or "cliente",
        )
        conn.commit()
        return {"ok": True}


# ── Pedidos ───────────────────────────────────────────────────────────────────

@router.get("/api/cliente/pedidos")
def cliente_pedidos(request: Request):
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        pedidos = conn.execute("""
            SELECT id, numero_pedido, estado, fecha_desde, fecha_hasta,
                   monto_total, monto_pagado, descuento_pct, notas, created_at
            FROM alquileres
            WHERE cliente_id = ?
            ORDER BY created_at DESC NULLS LAST, numero_pedido DESC
        """, (cliente_id,)).fetchall()

        from routes.alquileres import _batch_get_alquiler_items
        items_por_pedido = _batch_get_alquiler_items(conn, [p["id"] for p in pedidos])

        result = []
        for p in pedidos:
            d = row_to_dict(p)
            d["items"] = [
                _proyectar(it, _ITEM_CAMPOS_PORTAL)
                for it in items_por_pedido.get(p["id"], [])
            ]

            pagos = conn.execute("""
                SELECT monto, concepto, fecha
                FROM alquiler_pagos
                WHERE pedido_id = ?
                ORDER BY fecha
            """, (p["id"],)).fetchall()
            d["pagos"] = [row_to_dict(pg) for pg in pagos]

            # Solicitudes de modificación que el cliente debe ver — sólo las
            # de aprobación (las `directo` son auditoría interna del autosave
            # en presupuesto, no relevantes para el cliente).
            solic = conn.execute("""
                SELECT id, mensaje, estado, respuesta, resolved_by,
                       resolved_at, created_at
                FROM solicitudes_modificacion
                WHERE pedido_id = ? AND tipo = 'aprobacion'
                ORDER BY created_at DESC
            """, (p["id"],)).fetchall()
            d["solicitudes"] = [row_to_dict(s) for s in solic]

            d["documentos_disponibles"] = _documentos_disponibles(d.get("estado", ""))

            result.append(d)
        return result


@router.get("/api/cliente/pedidos/{id}")
def cliente_pedido_detalle(id: int, request: Request):
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        pedido = conn.execute("""
            SELECT id, numero_pedido, estado, fecha_desde, fecha_hasta,
                   monto_total, monto_pagado, descuento_pct,
                   descuento_jornadas_pct, cliente_id, notas, created_at
            FROM alquileres
            WHERE id = ? AND cliente_id = ?
        """, (id, cliente_id)).fetchone()
        if not pedido:
            raise HTTPException(404, "Pedido no encontrado")

        d = row_to_dict(pedido)

        from routes.alquileres import _get_alquiler_items
        d["items"] = [
            _proyectar(it, _ITEM_CAMPOS_PORTAL) for it in _get_alquiler_items(conn, id)
        ]

        pagos = conn.execute("""
            SELECT monto, concepto, fecha FROM alquiler_pagos
            WHERE pedido_id = ? ORDER BY fecha
        """, (id,)).fetchall()
        d["pagos"] = [row_to_dict(p) for p in pagos]

        solicitudes = conn.execute("""
            SELECT id, mensaje, estado, respuesta, resolved_by,
                   resolved_at, created_at
            FROM solicitudes_modificacion
            WHERE pedido_id = ? AND tipo = 'aprobacion'
            ORDER BY created_at DESC
        """, (id,)).fetchall()
        d["solicitudes"] = [row_to_dict(s) for s in solicitudes]

        d["documentos_disponibles"] = _documentos_disponibles(d.get("estado", ""))

        # Desglose canónico (neto/IVA/total con IVA) vía services/precios.
        # Mismo helper que admin/PDF/carrito → totales coinciden en las 4
        # superficies (#496). El frontend del portal lo lee directo.
        from routes.alquileres import _enriquecer_pedido_con_total
        _enriquecer_pedido_con_total(conn, d)

        return d


# ── Solicitud de modificación ─────────────────────────────────────────────────

class ModificacionItemIn(BaseModel):
    from pydantic import field_validator as _fv
    equipo_id: int
    cantidad:  int

    @_fv("cantidad")
    @classmethod
    def _cantidad_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("cantidad debe ser mayor a 0")
        return v


class ModificacionIn(BaseModel):
    """Cambio que el cliente propone aplicar al pedido.

    Si el pedido está en `presupuesto`, los cambios se aplican directo.
    Si está en `confirmado`, se guarda como propuesta pendiente de aprobación.
    """
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    items:       list[ModificacionItemIn] = Field(..., max_length=100)
    mensaje:     Optional[str] = Field(None, max_length=2000)

    @field_validator("fecha_desde", "fecha_hasta")
    @classmethod
    def _v_fechas(cls, v):
        from routes.alquileres import _validar_fecha_iso
        return _validar_fecha_iso(v)


def _validar_fechas_propuestas(
    fecha_desde: Optional[str], fecha_hasta: Optional[str],
    fallback_desde: Optional[str], fallback_hasta: Optional[str],
) -> None:
    """Valida que las fechas propuestas sean coherentes: futuras y bien ordenadas.

    Usa los valores actuales del pedido como fallback si el cliente no las envía.
    """
    nueva_desde = fecha_desde if fecha_desde is not None else fallback_desde
    nueva_hasta = fecha_hasta if fecha_hasta is not None else fallback_hasta
    if not nueva_desde or not nueva_hasta:
        return  # Pedido sin fechas (caso raro de borrador) — no validamos
    try:
        d0 = to_datetime(nueva_desde)
        d1 = to_datetime(nueva_hasta)
    except ValueError:
        raise HTTPException(400, "Formato de fechas inválido")
    if d0 >= d1:
        raise HTTPException(400, "fecha_hasta debe ser posterior a fecha_desde")
    hoy = now_ar().replace(hour=0, minute=0, second=0, microsecond=0)
    if d0 < hoy:
        raise HTTPException(400, "fecha_desde no puede ser en el pasado")


def _validar_modificacion_estado(estado: str) -> None:
    if estado not in ESTADOS_MODIFICABLES:
        raise HTTPException(
            400,
            f"Este pedido no se puede modificar en estado '{estado}'. "
            "Solo se pueden modificar pedidos en presupuesto o confirmado."
        )


def _validar_ventana_corte(
    conn,
    fecha_desde_actual: Optional[str],
    fecha_desde_propuesta: Optional[str] = None,
) -> int:
    """Valida la ventana de corte para cambios en el pedido.

    Pull-out (empujar `fecha_desde` hacia más adelante) está permitido aún
    dentro de la ventana: el cliente avisa que no necesita el equipo tan
    pronto, lo que descongestiona logística. Pull-in (acercar la fecha) sí
    se bloquea.

    Retorna las horas configuradas (útil para mensajes).
    """
    ventana = _modificacion_ventana_horas(conn)

    if fecha_desde_propuesta and fecha_desde_actual:
        try:
            d_prop = to_datetime(fecha_desde_propuesta)
            d_act = to_datetime(fecha_desde_actual)
            if d_prop >= d_act:
                return ventana  # pull-out: permitido sin chequeo
        except (ValueError, TypeError):
            pass

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


def _check_stock_hipotetico(
    conn, pedido_id: int, fecha_desde: str, fecha_hasta: str,
    items: "list",
) -> list[str]:
    """Pre-chequeo en SECO (dry-run) de stock para un set HIPOTÉTICO de items +
    fechas (la propuesta del cliente que todavía no se guardó).

    Usado en el path `confirmado`/propose: el cliente envía una propuesta y
    queremos rechazarla si no hay stock, sin pasar antes por aplicar nada.

    Delega en el motor único `reservas.validar_stock_hipotetico` — la MISMA pieza
    que usa el gate AUTORITATIVO `validar_stock`, así el dry-run del portal y el
    gate real NO pueden divergir (MEMORIA 2026-05-30 / 2026-05-31). Antes esta
    función re-implementaba la expansión "en seco" importando internos del motor
    (`expandir_demanda`, `parientes_de`, `reservado_total`, ...) y se
    desincronizaba en silencio si el gate cambiaba.
    """
    from reservas import validar_stock_hipotetico
    return validar_stock_hipotetico(conn, pedido_id, fecha_desde, fecha_hasta, items)


def _cancelar_solicitudes_pendientes(
    conn, pedido_id: int, motivo: str, actor: str = "system",
) -> int:
    """Cancela todas las solicitudes pendientes de un pedido. Retorna
    cuántas se cancelaron. Usado cuando el pedido cambia a un estado no
    modificable o se cancela: las solicitudes pendientes quedan huérfanas
    y debemos limpiarlas para no confundir al cliente y al admin.
    """
    rows = conn.execute(
        """UPDATE solicitudes_modificacion
           SET estado = 'cancelada', respuesta = ?,
               resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
           WHERE pedido_id = ? AND estado = 'pendiente'
           RETURNING id""",
        (motivo, actor, pedido_id)
    ).fetchall()
    return len(rows)


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


def _lineas_libres_actuales(conn, pedido_id: int) -> list:
    """Líneas personalizadas (#805, equipo_id NULL) ya guardadas en el pedido,
    como `PedidoItem`. El portal del cliente NO las maneja (solo ítems de
    catálogo) → hay que preservarlas al reaplicar los ítems. Sin esto, el
    DELETE+reinsert de `_apply_pedido_items` las borraría en silencio cuando el
    cliente edita su pedido: un flete/servicio que agregó el admin desaparecería
    y cambiaría el total cobrado (pérdida de plata)."""
    from routes.alquileres import PedidoItem
    rows = conn.execute(
        "SELECT cantidad, precio_jornada, nombre_libre, cobro_modo "
        "FROM alquiler_items WHERE pedido_id=? AND equipo_id IS NULL "
        "ORDER BY orden, id",
        (pedido_id,),
    ).fetchall()
    return [
        PedidoItem(
            equipo_id=None,
            cantidad=r["cantidad"],
            precio_jornada=r["precio_jornada"],
            nombre_libre=r["nombre_libre"],
            cobro_modo=r["cobro_modo"],
        )
        for r in rows
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
    from reservas import validar_stock as _check_stock
    from routes.alquileres import (
        PedidoDatos, _apply_pedido_datos, _apply_pedido_items,
        _get_alquiler_detail,
    )

    session = require_cliente(request)
    cliente_id = session["cliente_id"]

    if not data.items:
        raise HTTPException(400, "El pedido debe tener al menos un ítem")

    with get_db() as conn:
        try:
            pedido = conn.execute(
                "SELECT * FROM alquileres WHERE id = ? AND cliente_id = ?",
                (id, cliente_id)
            ).fetchone()
            if not pedido:
                raise HTTPException(404, "Pedido no encontrado")

            _validar_modificacion_estado(pedido["estado"])
            _validar_ventana_corte(conn, pedido["fecha_desde"], data.fecha_desde)
            _check_solicitud_pendiente(conn, id)
            _validar_fechas_propuestas(
                data.fecha_desde, data.fecha_hasta,
                pedido["fecha_desde"], pedido["fecha_hasta"],
            )
            # Horarios habilitados: solo si el cliente propone fechas nuevas (no
            # bloqueamos ediciones de solo-items aunque el admin haya cambiado los
            # horarios después de creado el pedido).
            if data.fecha_desde is not None or data.fecha_hasta is not None:
                from routes.alquileres import _validar_horarios_habilitados
                _validar_horarios_habilitados(
                    conn,
                    data.fecha_desde if data.fecha_desde is not None else pedido["fecha_desde"],
                    data.fecha_hasta if data.fecha_hasta is not None else pedido["fecha_hasta"],
                )

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

                # Preservar las líneas personalizadas (#805): el portal solo manda
                # ítems de catálogo; sin esto el reinsert las borraría.
                pedido_items = _items_payload_to_pedido_items(data.items, precios)
                pedido_items += _lineas_libres_actuales(conn, id)
                _apply_pedido_items(conn, id, pedido_items)

                # Re-validar stock con el rango nuevo
                p2 = conn.execute("SELECT fecha_desde, fecha_hasta FROM alquileres WHERE id=?", (id,)).fetchone()
                if p2["fecha_desde"] and p2["fecha_hasta"]:
                    problemas = _check_stock(conn, id, p2["fecha_desde"], p2["fecha_hasta"])
                    if problemas:
                        raise HTTPException(409, "Sin stock: " + "; ".join(problemas))

                # Auditoría: dedup. Si hay un row `directo` reciente para este
                # pedido (≤ 5 min), lo actualizamos en lugar de insertar uno
                # nuevo — sino el autosave llena la tabla con N rows por sesión.
                actor = session.get("email") or "cliente"
                reciente = conn.execute(
                    """SELECT id FROM solicitudes_modificacion
                       WHERE pedido_id = ? AND cliente_id = ? AND tipo = 'directo'
                         AND resolved_at >= CURRENT_TIMESTAMP - INTERVAL '5 minutes'
                       ORDER BY resolved_at DESC LIMIT 1""",
                    (id, cliente_id)
                ).fetchone()
                cambios_str = json.dumps(data.model_dump())
                if reciente:
                    conn.execute(
                        """UPDATE solicitudes_modificacion
                           SET mensaje = ?, cambios_json = ?,
                               resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
                           WHERE id = ?""",
                        (data.mensaje, cambios_str, actor, reciente["id"])
                    )
                else:
                    conn.execute(
                        """INSERT INTO solicitudes_modificacion
                           (pedido_id, cliente_id, mensaje, cambios_json, tipo, estado, resolved_at, resolved_by)
                           VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP,?)""",
                        (id, cliente_id, data.mensaje, cambios_str,
                         "directo", "aprobada", actor)
                    )
                conn.commit()

                pedido_actualizado = _get_alquiler_detail(conn, id)
                return {"ok": True, "tipo": "directo", "pedido": pedido_actualizado}

            # ── Caso `confirmado`: guardar propuesta ─────────────────────────
            # Validar stock hipotéticamente: rechazar antes de que el admin la vea
            # si la propuesta es imposible. Las fechas a chequear son las que el
            # cliente propone, con fallback a las actuales del pedido.
            fd = data.fecha_desde or pedido["fecha_desde"]
            fh = data.fecha_hasta or pedido["fecha_hasta"]
            problemas = _check_stock_hipotetico(conn, id, fd, fh, data.items)
            if problemas:
                raise HTTPException(409, "Sin stock para tu propuesta: " + "; ".join(problemas))

            try:
                conn.execute(
                    """INSERT INTO solicitudes_modificacion
                       (pedido_id, cliente_id, mensaje, cambios_json, tipo, estado)
                       VALUES (?,?,?,?,?,'pendiente')""",
                    (id, cliente_id, data.mensaje, json.dumps(data.model_dump()),
                     "aprobacion")
                )
                conn.commit()
            except Exception as e:
                # Si el partial unique index agarra una race con otra pestaña del
                # mismo cliente, devolvemos 409 igual que el pre-check optimista.
                # Re-mapeamos para que la respuesta sea consistente.
                msg = str(e).lower()
                if "uniq_solicitud_pendiente_por_pedido" in msg or "unique" in msg:
                    raise HTTPException(409, "Ya hay una solicitud pendiente para este pedido")
                raise

            background.add_task(_enviar_email_solicitud_admin, id, data.model_dump())

            return {"ok": True, "tipo": "aprobacion"}
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            logger.error("Error en modificación cliente pedido %s", id, exc_info=True)
            conn.rollback()
            raise


@router.delete("/api/cliente/pedidos/{id}/modificacion/{sm_id}")
def cliente_cancelar_solicitud(
    id: int, sm_id: int, request: Request, background: BackgroundTasks,
):
    """El cliente cancela su propia solicitud pendiente."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        # Lock + filtro atómico: si dos pestañas cancelan a la vez, sólo
        # una ve `estado='pendiente'`.
        sm = conn.execute(
            """SELECT sm.id, sm.estado, sm.pedido_id,
                      a.numero_pedido, c.nombre AS cliente_nombre,
                      c.email AS cliente_email
               FROM solicitudes_modificacion sm
               JOIN alquileres a ON a.id = sm.pedido_id
               JOIN clientes c ON c.id = sm.cliente_id
               WHERE sm.id = ? AND sm.pedido_id = ? AND sm.cliente_id = ?
               FOR UPDATE OF sm""",
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

        # Notificar al admin para cerrar el loop (no propaga si falla).
        background.add_task(
            _enviar_email_cancelacion_admin,
            sm["pedido_id"], sm["numero_pedido"],
            sm["cliente_nombre"], sm["cliente_email"],
        )
        return {"ok": True}


def _enviar_email_cancelacion_admin(
    pedido_id: int, numero_pedido, cliente_nombre: str, cliente_email: str,
) -> None:
    """Background task: notifica al admin que el cliente canceló su solicitud."""
    from config import SITE_URL
    from services.email import send_email
    from services.email.service import get_admin_to
    admin_to = get_admin_to()
    if not admin_to:
        return
    ctx = {
        "cliente_nombre": cliente_nombre or "",
        "cliente_email":  cliente_email or "",
        "numero_pedido":  numero_pedido or pedido_id,
        "admin_url":      f"{SITE_URL}/admin/pedidos/{pedido_id}",
    }
    send_email("modificacion_cancelada_admin", admin_to, ctx, pedido_id)


@router.get("/api/cliente/pedidos/{id}/disponibilidad")
def cliente_disponibilidad(
    id: int, request: Request, fecha_desde: str, fecha_hasta: str,
):
    """Wrapper de /api/disponibilidad con validación de ownership y
    `exclude_pedido_id` automático."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        owned = conn.execute(
            "SELECT id FROM alquileres WHERE id = ? AND cliente_id = ?",
            (id, cliente_id)
        ).fetchone()
        if not owned:
            raise HTTPException(404, "Pedido no encontrado")
    from routes.alquileres import get_disponibilidad
    return get_disponibilidad(
        fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, exclude_pedido_id=id,
    )


@router.get("/api/cliente/modificacion-config")
def cliente_modificacion_config(request: Request):
    """Devuelve la ventana de corte para que el frontend pueda mostrar/ocultar
    el botón de modificar sin tener que tocar settings."""
    require_cliente(request)
    with get_db() as conn:
        return {"ventana_horas": _modificacion_ventana_horas(conn)}


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
    from config import SITE_URL
    from services.email import send_email
    from services.email.service import get_admin_to
    from routes.alquileres import _get_alquiler_detail

    admin_to = get_admin_to()
    if not admin_to:
        return

    with get_db() as conn:
        try:
            pedido = _get_alquiler_detail(conn, pedido_id)
        except Exception:
            return

    ctx = {
        "cliente_nombre":  pedido.get("cliente_nombre") or "",
        "cliente_email":   pedido.get("cliente_email") or "",
        "numero_pedido":   pedido.get("numero_pedido") or pedido_id,
        "admin_url":       f"{SITE_URL}/admin/pedidos/{pedido_id}",
        **_build_diff_payload(pedido, cambios),
    }
    send_email("modificacion_solicitada_admin", admin_to, ctx, pedido_id)


def _enviar_email_resolucion_cliente(
    pedido_id: int, cliente_email: str, cliente_nombre: str,
    numero_pedido, estado: str, respuesta: str,
) -> None:
    """Background task: notifica al cliente cuando se resuelve su solicitud."""
    from config import SITE_URL
    from services.email import send_email
    estado_label = "aprobada" if estado == "aprobada" else "rechazada"
    ctx = {
        "cliente_nombre": cliente_nombre or "",
        "numero_pedido":  numero_pedido or pedido_id,
        "estado":         estado,
        "estado_label":   estado_label,
        "respuesta":      respuesta or "",
        "portal_url":     f"{SITE_URL}/cliente/portal",
    }
    send_email("modificacion_resuelta_cliente", cliente_email, ctx, pedido_id)


# ── Admin: ver solicitudes y resolverlas ─────────────────────────────────────

@router.get("/api/admin/solicitudes")
def admin_solicitudes(request: Request):
    """Lista de solicitudes de modificación (solo admins)."""
    require_admin(request)
    with get_db() as conn:
        rows = conn.execute("""
            SELECT sm.id, sm.pedido_id, sm.mensaje, sm.estado, sm.respuesta,
                   sm.cambios_json, sm.cambios_aplicados, sm.tipo,
                   sm.resolved_at, sm.resolved_by, sm.created_at,
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


class SolicitudOverrideItem(BaseModel):
    from pydantic import field_validator as _fv
    equipo_id: int
    cantidad:  int

    @_fv("cantidad")
    @classmethod
    def _cantidad_positiva(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("cantidad debe ser mayor a 0 (para quitar un equipo, omitilo del array)")
        return v


class SolicitudOverride(BaseModel):
    """Contrapropuesta del admin. Si se envía al aprobar, se aplica en lugar
    de la propuesta original del cliente."""
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    items:       list[SolicitudOverrideItem] = Field(..., max_length=100)


class SolicitudRespuesta(BaseModel):
    estado: str     # aprobada / rechazada
    respuesta: str = Field("", max_length=2000)
    cambios_override: Optional[SolicitudOverride] = None


@router.patch("/api/admin/solicitudes/{id}")
def admin_responder_solicitud(
    id: int, data: SolicitudRespuesta, request: Request, background: BackgroundTasks,
):
    """Resuelve una solicitud de modificación.

    - Si `estado='aprobada'` y la solicitud tiene `cambios_json` (`tipo='aprobacion'`),
      aplica los cambios al pedido reusando los helpers de `routes/alquileres`.
    - Si `estado='rechazada'`, sólo marca y notifica.
    """
    from reservas import validar_stock as _check_stock
    from routes.alquileres import (
        PedidoDatos, _apply_pedido_datos, _apply_pedido_items,
    )

    admin = require_admin(request)
    admin_email = admin.get("email") or "admin"
    if data.estado not in ("aprobada", "rechazada"):
        raise HTTPException(400, "Estado debe ser 'aprobada' o 'rechazada'")

    with get_db() as conn:
        try:
            # Lock pesimista de la fila para evitar que dos admins (o admin +
            # cancelación del cliente) corran en paralelo sobre la misma
            # solicitud y ambos pasen el check de "pendiente".
            sm = conn.execute(
                """SELECT sm.*, a.cliente_id, a.fecha_desde, a.fecha_hasta,
                          a.estado AS pedido_estado, a.numero_pedido,
                          c.email AS cliente_email, c.nombre AS cliente_nombre
                   FROM solicitudes_modificacion sm
                   JOIN alquileres a ON a.id = sm.pedido_id
                   JOIN clientes c ON c.id = sm.cliente_id
                   WHERE sm.id = ?
                   FOR UPDATE OF sm""",
                (id,)
            ).fetchone()
            if not sm:
                raise HTTPException(404, "Solicitud no encontrada")
            if sm["estado"] != "pendiente":
                raise HTTPException(400, "Esta solicitud ya fue resuelta")

            cambios_aplicados_str: Optional[str] = None

            if data.estado == "aprobada" and sm["tipo"] == "aprobacion":
                if sm["pedido_estado"] not in ESTADOS_MODIFICABLES:
                    raise HTTPException(
                        400, f"El pedido está en estado '{sm['pedido_estado']}' y ya no admite cambios"
                    )

                cambios_pre = sm["cambios_json"] or {}
                if isinstance(cambios_pre, str):
                    cambios_pre = json.loads(cambios_pre)

                # Contrapropuesta del admin: si se envió, sobreescribe la del cliente.
                if data.cambios_override is not None:
                    cambios = data.cambios_override.model_dump()
                    if not cambios.get("items"):
                        raise HTTPException(400, "La contrapropuesta debe incluir items")
                    _validar_fechas_propuestas(
                        cambios.get("fecha_desde"), cambios.get("fecha_hasta"),
                        sm["fecha_desde"], sm["fecha_hasta"],
                    )
                else:
                    cambios = cambios_pre

                _validar_ventana_corte(
                    conn, sm["fecha_desde"], cambios.get("fecha_desde"),
                )

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

                # Preservar las líneas personalizadas (#805) — ver nota en el caso directo.
                pedido_items = _items_payload_to_pedido_items(
                    [ModificacionItemIn(**it) for it in cambios.get("items") or []],
                    precios,
                )
                pedido_items += _lineas_libres_actuales(conn, sm["pedido_id"])
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

                # Snapshot de lo que efectivamente se aplicó (≠ a la propuesta del
                # cliente si admin usó override). Para auditoría.
                cambios_aplicados_str = json.dumps(cambios)

            conn.execute(
                """UPDATE solicitudes_modificacion
                   SET estado = ?, respuesta = ?, cambios_aplicados = ?,
                       resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
                   WHERE id = ?""",
                (data.estado, data.respuesta, cambios_aplicados_str, admin_email, id)
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

    from routes.alquileres import _get_alquiler_items
    pedido["items"] = [
        {
            **_proyectar(it, _ITEM_CAMPOS_DOC),
            "componentes": [_proyectar(c, _COMP_CAMPOS_DOC) for c in it["componentes"]],
        }
        for it in _get_alquiler_items(conn, pedido_id)
    ]

    # Datos del cliente para el contrato + Factura A si aplica.
    # Nombre y dirección: preferir datos RENAPER si la identidad fue verificada.
    cli = conn.execute(
        """SELECT nombre, apellido, email, telefono, direccion, cuit,
                  perfil_impuestos, razon_social, domicilio_fiscal,
                  email_facturacion,
                  dni, nombre_renaper, apellido_renaper, direccion_renaper
           FROM clientes WHERE id = ?""",
        (cliente_id,),
    ).fetchone()
    if cli:
        c = row_to_dict(cli)
        if c.get("nombre_renaper"):
            pedido["cliente_nombre"] = f"{c['nombre_renaper']} {c.get('apellido_renaper', '')}".strip()
        else:
            pedido["cliente_nombre"] = f"{c.get('nombre', '')} {c.get('apellido', '')}".strip()
        pedido["cliente_email"] = c.get("email")
        pedido["cliente_telefono"] = c.get("telefono")
        pedido["cliente_direccion"] = c.get("direccion_renaper") or c.get("direccion")
        pedido["cliente_cuit"] = c.get("cuit")
        pedido["cliente_dni"] = c.get("dni")
        pedido["cliente_perfil_impuestos"] = c.get("perfil_impuestos")
        pedido["cliente_razon_social"] = c.get("razon_social")
        pedido["cliente_domicilio_fiscal"] = c.get("domicilio_fiscal")
        pedido["cliente_email_facturacion"] = c.get("email_facturacion")

    # Desglose canónico (bruto/descuento/neto/IVA) — misma fuente de verdad
    # que el admin: el PDF sólo pinta lo que devuelve `calcular_total`.
    from routes.alquileres import _enriquecer_pedido_con_total
    _enriquecer_pedido_con_total(conn, pedido)

    return pedido


# Los documentos se generan al vuelo y deben reflejar siempre el estado actual
# del pedido. Sin esto el navegador cachea la URL estática y sirve un PDF viejo
# tras editar el pedido (mismo criterio que `_DOC_NO_CACHE` en alquileres.py).
_DOC_NO_CACHE = {"Cache-Control": "no-store, max-age=0"}

# El preview HTML se muestra dentro de un <iframe> del portal (mismo origen). El
# middleware global pone X-Frame-Options: DENY, que bloquea TODO embedding —
# incluido el propio — y deja el preview en blanco. SAMEORIGIN permite que el
# portal embeba su propio documento sin abrir framing a terceros.
_DOC_PREVIEW_HEADERS = {**_DOC_NO_CACHE, "X-Frame-Options": "SAMEORIGIN"}


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"', **_DOC_NO_CACHE},
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
        return HTMLResponse(content=html_str, headers=_DOC_PREVIEW_HEADERS)
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
        headers={"Content-Disposition": f'inline; filename="{pdf_filename}"', **_DOC_NO_CACHE},
    )


@router.get("/api/cliente/pedidos/{id}/remito.pdf")
@router.get("/api/cliente/pedidos/{id}/remito")
async def cliente_pedido_remito(id: int, request: Request, format: str = "pdf"):
    """Remito del pedido. format=pdf (default, download) o html (preview)."""
    session = require_cliente(request)
    with get_db() as conn:
        pedido = _load_pedido_para_pdf(conn, id, session["cliente_id"])
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
    with get_db() as conn:
        pedido = _load_pedido_para_pdf(conn, id, session["cliente_id"])
    if not _documentos_disponibles(pedido.get("estado", ""))["contrato"]:
        raise HTTPException(403, "El contrato estará disponible cuando confirmemos el pedido.")
    return await _doc_response_or_pdf(
        _contrato_html(pedido), _pedido_filename(pedido, doc="contrato"), format
    )


@router.get("/api/cliente/pedidos/{id}/albaran.pdf")
@router.get("/api/cliente/pedidos/{id}/albaran")
async def cliente_pedido_albaran(id: int, request: Request, format: str = "pdf"):
    """Albarán del pedido. format=pdf (default) o html (preview)."""
    session = require_cliente(request)
    with get_db() as conn:
        pedido = _load_pedido_para_pdf(conn, id, session["cliente_id"])
    if not _documentos_disponibles(pedido.get("estado", ""))["albaran"]:
        raise HTTPException(403, "El albarán estará disponible al momento de la entrega.")
    return await _doc_response_or_pdf(
        _albaran_html(pedido), _pedido_filename(pedido, doc="albaran"), format
    )


# ── Favoritos del cliente ──────────────────────────────────────────────────────


@router.get("/api/cliente/favoritos")
def get_favoritos(request: Request):
    """Lista de equipo_ids marcados como favoritos por el cliente."""
    session = require_cliente(request)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT equipo_id FROM cliente_favoritos WHERE cliente_id = %s",
            (session["cliente_id"],),
        ).fetchall()
        return [str(r["equipo_id"]) for r in rows]


class FavSync(BaseModel):
    ids: list[int]


@router.post("/api/cliente/favoritos/sync")
def sync_favoritos(data: FavSync, request: Request):
    """Merge de favoritos de localStorage al servidor al hacer login. No borra nada."""
    session = require_cliente(request)
    if not data.ids:
        return {"synced": 0}
    with get_db() as conn:
        count = 0
        for eid in data.ids[:200]:  # cap de seguridad
            eq = conn.execute(
                "SELECT id FROM equipos WHERE id = %s", (eid,)
            ).fetchone()
            if not eq:
                continue
            conn.execute(
                "INSERT INTO cliente_favoritos (cliente_id, equipo_id) VALUES (%s, %s)"
                " ON CONFLICT (cliente_id, equipo_id) DO NOTHING",
                (session["cliente_id"], eid),
            )
            count += 1
        conn.commit()
        return {"synced": count}


@router.post("/api/cliente/favoritos/{equipo_id}", status_code=201)
def add_favorito(equipo_id: int, request: Request):
    """Agrega un equipo a los favoritos del cliente."""
    session = require_cliente(request)
    with get_db() as conn:
        eq = conn.execute(
            "SELECT id FROM equipos WHERE id = %s", (equipo_id,)
        ).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no encontrado")
        conn.execute(
            "INSERT INTO cliente_favoritos (cliente_id, equipo_id) VALUES (%s, %s)"
            " ON CONFLICT (cliente_id, equipo_id) DO NOTHING",
            (session["cliente_id"], equipo_id),
        )
        conn.commit()
        return {"ok": True}


@router.delete("/api/cliente/favoritos/{equipo_id}")
def remove_favorito(equipo_id: int, request: Request):
    """Quita un equipo de los favoritos del cliente."""
    session = require_cliente(request)
    with get_db() as conn:
        conn.execute(
            "DELETE FROM cliente_favoritos WHERE cliente_id = %s AND equipo_id = %s",
            (session["cliente_id"], equipo_id),
        )
        conn.commit()
        return {"ok": True}
