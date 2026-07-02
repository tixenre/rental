"""Escritura del cierre contable del mes (#809, Fase 6) — la red de fiabilidad.

Cerrar un mes guarda una FOTO inmutable (ganancia + rendición + gastos del mes) y
**traba la edición de movimientos fechados en ese mes** (lo hace cumplir el motor
de movimientos vía `queries.cierres.mes_cerrado`). Reabrir borra la fila. `mes`
es 'YYYY-MM'. Lectura → `queries/cierres.py`.

Reusa los helpers puros de `reportes/cierres.py` (`validar_mes`, `rango_mes`) — no
los duplica. Es un cierre DISTINTO del de liquidación (#721): aquel congela el
reparto del reporte; este congela el estado de cajas/movimientos.
"""

import json

from reportes.cierres import rango_mes, validar_mes

from contabilidad.queries.cierres import cierre_de, snapshot_de
from contabilidad.commands.movimientos import _lock_mes


def cerrar_mes(conn, mes: str, por: str | None) -> dict:
    """Congela la foto del mes (ganancia + rendición + gastos) y lo traba.
    Idempotente: re-cerrar recalcula la foto con los datos actuales."""
    validar_mes(mes)
    _lock_mes(conn, mes)  # serializa contra crear/editar/anular movimiento del mes
    from contabilidad.queries.movimientos import gastos_por_categoria
    from contabilidad.queries.pyl import ganancia_neta
    from contabilidad.queries.rendicion import rendicion

    desde, hasta = rango_mes(mes)
    foto = {
        "mes": mes,
        "ganancia": ganancia_neta(conn, mes),
        "rendicion": rendicion(conn, mes),
        "gastos": gastos_por_categoria(conn, desde, hasta),
    }
    conn.execute(
        """INSERT INTO contabilidad_cierres (mes, snapshot_json, cerrado_por, cerrado_at)
           VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
           ON CONFLICT (mes) DO UPDATE SET
               snapshot_json = excluded.snapshot_json,
               cerrado_por   = excluded.cerrado_por,
               cerrado_at    = CURRENT_TIMESTAMP""",
        (mes, json.dumps(foto), por),
    )
    conn.commit()
    return snapshot_de(conn, mes)


def reabrir_mes(conn, mes: str) -> bool:
    """Borra el cierre → el mes vuelve a editarse y calcularse en vivo."""
    validar_mes(mes)
    _lock_mes(conn, mes)
    existia = cierre_de(conn, mes) is not None
    if existia:
        conn.execute("DELETE FROM contabilidad_cierres WHERE mes = %s", (mes,))
        conn.commit()
    return existia
