"""Carritos activos — persistencia server-side (#280 Fases 1 + 2 + 2.5).

POST /api/cart/heartbeat → upsert del carrito (anónimo o logueado).
GET  /api/admin/carritos → lista + métricas de funnel + demanda + conflicto de
                           stock para el back-office.

El conflicto de stock se calcula READ-ONLY reusando el motor de reservas
(`reservas.calcular_disponibilidad`) — nunca con lógica de overlap propia
(MEMORIA 2026-05-30: `backend/reservas/` = fuente única).
"""

import json
import logging
import uuid as _uuid
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from database import get_db, row_to_dict
from routes.auth import get_session

router = APIRouter(tags=["carritos"])
logger = logging.getLogger(__name__)

# Un carrito sin actividad por más de esto se considera abandonado (se le estampa
# `abandonado_en` la primera vez que lo detectamos; un heartbeat nuevo lo limpia).
ABANDONO_HORAS = 24


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
                abandonado_en  = NULL,
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
    """Lista carritos activos + métricas de funnel para el back-office.

    Devuelve, en una sola respuesta para que el dashboard refresque en un solo
    loop: la lista de carritos no confirmados (con flag de abandono y conflicto
    de stock por carrito), KPIs del funnel, ranking de demanda latente y la
    serie de carritos creados/confirmados por día.

    El parámetro `horas` amplía la ventana de la lista (ej. ?horas=168 = 7 días).
    """
    try:
        from admin_guard import require_admin
        from reservas.disponibilidad import calcular_disponibilidad
        require_admin(request)

        with get_db() as conn:
            # Estampar abandono: la primera vez que un carrito cruza el umbral sin
            # actividad le ponemos `abandonado_en`. Idempotente; un heartbeat nuevo
            # lo limpia (ver upsert). Es bookkeeping barato sobre el índice de updated_at.
            conn.execute(
                """
                UPDATE carritos_activos
                SET abandonado_en = NOW()
                WHERE NOT confirmado
                  AND abandonado_en IS NULL
                  AND total_items > 0
                  AND updated_at < NOW() - (? || ' hours')::interval
                """,
                (str(ABANDONO_HORAS),),
            )
            conn.commit()

            rows = conn.execute(
                """
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
                    ca.abandonado_en,
                    ca.created_at,
                    ca.updated_at
                FROM carritos_activos ca
                LEFT JOIN clientes cl ON cl.id = ca.cliente_id
                WHERE NOT ca.confirmado
                  AND ca.total_items > 0
                  AND ca.updated_at > NOW() - (? || ' hours')::interval
                ORDER BY ca.updated_at DESC
                LIMIT 200
                """,
                (str(horas),),
            ).fetchall()

            carritos = []
            for r in rows:
                d = row_to_dict(r)
                raw = d.pop("items_json")
                d["items"] = raw if isinstance(raw, list) else json.loads(raw or "[]")
                d["abandonado"] = d.pop("abandonado_en", None) is not None
                carritos.append(d)

            # Conflicto de stock por carrito (READ-ONLY, motor de reservas). Cacheamos
            # la disponibilidad por par de fechas para no recalcular el motor por carrito.
            disp_cache: dict[tuple[str, str], dict] = {}
            for c in carritos:
                fd, fh = c.get("fecha_desde"), c.get("fecha_hasta")
                if not fd or not fh:
                    c["sin_stock"] = False
                    continue
                fd, fh = str(fd), str(fh)
                key = (fd, fh)
                if key not in disp_cache:
                    disp_cache[key] = calcular_disponibilidad(conn, fd, fh)
                disp = disp_cache[key]
                sin_stock = False
                for it in c["items"]:
                    libres = disp.get(str(it["equipo_id"]))
                    it["disponible"] = libres
                    if libres is not None and it.get("cantidad", 0) > libres:
                        sin_stock = True
                c["sin_stock"] = sin_stock

            stats = _calcular_stats(conn, carritos)
            demanda = _calcular_demanda(carritos)
            por_dia = _carritos_por_dia(conn)

        return {
            "carritos": carritos,
            "total": len(carritos),
            "stats": stats,
            "demanda": demanda,
            "por_dia": por_dia,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("admin_listar_carritos falló")
        raise HTTPException(500, detail=f"{type(exc).__name__}: {exc}")


def _calcular_stats(conn, carritos: list[dict]) -> dict:
    """KPIs del funnel: pipeline, identificación, abandono y conversión 7d."""
    activos = len(carritos)
    pipeline_ars = sum(int(c.get("monto_estimado") or 0) for c in carritos)
    identificados = sum(1 for c in carritos if c.get("cliente_id"))
    abandonados = sum(1 for c in carritos if c.get("abandonado"))

    # Conversión de los últimos 7 días: confirmados / creados (con items).
    row = conn.execute(
        """
        SELECT
            COUNT(*)                              AS creados,
            COUNT(*) FILTER (WHERE confirmado)    AS confirmados
        FROM carritos_activos
        WHERE total_items > 0
          AND created_at > NOW() - INTERVAL '7 days'
        """
    ).fetchone()
    creados_7d = int(row["creados"] or 0)
    confirmados_7d = int(row["confirmados"] or 0)
    conversion_pct = round(100.0 * confirmados_7d / creados_7d, 1) if creados_7d else 0.0

    return {
        "activos": activos,
        "pipeline_ars": pipeline_ars,
        "identificados": identificados,
        "anonimos": activos - identificados,
        "abandonados": abandonados,
        "creados_7d": creados_7d,
        "confirmados_7d": confirmados_7d,
        "conversion_pct": conversion_pct,
    }


def _calcular_demanda(carritos: list[dict]) -> list[dict]:
    """Ranking de demanda latente: equipos más presentes en carritos activos.

    Por equipo: en cuántos carritos aparece (`carritos`) y cuántas unidades se
    piden en total (`unidades`). Ordenado por presencia y luego por unidades.
    """
    agg: dict[int, dict] = {}
    for c in carritos:
        for it in c.get("items", []):
            eid = it.get("equipo_id")
            if eid is None:
                continue
            a = agg.setdefault(
                eid, {"equipo_id": eid, "nombre": it.get("nombre") or str(eid), "carritos": 0, "unidades": 0}
            )
            a["carritos"] += 1
            a["unidades"] += int(it.get("cantidad") or 0)
    ranking = sorted(agg.values(), key=lambda a: (a["carritos"], a["unidades"]), reverse=True)
    return ranking[:10]


def _carritos_por_dia(conn) -> list[dict]:
    """Serie de los últimos 14 días: carritos creados y confirmados por día."""
    rows = conn.execute(
        """
        SELECT
            to_char(created_at, 'YYYY-MM-DD')   AS dia,
            COUNT(*)                            AS creados,
            COUNT(*) FILTER (WHERE confirmado)  AS confirmados
        FROM carritos_activos
        WHERE total_items > 0
          AND created_at > NOW() - INTERVAL '14 days'
        GROUP BY to_char(created_at, 'YYYY-MM-DD')
        ORDER BY to_char(created_at, 'YYYY-MM-DD')
        """
    ).fetchall()
    return [
        {"dia": r["dia"], "creados": int(r["creados"] or 0), "confirmados": int(r["confirmados"] or 0)}
        for r in rows
    ]
