"""Carritos activos — persistencia server-side (#280 Fases 1 + 2).

POST /api/cart/heartbeat → upsert del carrito (anónimo o logueado).
GET  /api/admin/carritos → lista de carritos activos para el back-office.
"""

import json
import uuid as _uuid
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from database import get_db, row_to_dict
from routes.auth import get_session

router = APIRouter(tags=["carritos"])


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
def cart_heartbeat(data: CartHeartbeat, request: Request):
    """Persiste el estado del carrito via upsert por session_id.

    Auth opcional: si hay sesión cliente válida asocia el cliente_id
    automáticamente. El frontend genera el session_id (UUID v4).
    """
    try:
        _uuid.UUID(data.session_id)
    except ValueError:
        raise HTTPException(400, "session_id inválido — debe ser UUID v4")

    session = get_session(request)
    cliente_id: Optional[int] = None
    if session and "cliente_id" in session:
        cliente_id = session["cliente_id"]

    total_items = sum(it.cantidad for it in data.items)
    monto_estimado = 0

    if data.items:
        enriched, monto_estimado = _enrich_items(
            data.items, data.fecha_desde, data.fecha_hasta
        )
    else:
        enriched = []

    items_json = json.dumps(enriched)

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO carritos_activos (
                session_id, cliente_id, items_json,
                fecha_desde, fecha_hasta, hora_desde, hora_hasta,
                total_items, monto_estimado, updated_at
            ) VALUES (?, ?, ?::jsonb, ?, ?, ?, ?, ?, ?, NOW())
            ON CONFLICT (session_id) DO UPDATE SET
                cliente_id     = COALESCE(EXCLUDED.cliente_id, carritos_activos.cliente_id),
                items_json     = EXCLUDED.items_json,
                fecha_desde    = EXCLUDED.fecha_desde,
                fecha_hasta    = EXCLUDED.fecha_hasta,
                hora_desde     = EXCLUDED.hora_desde,
                hora_hasta     = EXCLUDED.hora_hasta,
                total_items    = EXCLUDED.total_items,
                monto_estimado = EXCLUDED.monto_estimado,
                updated_at     = NOW()
            """,
            (
                data.session_id,
                cliente_id,
                items_json,
                data.fecha_desde,
                data.fecha_hasta,
                data.hora_desde,
                data.hora_hasta,
                total_items,
                monto_estimado,
            ),
        )
        conn.commit()

    return {"ok": True}


def _enrich_items(
    items: list[CartItem],
    fecha_desde: Optional[str],
    fecha_hasta: Optional[str],
) -> tuple[list[dict], int]:
    """Enriquece items con nombre del equipo y calcula monto estimado neto.

    Devuelve (lista_enriquecida, monto_estimado_ars).
    """
    from services.precios import calcular_total, jornadas_periodo, ItemPrecio
    from database import to_datetime

    d0 = to_datetime(fecha_desde) if fecha_desde else None
    d1 = to_datetime(fecha_hasta) if fecha_hasta else None
    jornadas = jornadas_periodo(d0, d1)

    enriched: list[dict] = []
    items_precio: list[ItemPrecio] = []

    with get_db() as conn:
        for it in items:
            # alias `e` por convención de queries sobre equipos (MEMORIA 2026-05-26)
            row = conn.execute(
                "SELECT e.nombre, e.precio_jornada FROM equipos e WHERE e.id = ?",
                (it.equipo_id,),
            ).fetchone()
            nombre = row["nombre"] if row else str(it.equipo_id)
            precio = int(row["precio_jornada"] or 0) if row else 0

            enriched.append({
                "equipo_id": it.equipo_id,
                "cantidad":  it.cantidad,
                "nombre":    nombre,
            })
            if precio > 0:
                items_precio.append({
                    "equipo_id":     it.equipo_id,
                    "cantidad":      it.cantidad,
                    "precio_jornada": precio,
                    "cobro_modo":    "jornada",
                })

    if not items_precio:
        return enriched, 0

    desglose = calcular_total(items=items_precio, jornadas=jornadas)
    return enriched, desglose["neto"]


def marcar_confirmado(session_id: str, conn) -> None:
    """Cierra el funnel: marca el carrito como confirmado al crear el pedido."""
    conn.execute(
        "UPDATE carritos_activos SET confirmado = TRUE, updated_at = NOW() "
        "WHERE session_id = ?",
        (session_id,),
    )


@router.get("/admin/carritos")
def admin_listar_carritos(request: Request, horas: int = 72):
    """Lista carritos activos para el back-office.

    Por defecto muestra los actualizados en las últimas 72h y no confirmados.
    El parámetro `horas` permite ampliar la ventana (ej. ?horas=168 = 7 días).
    """
    from admin_guard import require_admin

    require_admin(request)

    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT
                ca.id,
                ca.session_id,
                ca.cliente_id,
                cl.nombre       AS cliente_nombre,
                cl.email        AS cliente_email,
                cl.telefono     AS cliente_telefono,
                ca.items_json,
                ca.fecha_desde,
                ca.fecha_hasta,
                ca.hora_desde,
                ca.hora_hasta,
                ca.total_items,
                ca.monto_estimado,
                ca.confirmado,
                ca.created_at,
                ca.updated_at
            FROM carritos_activos ca
            LEFT JOIN clientes cl ON cl.id = ca.cliente_id
            WHERE NOT ca.confirmado
              AND ca.updated_at > NOW() - INTERVAL '{int(horas)} hours'
            ORDER BY ca.updated_at DESC
            LIMIT 200
            """,
        ).fetchall()

        result = []
        for r in rows:
            d = row_to_dict(r)
            d["items"] = json.loads(d.pop("items_json") or "[]")
            result.append(d)

    return {"carritos": result, "total": len(result)}
