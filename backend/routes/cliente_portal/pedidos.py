"""Ciclo del pedido del cliente (#501 — extraído del god-module `routes/cliente_portal.py`).

Crear / cancelar pedido + listar / ver detalle de los pedidos del cliente logueado.
Registra sus rutas en el router compartido del paquete `routes.cliente_portal`. Los
helpers compartidos (`require_cliente`, `_proyectar`, `_documentos_disponibles`) viven
en `core`; `_cancelar_solicitudes_pendientes` (cancelar solicitudes pendientes al
cancelar el pedido) vive en `solicitudes`.
"""
from typing import Optional

from fastapi import Request, HTTPException, BackgroundTasks
from pydantic import BaseModel, field_validator

from database import get_db, row_to_dict
from routes.cliente_portal.core import (
    router,
    require_cliente,
    require_cliente_verificado,
    _proyectar,
    _documentos_disponibles,
    _ITEM_CAMPOS_PORTAL,
)
from routes.cliente_portal.solicitudes import _cancelar_solicitudes_pendientes


# ── Crear / cancelar pedido ───────────────────────────────────────────────────

class CartItemIn(BaseModel):
    equipo_id:      int
    cantidad:       int
    # `precio_jornada` se acepta por compatibilidad con clientes ya
    # cacheados, pero el server lo IGNORA y resuelve el precio desde
    # `equipos.precio_jornada`. El cliente nunca decide el precio
    # (ver `cliente_crear_pedido`).
    precio_jornada: int = 0

    @field_validator("cantidad")
    @classmethod
    def _v_cantidad(cls, v: int) -> int:
        # Espejo de `PedidoItem.validate_cantidad` (routes/alquileres/core.py).
        # Acá la validación vive en el PARSE → 422 limpio; sin esto, una cantidad
        # inválida explotaba recién al construir `PedidoItem` adentro del handler → 500.
        if v is None or v < 1:
            raise ValueError("cantidad debe ser >= 1")
        if v > 999:
            raise ValueError("cantidad demasiado alta (máx 999)")
        return v


class PedidoClienteCreate(BaseModel):
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    notas:       Optional[str] = None
    items:       list[CartItemIn] = []
    # session_id del carrito (#280 Fase 1): si viene, marcamos el carrito como
    # confirmado en carritos_activos para cerrar el funnel de conversión.
    session_id:  Optional[str] = None

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
    session = require_cliente_verificado(request)
    cliente_id = session["cliente_id"]

    if not data.items:
        raise HTTPException(400, "El pedido debe tener al menos un ítem")
    if not data.fecha_desde or not data.fecha_hasta:
        raise HTTPException(400, "Elegí la fecha de retiro y de devolución")

    # Caps espejo de la UI (el cliente las tiene en el front; la API no las
    # validaba → defensa en profundidad). El rango de 120 días es límite del
    # cliente, NO del admin, por eso vive acá y no en `create_pedido`.
    if data.notas and len(data.notas) > 500:
        raise HTTPException(400, "Las notas no pueden superar los 500 caracteres")
    from datetime import datetime as _dt
    if (_dt.fromisoformat(data.fecha_hasta) - _dt.fromisoformat(data.fecha_desde)).days > 120:
        raise HTTPException(400, "El rango del alquiler no puede superar los 120 días")

    # Horas habilitadas de retiro/devolución (setting `horarios_retiro`).
    from routes.alquileres import _validar_horarios_habilitados
    with get_db() as _conn:
        _validar_horarios_habilitados(_conn, data.fecha_desde, data.fecha_hasta)

    # Reusamos la lógica de creación del back-office para mantener una sola fuente.
    from routes.alquileres import create_pedido_retry, PedidoCreate, PedidoItem

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
            # Sólo equipos del catálogo público y con precio: sin el gate de
            # `visible_catalogo`, un cliente podía reservar por API un equipo
            # oculto/interno (o sin precio) enumerando ids → pedido $0.
            row = conn.execute(
                "SELECT precio_jornada FROM equipos "
                "WHERE id = ? AND visible_catalogo = 1 AND precio_jornada IS NOT NULL",
                (it.equipo_id,),
            ).fetchone()
            if not row:
                raise HTTPException(404, f"Equipo {it.equipo_id} no encontrado en el catálogo")
            precios[it.equipo_id] = int(row["precio_jornada"])

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
    # `create_pedido_retry` reintenta ante deadlock de concurrencia (→ 503 si
    # persiste, nunca 500). Ver helper en `routes/alquileres/core.py`.
    resultado = create_pedido_retry(payload, background=background)

    # Cerrar el funnel de conversión (#280 Fase 1): marcar el carrito como
    # confirmado para que desaparezca del dashboard de carritos activos.
    if data.session_id:
        try:
            from routes.carritos import marcar_confirmado
            with get_db() as conn:
                marcar_confirmado(data.session_id, conn)
                conn.commit()
        except Exception:
            pass  # No crítico — el pedido ya se creó

    return resultado


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


