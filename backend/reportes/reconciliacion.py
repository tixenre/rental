"""Reconciliación de datos de liquidación (#88, hardening).

Chequeos de integridad que, si dan todos en cero, garantizan que el reporte de
liquidación es confiable. Pensado para mostrarse como semáforo en el reporte y
para cazar la divergencia entre las dos formas de marcar "pagado":
`alquileres.monto_pagado` (columna) vs `alquiler_pagos` (ledger, fuente de verdad
del reporte).
"""

from .comisiones import cargar_modelo

# Tope de ids de muestra a devolver por chequeo (no inundar la UI).
_SAMPLE = 25


def reconciliar(conn) -> dict:
    """Corre los chequeos de integridad. Devuelve `ok` global + detalle por chequeo
    (cantidad + ids de muestra)."""
    from database import row_to_dict

    # 1. Pagados según la columna pero invisibles para el reporte: el pedido dice
    #    monto_pagado >= monto_total, pero el ledger de pagos no llega al total
    #    (típico del endpoint legacy que setea la columna sin registrar el pago).
    sin_ledger = conn.execute(
        """
        SELECT a.id
        FROM alquileres a
        LEFT JOIN (
            SELECT pedido_id, COALESCE(SUM(monto), 0) AS pagado
            FROM alquiler_pagos GROUP BY pedido_id
        ) p ON p.pedido_id = a.id
        WHERE a.estado <> 'cancelado'
          AND a.monto_total > 0
          AND a.monto_pagado >= a.monto_total
          AND COALESCE(p.pagado, 0) < a.monto_total
        ORDER BY a.id
        """
    ).fetchall()

    # 2. La columna monto_pagado no coincide con la suma del ledger (cache stale o
    #    escritura por fuera del recálculo).
    divergentes = conn.execute(
        """
        SELECT a.id
        FROM alquileres a
        LEFT JOIN (
            SELECT pedido_id, COALESCE(SUM(monto), 0) AS pagado
            FROM alquiler_pagos GROUP BY pedido_id
        ) p ON p.pedido_id = a.id
        WHERE a.estado <> 'cancelado'
          AND a.monto_pagado <> COALESCE(p.pagado, 0)
        ORDER BY a.id
        """
    ).fetchall()

    # 3. Dueños fuera del modelo de comisiones → en el reporte cobrarían como un
    #    "beneficiario" fantasma (100% a sí mismos). Suele ser un typo en equipos.dueno.
    modelo = cargar_modelo(conn)
    canonicos = set(modelo.keys())
    duenos = conn.execute(
        "SELECT DISTINCT COALESCE(dueno, 'Rambla') AS dueno FROM equipos"
    ).fetchall()
    no_canonicos = sorted(
        row_to_dict(d)["dueno"] for d in duenos if row_to_dict(d)["dueno"] not in canonicos
    )

    def chk(rows):
        ids = [row_to_dict(r)["id"] for r in rows]
        return {"cantidad": len(ids), "ids": ids[:_SAMPLE]}

    pagados_sin_ledger = chk(sin_ledger)
    monto_pagado_divergente = chk(divergentes)

    ok = (
        pagados_sin_ledger["cantidad"] == 0
        and monto_pagado_divergente["cantidad"] == 0
        and len(no_canonicos) == 0
    )

    return {
        "ok": ok,
        "pagados_sin_ledger": pagados_sin_ledger,
        "monto_pagado_divergente": monto_pagado_divergente,
        "duenos_no_canonicos": no_canonicos,
    }
