"""Saldos por cuenta (#809) — el corazón del cálculo.

El saldo de una cuenta es:

    saldo = saldo_inicial
          + ingresos_alquiler   (solo cajas de socio: Σ alquiler_pagos del socio)
          + entradas            (Σ movimientos donde la cuenta es destino)
          − egresos             (Σ movimientos donde la cuenta es origen)

`ingresos_alquiler` DERIVA de `alquiler_pagos` (única fuente del cobro, #722): no
se carga ningún movimiento por un cobro de cliente → cero doble-contabilización.
La ventana arranca en el clean start (`LIQUIDACION_INICIO`, misma constante que la
liquidación) — los pagos previos quedaron con `destinatario` NULL a propósito y no
suman.

`calcular_saldos` es pura (testeable sin DB). El SQL solo trae filas planas.
"""

from collections import defaultdict
from datetime import date

from reportes.liquidacion import LIQUIDACION_INICIO


def ingresos_derivados(conn, desde: str | None = None, hasta: str | None = None) -> dict[str, int]:
    """Σ de `alquiler_pagos.monto` por `destinatario` (Pablo/Tincho), desde el
    clean start. Devuelve `{'Tincho': 480000, 'Pablo': 120000}`. Ventana opcional
    `desde`/`hasta` (por fecha de pago, inclusive por día)."""
    sql = """
        SELECT destinatario, COALESCE(SUM(monto), 0) AS total
        FROM alquiler_pagos
        WHERE destinatario IS NOT NULL
          AND fecha::date >= ?::date
    """
    params: list = [LIQUIDACION_INICIO]
    if desde:
        sql += " AND fecha::date >= ?::date"
        params.append(desde)
    if hasta:
        sql += " AND fecha::date <= ?::date"
        params.append(hasta)
    sql += " GROUP BY destinatario"
    rows = conn.execute(sql, tuple(params)).fetchall()
    return {r["destinatario"]: int(r["total"] or 0) for r in rows}


def movimientos_planos(conn, desde: str | None = None, hasta: str | None = None) -> list[dict]:
    """Movimientos NO anulados (filas planas para el cálculo de saldos). Ventana
    opcional por `fecha`."""
    from database import row_to_dict

    sql = """
        SELECT id, tipo, monto, cuenta_origen_id, cuenta_destino_id,
               categoria_id, metodo, fecha, es_rendicion, rendicion_mes
        FROM movimientos
        WHERE NOT anulado
    """
    params: list = []
    if desde:
        sql += " AND fecha >= ?::date"
        params.append(desde)
    if hasta:
        sql += " AND fecha <= ?::date"
        params.append(hasta)
    return [row_to_dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def calcular_saldos(cuentas: list[dict], movimientos: list[dict], ingresos: dict[str, int]) -> list[dict]:
    """PURA. Para cada cuenta, su saldo y el desglose. Devuelve una lista en el
    mismo orden que `cuentas`.

    `cuentas`: filas con id/nombre/tipo/socio/saldo_inicial.
    `movimientos`: filas con monto/cuenta_origen_id/cuenta_destino_id (no anulados).
    `ingresos`: {socio: monto} derivado de alquiler_pagos.
    """
    egresos_por: dict = defaultdict(int)   # cuenta es origen → sale plata
    entradas_por: dict = defaultdict(int)  # cuenta es destino → entra plata
    for m in movimientos:
        monto = int(m["monto"] or 0)
        origen = m.get("cuenta_origen_id")
        destino = m.get("cuenta_destino_id")
        if origen:
            egresos_por[origen] += monto
        if destino:
            entradas_por[destino] += monto

    filas: list[dict] = []
    for c in cuentas:
        cid = c["id"]
        socio = c.get("socio")
        saldo_inicial = int(c.get("saldo_inicial") or 0)
        ingresos_alquiler = int(ingresos.get(socio, 0)) if socio else 0
        entradas = int(entradas_por.get(cid, 0))
        egresos = int(egresos_por.get(cid, 0))
        saldo = saldo_inicial + ingresos_alquiler + entradas - egresos
        filas.append({
            "id": cid,
            "nombre": c["nombre"],
            "tipo": c["tipo"],
            "socio": socio,
            "saldo_inicial": saldo_inicial,
            "ingresos_alquiler": ingresos_alquiler,
            "entradas": entradas,
            "egresos": egresos,
            "saldo": saldo,
        })
    return filas


def saldos(conn, as_of: str | None = None) -> dict:
    """Saldos de todas las cuentas activas + total disponible. Compone la
    derivación de ingresos con el libro de movimientos."""
    cuentas = _cuentas_activas(conn)
    movs = movimientos_planos(conn)
    ingresos = ingresos_derivados(conn)
    filas = calcular_saldos(cuentas, movs, ingresos)
    return {
        "cuentas": filas,
        "total_disponible": sum(f["saldo"] for f in filas),
        "as_of": as_of or date.today().isoformat(),
    }


def saldo_de_cuenta(conn, cuenta_id: int) -> int:
    """Saldo actual de UNA cuenta (entero ARS). Usado por la baja lógica."""
    for f in saldos(conn)["cuentas"]:
        if f["id"] == cuenta_id:
            return int(f["saldo"])
    # Cuenta inactiva o inexistente: recalcular incluyéndola explícitamente.
    from .cuentas import obtener_cuenta
    cuenta = obtener_cuenta(conn, cuenta_id)
    if not cuenta:
        return 0
    filas = calcular_saldos([cuenta], movimientos_planos(conn), ingresos_derivados(conn))
    return int(filas[0]["saldo"]) if filas else 0


def _cuentas_activas(conn) -> list[dict]:
    from .cuentas import listar_cuentas
    return listar_cuentas(conn, incluir_inactivas=False)
