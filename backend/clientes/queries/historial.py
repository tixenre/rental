"""
Historial de pedidos de un cliente — resumen LIVIANO para la ficha admin (una
línea por pedido, equipos aplanados a texto). No es el mismo caso de uso que
"mis pedidos" del portal (`routes/cliente_portal/pedidos.py`): ese devuelve
el detalle rico (items completos, pagos, desglose, documentos) para el
dashboard de autoservicio — dominios de lectura distintos, no se fuerzan a
una sola forma.
"""
from database import row_to_dict


def resumen(conn, cliente_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT p.id, p.numero_pedido, p.estado, p.fecha_desde, p.fecha_hasta,
               p.monto_total, p.monto_pagado, p.descuento_pct, p.created_at,
               STRING_AGG(e.nombre, ' · ') AS equipos
        FROM alquileres p
        LEFT JOIN alquiler_items pi ON pi.pedido_id = p.id
        LEFT JOIN equipos e ON e.id = pi.equipo_id
        WHERE p.cliente_id = %s
        GROUP BY p.id, p.numero_pedido, p.estado, p.fecha_desde, p.fecha_hasta,
                 p.monto_total, p.monto_pagado, p.descuento_pct, p.created_at
        ORDER BY p.created_at DESC NULLS LAST, p.numero_pedido DESC
        """,
        (cliente_id,),
    ).fetchall()
    return [row_to_dict(r) for r in rows]
