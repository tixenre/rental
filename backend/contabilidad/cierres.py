"""Cierre contable del mes (#809, Fase 6) — la red de fiabilidad.

Cerrar un mes guarda una FOTO inmutable (ganancia + rendición + gastos del mes) y
**traba la edición de movimientos fechados en ese mes** (lo hace cumplir el motor
de movimientos vía `mes_cerrado`). Reabrir borra la fila. `mes` es 'YYYY-MM'.

Reusa los helpers puros de `reportes/cierres.py` (`validar_mes`, `rango_mes`) — no
los duplica. Es un cierre DISTINTO del de liquidación (#721): aquel congela el
reparto del reporte; este congela el estado de cajas/movimientos.
"""

import json

from reportes.cierres import rango_mes, validar_mes


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


def cerrar_mes(conn, mes: str, por: str | None) -> dict:
    """Congela la foto del mes (ganancia + rendición + gastos) y lo traba.
    Idempotente: re-cerrar recalcula la foto con los datos actuales."""
    validar_mes(mes)
    from contabilidad.movimientos import gastos_por_categoria
    from contabilidad.pyl import ganancia_neta
    from contabilidad.rendicion import rendicion

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
    existia = cierre_de(conn, mes) is not None
    if existia:
        conn.execute("DELETE FROM contabilidad_cierres WHERE mes = %s", (mes,))
        conn.commit()
    return existia
