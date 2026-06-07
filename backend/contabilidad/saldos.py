"""Saldos por cuenta (#809) — el corazón del cálculo.

El saldo de una cuenta es:

    saldo = saldo_inicial
          + ingresos_alquiler   (caja de cobrador: Σ alquiler_pagos del cobrador)
          + entradas            (Σ movimientos donde la cuenta es destino)
          − egresos             (Σ movimientos donde la cuenta es origen)

`ingresos_alquiler` DERIVA de `alquiler_pagos` (única fuente del cobro, #722): no
se carga ningún movimiento por un cobro de cliente → cero doble-contabilización.
El clean start se aplica por la **fecha del alquiler** del pedido (`fecha_desde >=
LIQUIDACION_INICIO`), MISMO corte que la liquidación y la rendición — un alquiler
de antes de junio NO entra a Finanzas aunque se cobre después (decisión 2026-06-03:
el corte es por fecha del alquiler, NO de pago).

`calcular_saldos` es pura (testeable sin DB). El SQL solo trae filas planas.
"""

from collections import defaultdict
from datetime import date

from reportes.liquidacion import LIQUIDACION_INICIO


def ingresos_derivados(conn, desde: str | None = None, hasta: str | None = None) -> dict[str, int]:
    """Σ de `alquiler_pagos.monto` por `destinatario` (Pablo/Tincho/Rambla), solo de
    pedidos cuyo ALQUILER cae en el clean start (`fecha_desde >= LIQUIDACION_INICIO`).
    Devuelve `{'Tincho': 480000, 'Pablo': 120000}`. Ventana opcional `desde`/`hasta`
    (por fecha de pago, inclusive por día)."""
    sql = """
        SELECT ap.destinatario, COALESCE(SUM(ap.monto), 0) AS total
        FROM alquiler_pagos ap
        JOIN alquileres al ON al.id = ap.pedido_id
        WHERE ap.destinatario IS NOT NULL
          AND al.fecha_desde >= ?::date
    """
    params: list = [LIQUIDACION_INICIO]
    if desde:
        sql += " AND ap.fecha::date >= ?::date"
        params.append(desde)
    if hasta:
        sql += " AND ap.fecha::date <= ?::date"
        params.append(hasta)
    sql += " GROUP BY ap.destinatario"
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
        moneda = c.get("moneda") or "ARS"
        saldo_inicial = int(c.get("saldo_inicial") or 0)
        # Los cobros de clientes son en ARS → solo alimentan cajas en pesos.
        ingresos_alquiler = int(ingresos.get(socio, 0)) if (socio and moneda == "ARS") else 0
        entradas = int(entradas_por.get(cid, 0))
        egresos = int(egresos_por.get(cid, 0))
        saldo = saldo_inicial + ingresos_alquiler + entradas - egresos
        filas.append({
            "id": cid,
            "nombre": c["nombre"],
            "tipo": c["tipo"],
            "socio": socio,
            "moneda": moneda,
            "saldo_inicial": saldo_inicial,
            "ingresos_alquiler": ingresos_alquiler,
            "entradas": entradas,
            "egresos": egresos,
            "saldo": saldo,
        })
    return filas


def _totales_por_moneda(filas: list[dict]) -> dict[str, int]:
    """Suma de saldos agrupada por moneda (no se mezclan ARS y USD). PURA."""
    tot: dict[str, int] = defaultdict(int)
    for f in filas:
        tot[f.get("moneda") or "ARS"] += int(f["saldo"])
    return dict(tot)


def saldos(conn, as_of: str | None = None) -> dict:
    """Saldos de todas las cuentas activas + totales por moneda. Compone la
    derivación de ingresos con el libro de movimientos."""
    cuentas = _cuentas_activas(conn)
    movs = movimientos_planos(conn)
    ingresos = ingresos_derivados(conn)
    filas = calcular_saldos(cuentas, movs, ingresos)
    totales = _totales_por_moneda(filas)
    return {
        "cuentas": filas,
        "totales": totales,
        "total_disponible": totales.get("ARS", 0),  # ARS (compat); USD va en `totales`
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
