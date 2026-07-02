"""Tablero financiero (#809) — compone las miradas en una sola respuesta. Nunca muta.

1. **Disponible**: cuánta plata hay y dónde (saldos por caja). Plata percibida.
2. **Ganancia del mes**: ingresos devengados − gastos. Resultado del negocio.

La rendición / quién le debe a quién vive en la cuenta corriente de socios
(`saldos().socios`, que ya viaja en `disponible`).
"""

from services.fechas import mes_actual_ar

from contabilidad.queries.cierres import cierre_de
from contabilidad.queries.pyl import ganancia_neta
from contabilidad.queries.saldos import saldos


def mes_actual() -> str:
    return mes_actual_ar()


def tablero(conn, mes: str | None = None) -> dict:
    mes = mes or mes_actual()
    disponible = saldos(conn)
    gan = ganancia_neta(conn, mes)
    c = cierre_de(conn, mes)
    return {
        "mes": mes,
        "cierre": {
            "cerrado": c is not None,
            "cerrado_por": c["cerrado_por"] if c else None,
            "cerrado_at": c["cerrado_at"] if c else None,
        },
        "disponible": disponible,
        "ganancia_mes": {
            "mes": mes,
            "ingresos": gan["facturado"],
            "gastos": gan["gastos"],
            "neta": gan["ganancia_neta"],
        },
    }
