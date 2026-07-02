"""Registro de pagos (#501 — extraído del god-module `routes/alquileres.py`).

El ledger `alquiler_pagos` es la fuente ÚNICA de "pagado": cada cobro deja su
fila y `monto_pagado` se DERIVA con `_recalcular_monto_pagado`. Acá viven el
modelo + validación de destinatario/método, el recálculo del monto pagado, y los
endpoints del ledger (por pedido + global). Registra sus rutas sobre el router
compartido del paquete `routes.alquileres`.
"""
import logging
from typing import Optional

from fastapi import Request, HTTPException, Query
from pydantic import BaseModel

from database import get_db, row_to_dict, now_ar
from auth.guards import require_admin
from routes.alquileres.core import (
    router,
    _maybe_finalizar,
    _get_alquiler_pagos,
    _get_alquiler_detail,
)

logger = logging.getLogger(__name__)


# Pagos: a quién se cobró (destinatario) y cómo (método). Fuente única de los
# valores admitidos — la usan la validación del endpoint y la vista de logs.
# Cualquiera de los tres puede cobrar; el default es Rambla (en transferencia).
# Cada destinatario mapea a una caja en Contabilidad (Pablo/Tincho → su caja de
# socio; Rambla → Fondo Rambla), donde la plata cobrada se atribuye sola.
from contabilidad.constants import COBRADORES as DESTINATARIOS_PAGO  # fuente única
METODOS_PAGO = ("transferencia", "efectivo")
DESTINATARIO_PAGO_DEFAULT = "Rambla"
METODO_PAGO_DEFAULT = "transferencia"


class PagoCreate(BaseModel):
    monto:        int
    concepto:     Optional[str] = None
    fecha:        Optional[str] = None   # YYYY-MM-DD; si no viene usa hoy
    destinatario: Optional[str] = None   # Tincho|Pablo (default Tincho)
    metodo:       Optional[str] = None   # transferencia|efectivo (default transferencia)


class AnularPagoBody(BaseModel):
    motivo: str


def _resolver_destino_metodo(
    destinatario: Optional[str], metodo: Optional[str]
) -> tuple[str, str]:
    """Aplica defaults (Tincho/transferencia) y valida contra los valores admitidos.

    Pieza pura (testeable sin DB): la usa `agregar_pago`. Lanza HTTP 400 si el
    valor explícito no está en la lista permitida.
    """
    d = destinatario or DESTINATARIO_PAGO_DEFAULT
    m = metodo or METODO_PAGO_DEFAULT
    if d not in DESTINATARIOS_PAGO:
        raise HTTPException(400, f"Destinatario inválido. Usar: {', '.join(DESTINATARIOS_PAGO)}")
    if m not in METODOS_PAGO:
        raise HTTPException(400, f"Método inválido. Usar: {', '.join(METODOS_PAGO)}")
    return d, m


def _recalcular_monto_pagado(conn, pedido_id: int):
    """Recalcula monto_pagado atómicamente desde alquiler_pagos.

    Usa UPDATE con subquery (en lugar de SELECT-luego-UPDATE) para evitar
    race conditions cuando dos pagos llegan en paralelo.

    No hace commit — el caller debe commitear inmediatamente después para que
    el UPDATE no quede huérfano si falla algo posterior en la misma transacción.

    `AND NOT anulado`: un pago anulado (soft-delete, #1184) no cuenta para lo
    pagado — mismo criterio que `movimientos` con sus movimientos anulados.
    """
    conn.execute(
        """
        UPDATE alquileres
           SET monto_pagado = (
               SELECT COALESCE(SUM(monto), 0)
                 FROM alquiler_pagos
                WHERE pedido_id = %s AND NOT anulado
           )
         WHERE id = %s
        """,
        (pedido_id, pedido_id),
    )


# ── Registro de pagos ────────────────────────────────────────────────────────
#
# `alquiler_pagos` (el ledger) es la ÚNICA fuente de verdad de "pagado": cada
# cobro deja su fila y `monto_pagado` se DERIVA con `_recalcular_monto_pagado`.
# Se retiró el endpoint legacy `PATCH /alquileres/{id}/pago` que seteaba
# `monto_pagado` a pelo sin registrar el pago (rompía el reporte de liquidación
# y desincronizaba dashboard vs reporte). Ver #722.

@router.get("/alquileres/{id}/pagos")
def list_pagos(id: int, request: Request):
    require_admin(request)
    with get_db() as conn:
        if not conn.execute("SELECT id FROM alquileres WHERE id=%s", (id,)).fetchone():
            raise HTTPException(404, "Pedido no encontrado")
        pagos = _get_alquiler_pagos(conn, id)
        return pagos


@router.post("/alquileres/{id}/pagos", status_code=201)
def agregar_pago(id: int, data: PagoCreate, request: Request):
    """Agrega una entrada de pago y recalcula monto_pagado."""
    admin = require_admin(request)
    if data.monto <= 0:
        raise HTTPException(400, "El monto debe ser mayor a 0")
    destinatario, metodo = _resolver_destino_metodo(data.destinatario, data.metodo)
    with get_db() as conn:
        try:
            p = conn.execute("SELECT estado FROM alquileres WHERE id=%s", (id,)).fetchone()
            if not p:
                raise HTTPException(404, "Pedido no encontrado")
            if p["estado"] in ("cancelado",):
                raise HTTPException(400, "No se pueden agregar pagos a un pedido cancelado")

            fecha = data.fecha or now_ar().date().isoformat()
            conn.execute("""
                INSERT INTO alquiler_pagos (pedido_id, monto, concepto, destinatario, metodo, fecha, created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (id, data.monto, data.concepto, destinatario, metodo, fecha, admin.get("email")))

            _recalcular_monto_pagado(conn, id)
            _maybe_finalizar(conn, id)
            conn.commit()

            pedido = _get_alquiler_detail(conn, id)
            return pedido
        except Exception:
            logger.error("Error agregando pago al pedido %s", id, exc_info=True)
            conn.rollback()
            raise


@router.post("/alquileres/{id}/pagos/{pago_id}/anular", status_code=200)
def anular_pago(id: int, pago_id: int, data: AnularPagoBody, request: Request):
    """Anula una entrada de pago (soft-delete con motivo) y recalcula monto_pagado.

    Reemplaza el viejo `DELETE` (hard-delete, sin motivo, sin actor) — auditoría
    2026-07-02 (#1184): esta tabla alimenta todo el motor contable y no
    respetaba "la plata no se borra" que `movimientos` sí respeta. Mismo patrón
    que `anular_movimiento`."""
    admin = require_admin(request)
    motivo = (data.motivo or "").strip()
    if not motivo:
        raise HTTPException(400, "Para anular un pago hay que indicar un motivo.")
    with get_db() as conn:
        try:
            if not conn.execute("SELECT id FROM alquileres WHERE id=%s", (id,)).fetchone():
                raise HTTPException(404, "Pedido no encontrado")
            actualizado = conn.execute(
                """UPDATE alquiler_pagos
                   SET anulado = TRUE, anulado_por = %s, anulado_at = CURRENT_TIMESTAMP,
                       anulado_motivo = %s
                   WHERE id = %s AND pedido_id = %s AND NOT anulado
                   RETURNING id""",
                (admin.get("email"), motivo, pago_id, id),
            ).fetchone()
            if not actualizado:
                raise HTTPException(404, "Pago no encontrado (o ya estaba anulado)")

            _recalcular_monto_pagado(conn, id)

            # Si se anuló el pago, puede que ya no esté finalizado → revertir si aplica
            p = conn.execute("SELECT estado, monto_total, monto_pagado FROM alquileres WHERE id=%s", (id,)).fetchone()
            if p and p["estado"] == "finalizado" and (p["monto_pagado"] or 0) < (p["monto_total"] or 0):
                conn.execute("UPDATE alquileres SET estado='devuelto' WHERE id=%s", (id,))

            conn.commit()
            pedido = _get_alquiler_detail(conn, id)
            return pedido
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            logger.error("Error anulando pago en pedido %s", id, exc_info=True)
            conn.rollback()
            raise


@router.get("/admin/pagos")
def list_all_pagos(
    request: Request,
    destinatario: Optional[str] = Query(None),
    metodo: Optional[str] = Query(None),
    desde: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    hasta: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    incluir_anulados: bool = Query(False),
    limit: int = Query(500, le=2000),
):
    """Ledger global de pagos — vista de logs del back-office.

    Lista las filas de `alquiler_pagos` (la fuente ÚNICA de "pagado") con su
    pedido y cliente, ordenadas por fecha desc. Filtros opcionales por
    destinatario, método y rango de fechas (inclusive). Por defecto excluye
    los anulados (mismo patrón que `listar_movimientos`). Devuelve también el
    total del subconjunto filtrado.
    """
    require_admin(request)
    where = ["1=1"]
    params: list = []
    if not incluir_anulados:
        where.append("NOT ap.anulado")
    if destinatario:
        where.append("ap.destinatario = %s")
        params.append(destinatario)
    if metodo:
        where.append("ap.metodo = %s")
        params.append(metodo)
    if desde:
        where.append("ap.fecha::date >= %s")
        params.append(desde)
    if hasta:
        where.append("ap.fecha::date <= %s")
        params.append(hasta)
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT ap.id, ap.pedido_id, ap.monto, ap.concepto,
                   ap.destinatario, ap.metodo, ap.fecha, ap.created_by,
                   ap.anulado, ap.anulado_por, ap.anulado_at, ap.anulado_motivo,
                   al.numero_pedido, al.cliente_nombre
              FROM alquiler_pagos ap
              JOIN alquileres al ON al.id = ap.pedido_id
             WHERE {" AND ".join(where)}
             ORDER BY ap.fecha DESC, ap.id DESC
             LIMIT %s
            """,
            (*params, limit),
        ).fetchall()
        pagos = [row_to_dict(r) for r in rows]
        total = sum((p["monto"] or 0) for p in pagos)
        return {"pagos": pagos, "total": total, "count": len(pagos)}
