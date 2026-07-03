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

from .liquidacion import combinar_meses, liquidar

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
           FROM liquidacion_cierres WHERE mes = %s""",
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


# Namespace del advisory lock para serializar cerrar_mes/reabrir_mes de la
# liquidación entre sí (dos cierres concurrentes del mismo mes no deben
# pisarse: uno podría commitear su foto DESPUÉS de que otro ya reabrió, o dos
# cierres corriendo out-of-order dejar una foto vieja "ganando"). NUEVO y
# SEPARADO de `_ADVISORY_NS_CONTAB_MES` (contabilidad/commands/movimientos.py,
# 5390420) a propósito: el cierre de liquidación (reparto/comisiones) y el
# cierre contable (cajas/movimientos) son operaciones independientes sobre
# invariantes distintos — compartir namespace bloquearía sin necesidad un
# cierre por el otro. Siguiente número libre tras 5390420.
_ADVISORY_NS_REPORTES_MES = 5390421


def _lock_mes(conn, mes: str) -> None:
    """xact-scoped (se libera solo al commit/rollback de `conn`) — mismo patrón
    que `contabilidad.commands.movimientos._lock_mes`, namespace propio."""
    try:
        anio, mo = mes.split("-")
        key = int(anio) * 100 + int(mo)   # 'YYYY-MM' → YYYYMM, key natural
    except (ValueError, AttributeError):
        key = 0
    conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_ADVISORY_NS_REPORTES_MES, key))


def cerrar_mes(conn, mes: str, por: str | None) -> dict:
    """Congela la foto del reporte de `mes` (upsert idempotente: re-cerrar
    recalcula la foto con los datos actuales). Devuelve el snapshot servible."""
    validar_mes(mes)
    _lock_mes(conn, mes)
    desde, hasta = rango_mes(mes)
    data = liquidar(conn, desde, hasta)
    snapshot_json = json.dumps(data)
    modelo_json = json.dumps(data.get("modelo", {}))
    conn.execute(
        """
        INSERT INTO liquidacion_cierres (mes, snapshot_json, modelo_json, cerrado_por, cerrado_at)
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
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


def _meses_en_rango(desde: str, hasta: str) -> list[str]:
    """Todos los meses calendario 'YYYY-MM' que tocan [desde, hasta], en orden —
    incluye los meses parciales de los bordes si el rango no arranca/termina en
    un límite de mes (ej. un año entero da los 12 meses completos)."""
    y, mo = int(desde[:4]), int(desde[5:7])
    y_h, mo_h = int(hasta[:4]), int(hasta[5:7])
    meses = []
    while (y, mo) <= (y_h, mo_h):
        meses.append(f"{y}-{mo:02d}")
        mo += 1
        if mo > 12:
            mo, y = 1, y + 1
    return meses


def liquidar_rango(conn, desde: str, hasta: str) -> dict:
    """Liquidación de un rango arbitrario de VARIOS meses (ej. la vista "Mes a
    mes"/el total anual) que RESPETA los cierres (#721, #1209): para cada mes
    calendario que el rango cubre COMPLETO, si está cerrado usa la foto
    congelada de `snapshot_de` en vez de recalcularlo en vivo — así la fila de
    ese mes y el total multi-mes no pueden mostrar un número distinto al de la
    tarjeta del mes individual (que ya usaba la foto). Nunca mezcla las dos
    fuentes PARA EL MISMO mes.

    Los fragmentos de mes en los bordes (el rango no arranca/termina en un
    límite de mes calendario) no tienen foto posible para un pedazo de mes —
    siempre se calculan en vivo, igual que antes de este fix.

    La vista de UN solo mes calendario exacto sigue resuelta aparte, en el route
    (`mes_de_rango` + `snapshot_de` directo) — llamar a esta función solo cuando
    el rango NO es un único mes exacto."""
    partes = []
    for mes in _meses_en_rango(desde, hasta):
        d_m, h_m = rango_mes(mes)
        seg_desde, seg_hasta = max(desde, d_m), min(hasta, h_m)
        completo = seg_desde == d_m and seg_hasta == h_m
        if completo:
            snap = snapshot_de(conn, mes)
            partes.append(snap if snap is not None else liquidar(conn, d_m, h_m))
        else:
            partes.append(liquidar(conn, seg_desde, seg_hasta))
    return combinar_meses(partes)


def reabrir_mes(conn, mes: str) -> bool:
    """Borra el cierre de `mes` → vuelve a calcularse en vivo. Devuelve True si
    había un cierre, False si el mes ya estaba abierto."""
    validar_mes(mes)
    _lock_mes(conn, mes)
    existia = cierre_de(conn, mes) is not None
    if existia:
        conn.execute("DELETE FROM liquidacion_cierres WHERE mes = %s", (mes,))
        conn.commit()
    return existia
