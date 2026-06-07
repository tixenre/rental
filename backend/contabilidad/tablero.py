"""Tablero financiero (#809) — compone las tres miradas en una sola respuesta.

1. **Disponible**: cuánta plata hay y dónde (saldos por caja). Plata percibida.
2. **Ganancia del mes**: ingresos devengados − gastos. Resultado del negocio.
3. **Rendición pendiente**: cuánto falta saldar entre los socios este mes.
"""

from datetime import date

from contabilidad.pyl import ganancia_neta
from contabilidad.rendicion import rendicion
from contabilidad.saldos import saldos


def mes_actual() -> str:
    return date.today().strftime("%Y-%m")


def tablero(conn, mes: str | None = None) -> dict:
    from contabilidad.cierres import cierre_de

    mes = mes or mes_actual()
    disponible = saldos(conn)
    gan = ganancia_neta(conn, mes)
    rend = rendicion(conn, mes)
    pendiente_total = sum(int(s["monto"]) for s in rend["sugeridos"])
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
            "ingresos": gan["ingresos"],
            "gastos": gan["gastos"],
            "neta": gan["ganancia_neta"],
        },
        "rendicion_pendiente": {
            "mes": mes,
            "total": pendiente_total,
            "sugeridos": rend["sugeridos"],
            "cuadra": rend["cuadra"],
        },
    }
