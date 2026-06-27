"""Registro de pagos (#501 — extraído del god-module `routes/alquileres.py`).

El ledger `alquiler_pagos` es la fuente ÚNICA de "pagado": cada cobro deja su
fila y `monto_pagado` se DERIVA con `_recalcular_monto_pagado`. Acá viven el
modelo + validación de destinatario/método, el recálculo del monto pagado, y los
endpoints del ledger (por pedido + global). Registra sus rutas sobre el router
compartido del paquete `routes.alquileres`.
"""
import datetime
import logging
from typing import Optional

from fastapi import Request, HTTPException, Query
from pydantic import BaseModel

from database import get_db, row_to_dict
from admin_guard import require_admin
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
from contabilidad.cuentas import COBRADORES as DESTINATARIOS_PAGO  # fuente única
METODOS_PAGO = ("transferencia", "efectivo")
DESTINATARIO_PAGO_DEFAULT = "Rambla"
METODO_PAGO_DEFAULT = "transferencia"


class PagoCreate(BaseModel):
    monto:        int
    concepto:     Optional[str] = None
    fecha:        Optional[str] = None   # YYYY-MM-DD; si no viene usa hoy
    destinatario: Optional[str] = None   # Tincho|Pablo (default Tincho)
    metodo:       Optional[str] = None   # transferencia|efectivo (default transferencia)


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
    """
    conn.execute(
        """
        UPDATE alquileres
           SET monto_pagado = (
               SELECT COALESCE(SUM(monto), 0)
                 FROM alquiler_pagos
                WHERE pedido_id = %s
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
    require_admin(request)
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

            fecha = data.fecha or datetime.date.today().isoformat()
            conn.execute("""
                INSERT INTO alquiler_pagos (pedido_id, monto, concepto, destinatario, metodo, fecha)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (id, data.monto, data.concepto, destinatario, metodo, fecha))

            _recalcular_monto_pagado(conn, id)
            _maybe_finalizar(conn, id)
            conn.commit()

            pedido = _get_alquiler_detail(conn, id)
            return pedido
        except Exception:
            logger.error("Error agregando pago al pedido %s", id, exc_info=True)
            conn.rollback()
            raise


@router.delete("/alquileres/{id}/pagos/{pago_id}", status_code=200)
def eliminar_pago(id: int, pago_id: int, request: Request):
    require_admin(request)
    """Elimina una entrada de pago y recalcula monto_pagado."""
    with get_db() as conn:
        try:
            if not conn.execute("SELECT id FROM alquileres WHERE id=%s", (id,)).fetchone():
                raise HTTPException(404, "Pedido no encontrado")
            if not conn.execute(
                "SELECT id FROM alquiler_pagos WHERE id=%s AND pedido_id=%s", (pago_id, id)
            ).fetchone():
                raise HTTPException(404, "Pago no encontrado")

            conn.execute("DELETE FROM alquiler_pagos WHERE id=%s", (pago_id,))
            _recalcular_monto_pagado(conn, id)

            # Si se quitó pago, puede que ya no esté finalizado → revertir si aplica
            p = conn.execute("SELECT estado, monto_total, monto_pagado FROM alquileres WHERE id=%s", (id,)).fetchone()
            if p and p["estado"] == "finalizado" and (p["monto_pagado"] or 0) < (p["monto_total"] or 0):
                conn.execute("UPDATE alquileres SET estado='devuelto' WHERE id=%s", (id,))

            conn.commit()
            pedido = _get_alquiler_detail(conn, id)
            return pedido
        except Exception:
            logger.error("Error registrando pago en pedido %s", id, exc_info=True)
            conn.rollback()
            raise


@router.get("/admin/pagos")
def list_all_pagos(
    request: Request,
    destinatario: Optional[str] = Query(None),
    metodo: Optional[str] = Query(None),
    desde: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    hasta: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    limit: int = Query(500, le=2000),
):
    """Ledger global de pagos — vista de logs del back-office.

    Lista las filas de `alquiler_pagos` (la fuente ÚNICA de "pagado") con su
    pedido y cliente, ordenadas por fecha desc. Filtros opcionales por
    destinatario, método y rango de fechas (inclusive). Devuelve también el
    total del subconjunto filtrado.
    """
    require_admin(request)
    where = ["1=1"]
    params: list = []
    if destinatario:
        where.append("ap.destinatario = ?")
        params.append(destinatario)
    if metodo:
        where.append("ap.metodo = ?")
        params.append(metodo)
    if desde:
        where.append("ap.fecha::date >= ?")
        params.append(desde)
    if hasta:
        where.append("ap.fecha::date <= ?")
        params.append(hasta)
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT ap.id, ap.pedido_id, ap.monto, ap.concepto,
                   ap.destinatario, ap.metodo, ap.fecha,
                   al.numero_pedido, al.cliente_nombre
              FROM alquiler_pagos ap
              JOIN alquileres al ON al.id = ap.pedido_id
             WHERE {" AND ".join(where)}
             ORDER BY ap.fecha DESC, ap.id DESC
             LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        pagos = [row_to_dict(r) for r in rows]
        total = sum((p["monto"] or 0) for p in pagos)
        return {"pagos": pagos, "total": total, "count": len(pagos)}
