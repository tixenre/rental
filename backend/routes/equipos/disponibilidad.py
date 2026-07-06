"""routes/equipos/disponibilidad.py — KPIs, calendario e historial de un equipo.

Move-verbatim (issue de tracking #1258, Corte B): `equipos_afuera`/`equipos_kpis`
(disponibilidad en tiempo real), `disponibilidad_calendario`/`get_equipo_calendario`
(vistas de calendario) y `get_equipo_historial`/`get_precio_historial` (historial
de alquileres/precio) — todo lectura, ninguno muta. Registra sus rutas en el
router compartido del paquete `routes.equipos` (definido en `core.py`).
"""
import calendar as _cal
import datetime
from datetime import date as _date, timedelta
from typing import Optional

from fastapi import Query, HTTPException, Request

from database import get_db, row_to_dict
from reservas import reservado_total
from reservas.semantics import parientes_de
from auth.guards import require_admin
from routes.equipos.core import router


# ── Disponibilidad en tiempo real ────────────────────────────────────────────

@router.get("/equipos/afuera")
def equipos_afuera():
    """
    Devuelve los equipos actualmente retirados (pedidos en estado 'retirado'
    con fecha_hasta >= hoy), con cantidad afuera y fecha de devolución.
    Respuesta: { "equipo_id": { cantidad_afuera, stock_total, devuelve, pedidos } }
    """
    today = datetime.date.today().isoformat()
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                pi.equipo_id,
                e.cantidad                                              AS stock_total,
                SUM(pi.cantidad)                                        AS cantidad_afuera,
                MIN(p.fecha_hasta)                                      AS devuelve_pronto,
                MAX(p.fecha_hasta)                                      AS devuelve_ultimo,
                STRING_AGG(
                    COALESCE(c.nombre || ' ' || c.apellido, p.cliente_nombre),
                    ', '
                )                                                       AS clientes
            FROM alquiler_items pi
            JOIN alquileres  p ON p.id  = pi.pedido_id
            JOIN equipos  e ON e.id  = pi.equipo_id
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE p.estado    = 'retirado'
              AND p.fecha_hasta >= %s
            GROUP BY pi.equipo_id, e.cantidad
        """, (today,)).fetchall()
        return {str(r["equipo_id"]): row_to_dict(r) for r in rows}


@router.get("/equipos/kpis")
def equipos_kpis(request: Request):
    """KPIs del inventario para el header de /admin/equipos:
    - total: equipos FÍSICOS del catálogo (no eliminados). Excluye los combos: un
      combo es un bundle (sin stock propio, precio derivado), no un equipo distinto.
    - en_uso_hoy: unidades en pedidos retirados que solapan hoy.
    - mantenimiento: equipos con mantenimiento que bloquea stock activo hoy.
    """
    require_admin(request)
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM equipos "
            "WHERE eliminado_at IS NULL AND es_recurso_interno = FALSE AND tipo != 'combo'"
        ).fetchone()[0]
        en_uso_hoy = conn.execute("""
            SELECT COALESCE(SUM(pi.cantidad), 0)
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            WHERE p.estado = 'retirado'
              AND p.fecha_desde::date <= CURRENT_DATE
              AND p.fecha_hasta::date >= CURRENT_DATE
        """).fetchone()[0]
        mantenimiento = conn.execute("""
            SELECT COUNT(DISTINCT equipo_id)
            FROM equipo_mantenimiento
            WHERE bloquea_stock = TRUE
              AND fecha::date <= CURRENT_DATE
              AND COALESCE(fecha_hasta, fecha)::date >= CURRENT_DATE
        """).fetchone()[0]
        return {
            "total": int(total or 0),
            "en_uso_hoy": int(en_uso_hoy or 0),
            "mantenimiento": int(mantenimiento or 0),
        }


@router.get("/equipos/{id}/disponibilidad-calendario")
def disponibilidad_calendario(
    id: int,
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
):
    """Estado de disponibilidad por día de UN equipo (#808), catálogo-facing.

    Devuelve `{'stock': N, 'dias': {YYYY-MM-DD: 'parcial'|'reservado'}}` — los días
    `libre` se OMITEN (default en el front). Lectura sobre el motor de reservas
    (`estado_diario_equipo`), sin recalcular overlap. Sin auth (igual que el catálogo).
    """
    from reservas.disponibilidad import estado_diario_equipo

    hoy = _date.today()
    d_desde = desde or hoy.isoformat()
    d_hasta = hasta or (hoy + timedelta(days=90)).isoformat()
    # Cap defensivo del rango (≤ 180 días) para no abusar de la lectura.
    try:
        span = (_date.fromisoformat(d_hasta[:10]) - _date.fromisoformat(d_desde[:10])).days
    except ValueError:
        raise HTTPException(400, "Fechas inválidas (usar YYYY-MM-DD)")
    if span < 0:
        raise HTTPException(400, "El rango es inválido (hasta < desde)")
    if span > 180:
        raise HTTPException(400, "El rango no puede superar 180 días")

    with get_db() as conn:
        res = estado_diario_equipo(conn, id, d_desde, d_hasta)
    if res is None:
        raise HTTPException(404, "Equipo no encontrado")
    # Slim: solo días no-libres (libre = ausente).
    res["dias"] = {d: e for d, e in res["dias"].items() if e != "libre"}
    return res


# ── Historial de alquileres por equipo ───────────────────────────────────────

@router.get("/equipos/{id}/historial")
def get_equipo_historial(id: int):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

        rows = conn.execute("""
            SELECT
                p.id, p.numero_pedido, p.estado,
                p.fecha_desde, p.fecha_hasta,
                COALESCE(c.nombre || ' ' || c.apellido, p.cliente_nombre) AS cliente,
                pi.cantidad, pi.precio_jornada AS precio_item,
                GREATEST(1, (p.fecha_hasta::date - p.fecha_desde::date))::INTEGER AS dias
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE pi.equipo_id = %s
            ORDER BY p.fecha_desde DESC
        """, (id,)).fetchall()

        items      = [row_to_dict(r) for r in rows]
        total_dias = sum(r["dias"] or 1 for r in items)
        total_rev  = sum((r["precio_item"] or 0) * (r["cantidad"] or 1) * (r["dias"] or 1) for r in items)

        return {
            "historial": items,
            "stats": {
                "total_alquileres": len(items),
                "total_dias":       total_dias,
                "total_revenue":    total_rev,
                "ultimo_alquiler":  items[0]["fecha_desde"] if items else None,
            },
        }


# ── Historial de precios ─────────────────────────────────────────────────────

@router.get("/equipos/{id}/precio-historial")
def get_precio_historial(id: int):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")
        rows = conn.execute("""
            SELECT precio_jornada, changed_at
            FROM equipo_precio_historial
            WHERE equipo_id = %s
            ORDER BY changed_at DESC
        """, (id,)).fetchall()
        return [row_to_dict(r) for r in rows]


@router.get("/equipos/{id}/calendario")
def get_equipo_calendario(id: int, year: int = Query(...), month: int = Query(...)):
    """Unidades libres por día de un equipo en un mes.

    Delega el conteo de "reservado" en el motor único `reservas.reservado_total`,
    que sube por TODO el grafo de composición (combos/kits anidados, a cualquier
    profundidad). Antes este endpoint reimplementaba el overlap a 1 solo nivel de
    kit (`directas` + `via_kit`) → mostraba un equipo como libre aunque estuviera
    reservado vía un compuesto anidado (#923; violaba la fuente única, MEMORIA
    2026-05-30 / 2026-05-31). El grafo inverso se calcula una vez y se reusa por día.
    Comportamiento por día = overlap a nivel timestamp (igual que el gate): un día
    en el que el alquiler sigue ocupado, aunque devuelva más tarde, cuenta como
    ocupado (la versión vieja, a fecha exclusiva, lo mostraba libre — optimista).
    """
    if not (1 <= month <= 12):
        raise HTTPException(400, "Mes inválido")

    with get_db() as conn:
        equipo = conn.execute(
            "SELECT id, cantidad FROM equipos WHERE id=%s", (id,)
        ).fetchone()
        if not equipo:
            raise HTTPException(404, "Equipo no encontrado")

        stock_total = equipo["cantidad"]
        _, days_in_month = _cal.monthrange(year, month)
        rev = parientes_de(conn)  # grafo inverso de composición — una vez (motor)

        result: dict[str, int] = {}
        for day_num in range(1, days_in_month + 1):
            d0 = _date(year, month, day_num)
            d1 = d0 + timedelta(days=1)
            # Reservado recursivo (directo + vía cualquier compuesto que lo
            # contenga) que se pisa con [d0, d1). excl=-1 → no excluir ningún
            # pedido (contar todos). Sin buffer (vista de día, no chequeo de gate).
            reservado = reservado_total(
                conn, id, -1, d1.isoformat(), d0.isoformat(), rev_graph=rev,
            )
            result[d0.isoformat()] = max(0, stock_total - reservado)

        return result
