"""Carritos activos — route FINO (#280 Fases 1 + 2 + 2.5).

POST /api/cart/heartbeat → upsert del carrito (anónimo o logueado).
GET  /api/admin/carritos → lista + métricas de funnel + demanda + conflicto de
                           stock para el back-office.

El route es transporte: parsea / autentica (get_session / require_admin) y delega
la lógica en `services.carrito.activos` (patrón del repo: route = transporte, service
= lógica). El conflicto de stock se calcula READ-ONLY reusando el motor de reservas
(`reservas.calcular_disponibilidad`) — nunca con lógica de overlap propia
(MEMORIA 2026-05-30: `backend/reservas/` = fuente única).
"""

import logging
import uuid as _uuid
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from database import get_db
from auth.session import get_session
from rate_limit import limiter
from services.carrito.activos import (
    heartbeat_upsert,
    listar_carritos_admin,
    # Re-exportado para no romper el import de `routes.carritos` en pedidos.py.
    marcar_confirmado,  # noqa: F401
)

router = APIRouter(tags=["carritos"])
logger = logging.getLogger(__name__)


class CartItem(BaseModel):
    equipo_id: int
    cantidad:  int


class CartHeartbeat(BaseModel):
    session_id: str
    items:      list[CartItem] = []
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None
    hora_desde:  Optional[str] = None
    hora_hasta:  Optional[str] = None


@router.post("/cart/heartbeat")
@limiter.limit("60/minute")
def cart_heartbeat(data: CartHeartbeat, request: Request):
    """Persiste el estado del carrito via upsert por session_id.

    Auth opcional: si hay sesión cliente válida asocia el cliente_id
    automáticamente. El frontend genera el session_id (UUID v4).

    Límite bespoke (no CLIENTE_WRITE_LIMIT): a diferencia de los endpoints de
    `cliente_portal`, este acepta tráfico ANÓNIMO (sin sesión) — mismo criterio
    que busquedas.py/compartir.py/cotizacion.py. El frontend debounea 2s por
    cambio de carrito (`useCartHeartbeat.ts`), así que 60/min da margen holgado
    sin dejarlo sin freno.
    """
    try:
        _uuid.UUID(data.session_id)
    except ValueError:
        raise HTTPException(400, "session_id inválido — debe ser UUID v4")

    session = get_session(request)
    cliente_id: Optional[int] = None
    if session and "cliente_id" in session:
        cliente_id = session["cliente_id"]

    with get_db() as conn:
        heartbeat_upsert(
            conn,
            session_id=data.session_id,
            items=data.items,
            fecha_desde=data.fecha_desde,
            fecha_hasta=data.fecha_hasta,
            hora_desde=data.hora_desde,
            hora_hasta=data.hora_hasta,
            cliente_id=cliente_id,
        )
        conn.commit()

    return {"ok": True}


@router.get("/admin/carritos")
def admin_listar_carritos(request: Request, horas: int = 72):
    """Lista carritos activos + métricas de funnel para el back-office.

    Autentica admin y delega el armado de la respuesta en el servicio.
    El parámetro `horas` amplía la ventana de la lista (ej. ?horas=168 = 7 días).
    """
    try:
        from auth.guards import require_admin
        require_admin(request)

        with get_db() as conn:
            return listar_carritos_admin(conn, horas)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("admin_listar_carritos falló")
        raise HTTPException(500, detail=f"{type(exc).__name__}: {exc}")
