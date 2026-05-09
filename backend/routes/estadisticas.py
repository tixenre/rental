"""
routes/estadisticas.py — Análisis y estadísticas de alquileres.
"""

from fastapi import APIRouter, Query
from typing import Optional
from database import get_db, row_to_dict

router = APIRouter()


@router.get("/estadisticas")
def get_estadisticas():
    conn = get_db()
    try:
        totales = conn.execute("""
            SELECT
                COUNT(DISTINCT p.id)           AS total_pedidos,
                COUNT(DISTINCT p.cliente_id)   AS total_clientes,
                SUM(pi.subtotal)               AS total_ars,
                MIN(p.fecha_desde)             AS desde,
                MAX(p.fecha_desde)             AS hasta
            FROM alquileres p
            JOIN alquiler_items pi ON pi.pedido_id = p.id
            WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
        """).fetchone()

        por_mes = conn.execute("""
            SELECT
                substr(p.fecha_desde, 1, 7)    AS mes,
                COUNT(DISTINCT p.id)           AS pedidos,
                SUM(pi.subtotal)               AS total_ars
            FROM alquileres p
            JOIN alquiler_items pi ON pi.pedido_id = p.id
            WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
            GROUP BY substr(p.fecha_desde, 1, 7)
            ORDER BY substr(p.fecha_desde, 1, 7) DESC
            LIMIT 24
        """).fetchall()

        top_equipos = conn.execute("""
            SELECT
                e.nombre                       AS equipo,
                SUM(pi.subtotal)               AS total_ars,
                COUNT(*)                       AS veces
            FROM alquiler_items pi
            JOIN alquileres p  ON p.id  = pi.pedido_id
            JOIN equipos e  ON e.id  = pi.equipo_id
            WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
            GROUP BY pi.equipo_id, e.nombre
            ORDER BY total_ars DESC
            LIMIT 15
        """).fetchall()

        top_clientes = conn.execute("""
            SELECT
                MAX(COALESCE(c.apellido || ', ' || c.nombre, p.cliente_nombre)) AS cliente,
                SUM(p.monto_total)             AS total_ars,
                COUNT(DISTINCT p.id)           AS pedidos
            FROM alquileres p
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
            GROUP BY COALESCE(CAST(p.cliente_id AS TEXT), 'txt:' || p.cliente_nombre)
            ORDER BY total_ars DESC
            LIMIT 10
        """).fetchall()

        por_dueno = conn.execute("""
            SELECT
                COALESCE(e.dueno, 'Rambla')    AS dueno,
                SUM(pi.subtotal)               AS total_ars,
                COUNT(*)                       AS items
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            JOIN equipos e ON e.id = pi.equipo_id
            WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
            GROUP BY COALESCE(e.dueno, 'Rambla')
            ORDER BY total_ars DESC
        """).fetchall()

        por_mes_calc = [row_to_dict(r) for r in por_mes]
        por_mes_calc.sort(key=lambda x: x['mes'])
        crecimiento = []
        for i, mes in enumerate(por_mes_calc):
            if i > 0:
                mes_anterior = por_mes_calc[i - 1]
                total_ant = mes_anterior['total_ars'] or 0
                pct = ((mes['total_ars'] - total_ant) / total_ant * 100) if total_ant > 0 else (0 if mes['total_ars'] == 0 else 100)
            else:
                pct = 0
            crecimiento.append({'mes': mes['mes'], 'total_ars': mes['total_ars'], 'crecimiento_pct': round(pct, 1) if pct else 0})
        crecimiento.sort(key=lambda x: x['mes'], reverse=True)

        clientes_recurrentes = conn.execute("""
            SELECT
                MAX(COALESCE(c.apellido || ', ' || c.nombre, p.cliente_nombre)) AS cliente,
                COUNT(DISTINCT p.id)           AS veces_alquiladas,
                SUM(p.monto_total)             AS total_ars
            FROM alquileres p
            LEFT JOIN clientes c ON c.id = p.cliente_id
            WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
            GROUP BY COALESCE(CAST(p.cliente_id AS TEXT), 'txt:' || p.cliente_nombre)
            HAVING COUNT(DISTINCT p.id) > 1
            ORDER BY veces_alquiladas DESC
            LIMIT 10
        """).fetchall()

        return {
            "totales":              row_to_dict(totales),
            "por_mes":              [row_to_dict(r) for r in por_mes],
            "crecimiento":          crecimiento,
            "top_equipos":          [row_to_dict(r) for r in top_equipos],
            "top_clientes":         [row_to_dict(r) for r in top_clientes],
            "clientes_recurrentes": [row_to_dict(r) for r in clientes_recurrentes],
            "por_dueno":            [row_to_dict(r) for r in por_dueno],
        }
    finally:
        conn.close()


@router.get("/estadisticas/pedidos")
def list_pedidos_stats(
    q:        Optional[str] = Query(None),
    dueno:    Optional[str] = Query(None),
    page:     int = Query(1, ge=1),
    per_page: int = Query(80, ge=1, le=500),
):
    conn   = get_db()
    offset = (page - 1) * per_page
    where  = "WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')"
    params: list = []

    if q:
        like = f"%{q}%"
        where += " AND (p.cliente_nombre LIKE ? OR CAST(p.numero_pedido AS TEXT) LIKE ? OR e.nombre LIKE ?)"
        params += [like, like, like]
    if dueno:
        where += " AND e.dueno = ?"
        params.append(dueno)

    join_eq = "JOIN alquiler_items pi ON pi.pedido_id = p.id JOIN equipos e ON e.id = pi.equipo_id" if (dueno or q) else ""

    try:
        total = conn.execute(
            f"SELECT COUNT(DISTINCT p.id) FROM alquileres p {join_eq} {where}", params
        ).fetchone()[0]

        rows = conn.execute(f"""
            SELECT DISTINCT
                p.id, p.numero_pedido, p.numero_remito, p.estado,
                p.fecha_desde, p.fecha_hasta, p.monto_total, p.descuento_pct,
                COALESCE(c.apellido || ', ' || c.nombre, p.cliente_nombre) AS cliente
            FROM alquileres p
            LEFT JOIN clientes c ON c.id = p.cliente_id
            {join_eq}
            {where}
            ORDER BY p.fecha_desde DESC
            LIMIT ? OFFSET ?
        """, params + [per_page, offset]).fetchall()

        return {"total": total, "page": page, "per_page": per_page, "items": [row_to_dict(r) for r in rows]}
    finally:
        conn.close()
