"""Cierre de meses de liquidación (#721) — congelar la foto de un mes liquidado.

El reporte de liquidación (#88) se calcula EN VIVO. Dos cosas reescriben el pasado:
editar el modelo de comisiones (afecta todos los meses) y editar un pedido/pago
viejo (afecta su mes). Mientras el mes está **abierto** eso es deseable (las
correcciones fluyen). Un mes ya liquidado/pagado tiene que quedar **firme**.

Cerrar un mes guarda una **foto inmutable** del reporte de ese mes —los números Y
el modelo con que se calculó— en `liquidacion_cierres`. Mientras está cerrado el
reporte se sirve desde la foto, inmune a cambios posteriores (modelo o pedidos).
**Reabrir** = borrar la fila → el mes vuelve a calcularse en vivo.

El mes es `'YYYY-MM'`. La foto es el dict completo de `liquidar` para ese mes, así
el front la renderiza idéntica. La staleness (editar un pedido de un mes cerrado)
la caza el chequeo de reconciliación, no este módulo.
"""

import json
import re
from calendar import monthrange

from .liquidacion import liquidar

_MES_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def validar_mes(mes: str) -> None:
    """Valida que `mes` tenga la forma 'YYYY-MM'. Lanza ValueError si no."""
    if not isinstance(mes, str) or not _MES_RE.match(mes):
        raise ValueError("Mes inválido — usá el formato YYYY-MM.")


def rango_mes(mes: str) -> tuple[str, str]:
    """('YYYY-MM') → (primer_día, último_día) en ISO 'YYYY-MM-DD'."""
    validar_mes(mes)
    y, mo = int(mes[:4]), int(mes[5:7])
    ultimo = monthrange(y, mo)[1]
    return f"{mes}-01", f"{mes}-{ultimo:02d}"


def mes_de_rango(desde: str, hasta: str) -> str | None:
    """Si [desde, hasta] es EXACTAMENTE un mes calendario, devuelve su 'YYYY-MM';
    si no (ej. un año entero), None. Es lo que decide si un pedido de reporte cae
    sobre un mes cerrable — la vista mensual del front manda justo un mes."""
    if not (isinstance(desde, str) and isinstance(hasta, str)):
        return None
    if len(desde) < 7 or desde[:7] != hasta[:7]:
        return None
    mes = desde[:7]
    try:
        d, h = rango_mes(mes)
    except ValueError:
        return None
    return mes if (desde == d and hasta == h) else None


def cierre_de(conn, mes: str) -> dict | None:
    """La fila de cierre de `mes` (dict), o None si el mes está abierto."""
    from database import row_to_dict

    row = conn.execute(
        """SELECT mes, snapshot_json, modelo_json, cerrado_por, cerrado_at
           FROM liquidacion_cierres WHERE mes = ?""",
        (mes,),
    ).fetchone()
    return row_to_dict(row) if row else None


def snapshot_de(conn, mes: str) -> dict | None:
    """El reporte FROZEN de un mes cerrado, listo para servir (con metadata
    `cerrado/cerrado_por/cerrado_at`), o None si el mes está abierto."""
    c = cierre_de(conn, mes)
    if not c:
        return None
    data = json.loads(c["snapshot_json"])
    data["cerrado"] = True
    data["cerrado_por"] = c["cerrado_por"]
    data["cerrado_at"] = c["cerrado_at"]
    return data


def cerrar_mes(conn, mes: str, por: str | None) -> dict:
    """Congela la foto del reporte de `mes` (upsert idempotente: re-cerrar
    recalcula la foto con los datos actuales). Devuelve el snapshot servible."""
    desde, hasta = rango_mes(mes)
    data = liquidar(conn, desde, hasta)
    snapshot_json = json.dumps(data)
    modelo_json = json.dumps(data.get("modelo", {}))
    conn.execute(
        """
        INSERT INTO liquidacion_cierres (mes, snapshot_json, modelo_json, cerrado_por, cerrado_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT (mes) DO UPDATE SET
            snapshot_json = excluded.snapshot_json,
            modelo_json   = excluded.modelo_json,
            cerrado_por   = excluded.cerrado_por,
            cerrado_at    = CURRENT_TIMESTAMP
        """,
        (mes, snapshot_json, modelo_json, por),
    )
    conn.commit()
    return snapshot_de(conn, mes)


def reabrir_mes(conn, mes: str) -> bool:
    """Borra el cierre de `mes` → vuelve a calcularse en vivo. Devuelve True si
    había un cierre, False si el mes ya estaba abierto."""
    validar_mes(mes)
    existia = cierre_de(conn, mes) is not None
    if existia:
        conn.execute("DELETE FROM liquidacion_cierres WHERE mes = ?", (mes,))
        conn.commit()
    return existia
