"""El semáforo unificado de reconciliación — un solo `ok` + detalle.

OWNA: nada nuevo. Delega en los dos `reconciliar()` existentes
(`reportes.reconciliacion` + `contabilidad.queries.reconciliacion`, que YA anida
al primero) — no reimplementa ningún chequeo. Primer consumidor real: el job de
alerta proactiva (`jobs/reconciliacion.py`, Fase 2 #1184), que antes hubiera
tenido que llamar a los dos por separado.
"""


def estado(conn) -> dict:
    """`{ok, reporte, contabilidad}` — `ok` es el AND de ambos semáforos."""
    from contabilidad.queries.reconciliacion import (
        reconciliar as reconciliar_contabilidad,
    )
    from reportes.reconciliacion import reconciliar as reconciliar_reportes

    reporte = reconciliar_reportes(conn)
    contable = reconciliar_contabilidad(conn)
    return {
        "ok": bool(reporte.get("ok")) and bool(contable.get("ok")),
        "reporte": reporte,
        "contabilidad": contable,
    }
