"""Lectura del cierre contable del mes (#809, Fase 6). Nunca muta — ver
`commands/cierres.py` para `cerrar_mes`/`reabrir_mes`.

Cerrar un mes guarda una FOTO inmutable (ganancia + rendición + gastos del mes) y
**traba la edición de movimientos fechados en ese mes** (lo hace cumplir el motor
de movimientos vía `mes_cerrado`). `mes` es 'YYYY-MM'.

Es un cierre DISTINTO del de liquidación (#721): aquel congela el reparto del
reporte; este congela el estado de cajas/movimientos.
"""

import json


def cierre_de(conn, mes: str) -> dict | None:
    from database import row_to_dict
    row = conn.execute(
        "SELECT mes, snapshot_json, cerrado_por, cerrado_at FROM contabilidad_cierres WHERE mes = %s",
        (mes,),
    ).fetchone()
    return row_to_dict(row) if row else None


def mes_cerrado(conn, mes: str | None) -> bool:
    """True si el mes contable está cerrado. Lo consultan crear/editar/anular
    movimiento para no tocar un período firme."""
    if not mes:
        return False
    return cierre_de(conn, mes) is not None


def snapshot_de(conn, mes: str) -> dict | None:
    """La foto congelada de un mes cerrado (con metadata), o None si está abierto."""
    c = cierre_de(conn, mes)
    if not c:
        return None
    data = json.loads(c["snapshot_json"])
    data["cerrado"] = True
    data["cerrado_por"] = c["cerrado_por"]
    data["cerrado_at"] = c["cerrado_at"]
    return data
