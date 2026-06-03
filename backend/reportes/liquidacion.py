"""Liquidación: cuánto entró y cómo se reparte entre dueños (#88).

Reglas (decididas con el dueño):
- Solo cuentan pedidos **100% pagados** (`monto_pagado >= monto_total`).
- Cada pedido se atribuye al **día en que quedó saldado** (la fecha del pago con
  el que el acumulado cruzó `monto_total`) — NO por fecha de alquiler. Si se pagó
  en otro mes, cuenta para ese mes.
- El `monto_total` se prorratea entre los equipos del pedido por su participación
  en el `subtotal`, y la plata de cada equipo se reparte según su `dueno`
  (`comisiones.repartir`).

El pipeline es SQL → filas planas → `agregar` (puro), para poder testear la
matemática (prorrateo + reparto + buckets) sin DB.
"""

from collections import defaultdict

from .comisiones import cargar_modelo, repartir


def filas_atribucion(conn, desde: str, hasta: str) -> list[dict]:
    """Filas `(fecha, dueno, equipo, monto)`: el monto prorrateado que cada equipo
    aportó, fechado en el día en que su pedido quedó saldado, dentro del rango."""
    from database import row_to_dict
    sql = """
        WITH acum AS (
            SELECT ap.pedido_id,
                   ap.fecha,
                   SUM(ap.monto) OVER (
                       PARTITION BY ap.pedido_id ORDER BY ap.fecha, ap.id
                   ) AS acumulado
            FROM alquiler_pagos ap
        ),
        saldado AS (
            SELECT a.pedido_id, MIN(a.fecha) AS fecha_saldado
            FROM acum a
            JOIN alquileres al ON al.id = a.pedido_id
            WHERE al.estado <> 'cancelado'
              AND al.monto_total > 0
              AND a.acumulado >= al.monto_total
            GROUP BY a.pedido_id
        ),
        en_rango AS (
            SELECT pedido_id, fecha_saldado
            FROM saldado
            WHERE fecha_saldado::date BETWEEN ?::date AND ?::date
        ),
        tot AS (
            SELECT pedido_id, SUM(subtotal) AS suma_items
            FROM alquiler_items
            GROUP BY pedido_id
        )
        SELECT r.fecha_saldado::date                              AS fecha,
               COALESCE(e.dueno, 'Rambla')                        AS dueno,
               e.nombre                                           AS equipo,
               al.monto_total * pi.subtotal::numeric / NULLIF(t.suma_items, 0) AS monto
        FROM en_rango r
        JOIN alquileres al ON al.id = r.pedido_id
        JOIN alquiler_items pi ON pi.pedido_id = al.id
        JOIN equipos e ON e.id = pi.equipo_id
        JOIN tot t ON t.pedido_id = al.id
    """
    rows = conn.execute(sql, (desde, hasta)).fetchall()
    return [row_to_dict(r) for r in rows]


def agregar(filas: list[dict], modelo: dict) -> dict:
    """Agrega filas planas en el reporte. Puro (sin DB). Aplica el reparto de
    comisiones por fila y arma resumen + serie mensual + serie diaria + detalle
    por dueño. Los montos se redondean a enteros ARS al serializar."""
    total = 0.0
    por_benef: dict[str, float] = defaultdict(float)
    mes_total: dict[str, float] = defaultdict(float)
    mes_benef: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    dia_total: dict[str, float] = defaultdict(float)
    dia_benef: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    dueno_generado: dict[str, float] = defaultdict(float)
    dueno_reparto: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    dueno_equipos: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for f in filas:
        monto = float(f["monto"] or 0)
        if monto == 0:
            continue
        dueno = f["dueno"]
        fecha = str(f["fecha"])
        mes, dia = fecha[:7], fecha[:10]

        total += monto
        mes_total[mes] += monto
        dia_total[dia] += monto
        dueno_generado[dueno] += monto
        dueno_equipos[dueno][f["equipo"]] += monto

        for benef, m in repartir(dueno, monto, modelo).items():
            por_benef[benef] += m
            mes_benef[mes][benef] += m
            dia_benef[dia][benef] += m
            dueno_reparto[dueno][benef] += m

    def rd(d: dict) -> dict:
        return {k: int(round(v)) for k, v in d.items()}

    por_mes = [
        {"mes": m, "total": int(round(mes_total[m])), "por_beneficiario": rd(mes_benef[m])}
        for m in sorted(mes_total)
    ]
    por_dia = [
        {"dia": d, "total": int(round(dia_total[d])), "por_beneficiario": rd(dia_benef[d])}
        for d in sorted(dia_total)
    ]
    por_dueno = [
        {
            "dueno": dn,
            "monto_generado": int(round(dueno_generado[dn])),
            "reparto": rd(dueno_reparto[dn]),
            "equipos": sorted(
                ({"equipo": e, "monto": int(round(v))} for e, v in dueno_equipos[dn].items()),
                key=lambda x: x["monto"],
                reverse=True,
            ),
        }
        for dn in sorted(dueno_generado, key=lambda k: dueno_generado[k], reverse=True)
    ]

    return {
        "resumen": {"total": int(round(total)), "por_beneficiario": rd(por_benef)},
        "por_mes": por_mes,
        "por_dia": por_dia,
        "por_dueno": por_dueno,
    }


def liquidar(conn, desde: str, hasta: str) -> dict:
    """Reporte completo de liquidación para el rango. Carga el modelo de comisiones,
    atribuye y agrega. Devuelve también el `modelo` aplicado (para mostrarlo)."""
    modelo = cargar_modelo(conn)
    data = agregar(filas_atribucion(conn, desde, hasta), modelo)
    data["modelo"] = modelo
    # Lista ordenada de beneficiarios que aparecen en el modelo (para la UI).
    beneficiarios: list[str] = []
    for reglas in modelo.values():
        for b in reglas:
            if b not in beneficiarios:
                beneficiarios.append(b)
    data["beneficiarios"] = beneficiarios
    return data
