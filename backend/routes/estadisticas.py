"""
routes/estadisticas.py — Análisis y estadísticas de alquileres.
Lee directo de pedidos + alquiler_items + equipos. Sin tablas intermedias.
"""

from fastapi import APIRouter, Request
from database import get_db, row_to_dict
from admin_guard import require_admin

router = APIRouter()


@router.get("/estadisticas")
def get_estadisticas(request: Request):
    require_admin(request)
    conn = get_db()
    try:
        return compute_estadisticas(conn)
    finally:
        conn.close()


def compute_estadisticas(conn) -> dict:
    """Calcula el dict completo de estadísticas a partir de una conexión.

    Fuente única (barra de calidad: modularidad) — la usan tanto el endpoint
    `get_estadisticas` (transporte HTTP) como el PDF de Reportes (sección
    'Resumen general'). No abre ni cierra la conexión: el caller la administra.
    """
    if True:
        # ── Totales generales (solo pedidos confirmados/finalizados) ──────────────
        totales = conn.execute("""
            SELECT
                COUNT(DISTINCT p.id)           AS total_pedidos,
                COUNT(DISTINCT p.cliente_id)   AS total_clientes,
                SUM(pi.subtotal * (1 - COALESCE(p.descuento_pct, 0) / 100.0))               AS total_ars,
                MIN(p.fecha_desde)             AS desde,
                MAX(p.fecha_desde)             AS hasta
            FROM alquileres p
            JOIN alquiler_items pi ON pi.pedido_id = p.id
            WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
        """).fetchone()

        # ── Por mes ───────────────────────────────────────────────────────────────
        por_mes = conn.execute("""
            SELECT
                to_char(p.fecha_desde, 'YYYY-MM')    AS mes,
                COUNT(DISTINCT p.id)           AS pedidos,
                SUM(pi.subtotal * (1 - COALESCE(p.descuento_pct, 0) / 100.0))               AS total_ars
            FROM alquileres p
            JOIN alquiler_items pi ON pi.pedido_id = p.id
            WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
            GROUP BY to_char(p.fecha_desde, 'YYYY-MM')
            ORDER BY to_char(p.fecha_desde, 'YYYY-MM') DESC
            LIMIT 24
        """).fetchall()

        # ── Top equipos ───────────────────────────────────────────────────────────
        top_equipos = conn.execute("""
            SELECT
                e.nombre                       AS equipo,
                SUM(pi.subtotal * (1 - COALESCE(p.descuento_pct, 0) / 100.0))               AS total_ars,
                COUNT(*)                       AS veces
            FROM alquiler_items pi
            JOIN alquileres p  ON p.id  = pi.pedido_id
            JOIN equipos e  ON e.id  = pi.equipo_id
            WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
            GROUP BY pi.equipo_id, e.nombre
            ORDER BY total_ars DESC
            LIMIT 15
        """).fetchall()

        # ── Top clientes ──────────────────────────────────────────────────────────
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

        # ── Por dueño (basado en equipos.dueno) ───────────────────────────────────
        por_dueno = conn.execute("""
            SELECT
                COALESCE(e.dueno, 'Rambla')    AS dueno,
                SUM(pi.subtotal * (1 - COALESCE(p.descuento_pct, 0) / 100.0))               AS total_ars,
                COUNT(*)                       AS items
            FROM alquiler_items pi
            JOIN alquileres p ON p.id = pi.pedido_id
            JOIN equipos e ON e.id = pi.equipo_id
            WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
            GROUP BY COALESCE(e.dueno, 'Rambla')
            ORDER BY total_ars DESC
        """).fetchall()

        # ── Crecimiento mes a mes ──────────────────────────────────────────────────
        por_mes_calc = [row_to_dict(r) for r in por_mes]
        por_mes_calc.sort(key=lambda x: x['mes'])

        crecimiento = []
        for i, mes in enumerate(por_mes_calc):
            if i > 0:
                mes_anterior = por_mes_calc[i - 1]
                total_ant = mes_anterior['total_ars'] or 0
                if total_ant > 0:
                    pct = ((mes['total_ars'] - total_ant) / total_ant) * 100
                else:
                    pct = 0 if mes['total_ars'] == 0 else 100
            else:
                pct = 0
            crecimiento.append({
                'mes':             mes['mes'],
                'total_ars':       mes['total_ars'],
                'crecimiento_pct': round(pct, 1) if pct else 0,
            })
        crecimiento.sort(key=lambda x: x['mes'], reverse=True)

        # ── Clientes más recurrentes ───────────────────────────────────────────────
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

        # ── Mejor y peor mes ───────────────────────────────────────────────────────
        mejor_peor = conn.execute("""
            SELECT
                (SELECT mes FROM (
                    SELECT to_char(p.fecha_desde, 'YYYY-MM') AS mes, SUM(pi.subtotal * (1 - COALESCE(p.descuento_pct, 0) / 100.0)) AS total
                    FROM alquileres p
                    JOIN alquiler_items pi ON pi.pedido_id = p.id
                    WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
                    GROUP BY to_char(p.fecha_desde, 'YYYY-MM')
                    ORDER BY total DESC LIMIT 1
                ) t1) AS mejor_mes,
                (SELECT MAX(total) FROM (
                    SELECT SUM(pi.subtotal * (1 - COALESCE(p.descuento_pct, 0) / 100.0)) AS total
                    FROM alquileres p
                    JOIN alquiler_items pi ON pi.pedido_id = p.id
                    WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
                    GROUP BY to_char(p.fecha_desde, 'YYYY-MM')
                ) t2) AS mejor_total,
                (SELECT mes FROM (
                    SELECT to_char(p.fecha_desde, 'YYYY-MM') AS mes, SUM(pi.subtotal * (1 - COALESCE(p.descuento_pct, 0) / 100.0)) AS total
                    FROM alquileres p
                    JOIN alquiler_items pi ON pi.pedido_id = p.id
                    WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
                    GROUP BY to_char(p.fecha_desde, 'YYYY-MM')
                    ORDER BY total ASC LIMIT 1
                ) t3) AS peor_mes,
                (SELECT MIN(total) FROM (
                    SELECT SUM(pi.subtotal * (1 - COALESCE(p.descuento_pct, 0) / 100.0)) AS total
                    FROM alquileres p
                    JOIN alquiler_items pi ON pi.pedido_id = p.id
                    WHERE p.estado IN ('confirmado', 'finalizado', 'retirado')
                    GROUP BY to_char(p.fecha_desde, 'YYYY-MM')
                ) t4) AS peor_total
        """).fetchone()

        mejor_peor_dict = row_to_dict(mejor_peor) if mejor_peor else {}
        mejor_peor_mes = {
            'mejor_mes':   mejor_peor_dict.get('mejor_mes'),
            'mejor_total': mejor_peor_dict.get('mejor_total'),
            'peor_mes':    mejor_peor_dict.get('peor_mes'),
            'peor_total':  mejor_peor_dict.get('peor_total'),
        }

        # ── Equipos más favoriteados (analytics de comportamiento de clientes) ──
        # Tabla creada en migración e1f2a3b4c5d6 — guard por si la migración
        # aún no corrió en este ambiente.
        table_exists = conn.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'cliente_favoritos'
            )
        """).scalar()
        if table_exists:
            favoritos_equipo = conn.execute("""
                SELECT
                    e.nombre                       AS equipo,
                    COUNT(*)                       AS total_favoritos,
                    COUNT(DISTINCT cf.cliente_id)  AS clientes_unicos
                FROM cliente_favoritos cf
                JOIN equipos e ON e.id = cf.equipo_id
                GROUP BY cf.equipo_id, e.nombre
                ORDER BY total_favoritos DESC
                LIMIT 15
            """).fetchall()
        else:
            favoritos_equipo = []

        return {
            "totales":              row_to_dict(totales),
            "por_mes":              [row_to_dict(r) for r in por_mes],
            "crecimiento":          crecimiento,
            "top_equipos":          [row_to_dict(r) for r in top_equipos],
            "top_clientes":         [row_to_dict(r) for r in top_clientes],
            "clientes_recurrentes": [row_to_dict(r) for r in clientes_recurrentes],
            "mejor_peor_mes":       mejor_peor_mes,
            "por_dueno":            [row_to_dict(r) for r in por_dueno],
            "favoritos_equipo":     [row_to_dict(r) for r in favoritos_equipo],
        }
