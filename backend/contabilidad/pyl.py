"""Ganancia neta del mes (#809) — ingresos − gastos.

Criterio de ingreso (decisión del dueño, documentada): el P&L usa el **ingreso
devengado** = total del reporte de liquidación del mes (pedidos 100% pagados,
atribuidos al día en que se saldaron). Así "ganancia del mes" coincide con el
reporte que el dueño ya conoce. OJO: es una base distinta a la del **saldo de
caja** (que se mueve por plata entrante, incluidas señas). La dualidad
devengado vs percibido es a propósito.

Si el mes está cerrado (#721) el ingreso sale de la foto congelada.
"""

from reportes.cierres import rango_mes, snapshot_de
from reportes.liquidacion import liquidar


def ingresos_devengados(conn, mes: str) -> int:
    """Total del reporte de liquidación del mes (foto si está cerrado)."""
    desde, hasta = rango_mes(mes)
    snap = snapshot_de(conn, mes)
    data = snap if snap is not None else liquidar(conn, desde, hasta)
    return int(data["resumen"]["total"])


def ganancia_neta(conn, mes: str) -> dict:
    """Ingresos devengados − gastos del mes. Incluye el desglose de gastos."""
    from contabilidad.movimientos import gastos_por_categoria

    desde, hasta = rango_mes(mes)
    ingresos = ingresos_devengados(conn, mes)
    por_categoria = gastos_por_categoria(conn, desde, hasta)
    gastos = sum(int(g["monto"]) for g in por_categoria)
    return {
        "mes": mes,
        "ingresos": ingresos,
        "gastos": gastos,
        "ganancia_neta": ingresos - gastos,
        "gastos_por_categoria": por_categoria,
    }
