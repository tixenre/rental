"""Endpoints HTTP de pedidos (#501 — extraído del god-module `routes/alquileres.py`).

Capa de transporte del ciclo de vida del pedido: alta (admin), listado, detalle,
baja, transición de estado y edición de datos/ítems. La lógica reusable
(`create_pedido`, `_apply_pedido_*`, enriquecimiento, recálculo de total) vive en
`core` y se importa; acá quedan solo los handlers que registran sus rutas sobre el
router compartido del paquete `routes.alquileres`.
"""
import logging
from typing import Optional

from fastapi import Request, HTTPException, Query, BackgroundTasks

from database import get_db, row_to_dict, to_datetime
from admin_guard import require_admin
from services.email import send_email
from reservas import validar_stock as _check_stock
from routes.alquileres.core import (
    router,
    ESTADOS_VALIDOS,
    PedidoCreate,
    PedidoEstado,
    PedidoDatos,
    PedidoItemUpdate,
    create_pedido,
    _es_historico,
    _maybe_finalizar,
    _next_numero_pedido,
    _get_alquiler_detail,
    _batch_get_alquiler_items,
    _enriquecer_pedidos_con_cliente,
    _pedido_email_context,
    _ics_adjunto_pedido,
    _apply_pedido_datos,
    _apply_pedido_items,
)

logger = logging.getLogger(__name__)


SORT_COLS = {
    "numero":  "p.numero_pedido",
    "cliente": "p.cliente_nombre",
    "monto":   "p.monto_total",
    "fecha":   "p.fecha_desde",
    "estado":  "p.estado",
}

ESTADOS_REQUIEREN_FECHAS = {"confirmado", "retirado", "devuelto", "finalizado"}


# Estados que reservan stock activamente — cualquier transición HACIA uno de
# estos requiere re-validar stock incluso si el destino no exige fechas/items
# (caso típico: borrador → presupuesto).
ESTADOS_QUE_RESERVAN = {"presupuesto", "confirmado", "retirado"}


@router.post("/alquileres", status_code=201)
def create_pedido_endpoint(data: PedidoCreate, request: Request, background: BackgroundTasks):
    """Endpoint admin para crear pedido. La lógica está en `create_pedido`,
    así el portal cliente (cliente_portal.py) la reutiliza sin pasar por admin guard."""
    require_admin(request)
    return create_pedido(data, background=background, es_admin=True)


@router.get("/alquileres")
def list_pedidos(
    request: Request,
    estado:   Optional[str] = Query(None),
    fuente:   Optional[str] = Query(None),
    q:        Optional[str] = Query(None),
    con_saldo: Optional[bool] = Query(None, description="Si true, solo pedidos con saldo pendiente (monto_pagado < monto_total)"),
    page:     int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    sort_by:  Optional[str] = Query(None),
    sort_dir: Optional[str] = Query("desc"),
):
    require_admin(request)
    offset = (page - 1) * per_page
    params: list = []
    where  = "WHERE 1=1"

    with get_db() as conn:
        if estado:
            where += " AND p.estado = ?"
            params.append(estado)
        if fuente:
            where += " AND p.fuente = ?"
            params.append(fuente)
        if q:
            like = f"%{q}%"
            # Busca por la foto del pedido Y por el nombre ACTUAL del cliente
            # (el contacto se muestra en vivo → buscar por el dato corregido
            # también tiene que encontrar el pedido).
            where += (
                " AND (p.cliente_nombre LIKE ? OR CAST(p.numero_pedido AS TEXT) LIKE ?"
                " OR EXISTS (SELECT 1 FROM clientes c WHERE c.id = p.cliente_id"
                " AND (c.nombre LIKE ? OR c.apellido LIKE ?)))"
            )
            params += [like, like, like, like]
        if con_saldo:
            # Pedidos con saldo > 0 y no cancelados. Borrador y presupuesto no
            # aplican porque todavía no se cobra; cancelado tampoco.
            where += " AND (COALESCE(p.monto_pagado, 0) < COALESCE(p.monto_total, 0))"
            where += " AND p.estado IN ('confirmado','retirado','devuelto','finalizado')"

        col = SORT_COLS.get(sort_by, "p.numero_pedido")
        direction = "ASC" if sort_dir == "asc" else "DESC"
        # Poner "Registro manual" (sin número de pedido) al final.
        has_numero = "(p.numero_pedido IS NOT NULL)"
        order = f"{has_numero} DESC, {col} {direction} NULLS LAST"
        # secundario: número descendente para desempate
        if col != "p.numero_pedido":
            order += ", p.numero_pedido DESC NULLS LAST"

        total = conn.execute(f"SELECT COUNT(*) FROM alquileres p {where}", params).fetchone()[0]
        rows  = conn.execute(
            f"SELECT p.* FROM alquileres p {where} ORDER BY {order} LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()

        pedidos    = [row_to_dict(r) for r in rows]
        _enriquecer_pedidos_con_cliente(conn, pedidos)
        items_map  = _batch_get_alquiler_items(conn, [p["id"] for p in pedidos])

        # Pedidos con solicitud de modificación pendiente — para badge en UI.
        pedido_ids = [p["id"] for p in pedidos]
        pendientes: set[int] = set()
        if pedido_ids:
            ph = ",".join(["?"] * len(pedido_ids))
            for r in conn.execute(
                f"""SELECT DISTINCT pedido_id FROM solicitudes_modificacion
                    WHERE estado = 'pendiente' AND pedido_id IN ({ph})""",
                pedido_ids,
            ).fetchall():
                pendientes.add(r["pedido_id"])

        for p in pedidos:
            p["items"] = items_map.get(p["id"], [])
            p["tiene_solicitud_pendiente"] = p["id"] in pendientes

        return {"total": total, "page": page, "per_page": per_page, "items": pedidos}


@router.get("/alquileres/{id}")
def get_pedido(id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        pedido = _get_alquiler_detail(conn, id)
    return pedido


@router.delete("/alquileres/{id}", status_code=204)
def delete_pedido(id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            if not conn.execute("SELECT id FROM alquileres WHERE id=?", (id,)).fetchone():
                raise HTTPException(404, "Pedido no encontrado")
            # Borrar ítems, pagos e historicos asociados (FK cascade si está activada, pero por las dudas)
            conn.execute("DELETE FROM alquiler_items  WHERE pedido_id=?", (id,))
            conn.execute("DELETE FROM alquiler_pagos  WHERE pedido_id=?", (id,))
            conn.execute("DELETE FROM alquileres       WHERE id=?",        (id,))
            conn.commit()
        except Exception:
            logger.error("Error eliminando pedido %s", id, exc_info=True)
            conn.rollback()
            raise


@router.patch("/alquileres/{id}")
def update_pedido(id: int, data: PedidoEstado, request: Request, background: BackgroundTasks):
    require_admin(request)
    if data.estado not in ESTADOS_VALIDOS:
        raise HTTPException(400, f"Estado inválido. Usar: {', '.join(sorted(ESTADOS_VALIDOS))}")

    with get_db() as conn:
        try:
            p_row = conn.execute("SELECT * FROM alquileres WHERE id=?", (id,)).fetchone()
            if not p_row:
                raise HTTPException(404, "Pedido no encontrado")

            # ── Validaciones para estados que requieren fechas y stock ──────────────
            if data.estado in ESTADOS_REQUIEREN_FECHAS and not _es_historico(p_row["fuente"]):
                errores = []
                if not p_row["fecha_desde"] or not p_row["fecha_hasta"]:
                    errores.append("El pedido no tiene fechas de inicio y fin.")
                else:
                    try:
                        d0 = to_datetime(p_row["fecha_desde"])
                        d1 = to_datetime(p_row["fecha_hasta"])

                        if d0 >= d1:
                            errores.append("fecha_hasta debe ser posterior a fecha_desde")
                        # Endpoint admin-only (require_admin arriba): el admin puede
                        # avanzar pedidos con fecha de retiro pasada (carga
                        # retroactiva), así que no se rechaza el pasado acá.
                    except ValueError:
                        errores.append("Las fechas tienen formato inválido")

                if not conn.execute(
                    "SELECT 1 FROM alquiler_items WHERE pedido_id=?", (id,)
                ).fetchone():
                    errores.append("El pedido no tiene equipos cargados.")
                if p_row["fecha_desde"] and p_row["fecha_hasta"] and not errores:
                    sin_stock = _check_stock(conn, id, p_row["fecha_desde"], p_row["fecha_hasta"])
                    for s in sin_stock:
                        errores.append(f"Sin stock suficiente: {s}")
                if errores:
                    raise HTTPException(422, {"errores": errores})

            # Cualquier transición a un estado que reserva stock debe re-validar,
            # incluyendo "presupuesto" (que no exige fechas pero sí reserva si las
            # tiene). Salteamos si la transición no cambia el flag de "reserva"
            # (ej. confirmado → confirmado, o presupuesto → confirmado ya validado
            # arriba).
            elif (
                data.estado in ESTADOS_QUE_RESERVAN
                and p_row["estado"] not in ESTADOS_QUE_RESERVAN
                and not _es_historico(p_row["fuente"])
                and p_row["fecha_desde"] and p_row["fecha_hasta"]
            ):
                sin_stock = _check_stock(conn, id, p_row["fecha_desde"], p_row["fecha_hasta"])
                if sin_stock:
                    raise HTTPException(
                        422,
                        {"errores": [f"Sin stock suficiente: {s}" for s in sin_stock]},
                    )

            es_historico    = _es_historico(p_row["fuente"])
            estado_anterior = p_row["estado"]
            updates         = {"estado": data.estado}

            if data.estado == "confirmado" and not p_row["numero_pedido"]:
                next_n = _next_numero_pedido(conn)
                updates["numero_pedido"] = next_n

            set_clause = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE alquileres SET {set_clause} WHERE id=?", (*updates.values(), id))

            # Si el pedido se va a un estado fuera de los modificables, las
            # solicitudes pendientes quedan huérfanas. Las cancelamos en la
            # misma transacción para no confundir al cliente ni al admin.
            # Import diferido para evitar ciclo con cliente_portal.
            from routes.cliente_portal import (
                ESTADOS_MODIFICABLES, _cancelar_solicitudes_pendientes,
            )
            if data.estado not in ESTADOS_MODIFICABLES:
                _cancelar_solicitudes_pendientes(
                    conn, id,
                    motivo=f"El pedido pasó a estado '{data.estado}'.",
                    actor="system",
                )

            _maybe_finalizar(conn, id)
            conn.commit()

            pedido = _get_alquiler_detail(conn, id)
        except Exception:
            logger.error("Error actualizando estado del pedido %s", id, exc_info=True)
            conn.rollback()
            raise

    # Notif al cliente cuando pasamos a 'confirmado' (solo si veníamos de
    # otro estado — no re-mandamos si ya estaba confirmado).
    if (
        pedido
        and data.estado == "confirmado"
        and estado_anterior != "confirmado"
        and pedido.get("cliente_email")
    ):
        ctx = _pedido_email_context(pedido)
        background.add_task(
            send_email, "pedido_confirmado_cliente",
            pedido["cliente_email"], ctx, pedido.get("id"),
            attachments=_ics_adjunto_pedido(pedido),
        )
    return pedido


@router.patch("/alquileres/{id}/datos")
def update_pedido_datos(id: int, data: PedidoDatos, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            pedido = _apply_pedido_datos(conn, id, data, es_admin=True)
            conn.commit()
            return pedido
        except Exception:
            logger.error("Error actualizando datos del pedido %s", id, exc_info=True)
            conn.rollback()
            raise


@router.put("/alquileres/{id}/items")
def update_alquiler_items(id: int, data: PedidoItemUpdate, request: Request):
    require_admin(request)
    with get_db() as conn:
        try:
            pedido = _apply_pedido_items(conn, id, data.items)

            # Si el pedido está en estado que reserva stock, validar después de
            # aplicar los nuevos items. Sin esto el admin podía sumar cantidades
            # que excedieran el stock disponible y crear doble booking silencioso.
            p = conn.execute(
                "SELECT estado, fecha_desde, fecha_hasta FROM alquileres WHERE id=?", (id,)
            ).fetchone()
            if (
                p["estado"] in {"presupuesto", "confirmado", "retirado"}
                and p["fecha_desde"] and p["fecha_hasta"]
            ):
                problemas = _check_stock(conn, id, p["fecha_desde"], p["fecha_hasta"])
                if problemas:
                    raise HTTPException(409, "Sin stock: " + "; ".join(problemas))

            conn.commit()
            return pedido
        except Exception:
            logger.error("Error actualizando items del pedido %s", id, exc_info=True)
            conn.rollback()
            raise
