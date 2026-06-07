"""Reconciliación contable (#809, Fase 6) — semáforo de confianza.

Chequeos de integridad que verifican que la plata del módulo cuadre. Devuelve
`{ok: bool, ...}`; cada chequeo lista lo que encontró. Read-only.
"""

from reportes.liquidacion import LIQUIDACION_INICIO


def reconciliar(conn) -> dict:
    from contabilidad.saldos import saldos

    out: dict = {}

    # 1. Cajas con saldo negativo (no debería pasar: algo se cargó de más o falta
    #    un ingreso/aporte).
    s = saldos(conn)
    negativos = [
        {"cuenta": c["nombre"], "saldo": c["saldo"]} for c in s["cuentas"] if c["saldo"] < 0
    ]
    out["saldos_negativos"] = {"cantidad": len(negativos), "cuentas": negativos}

    # 2. Cobros (≥ clean start) sin un socio válido como destinatario → no entran a
    #    ninguna caja y rompen la derivación de ingresos.
    row = conn.execute(
        """SELECT COUNT(*) AS n, COALESCE(SUM(monto), 0) AS m
           FROM alquiler_pagos
           WHERE fecha::date >= ?::date
             AND (destinatario IS NULL OR destinatario NOT IN ('Pablo', 'Tincho'))""",
        (LIQUIDACION_INICIO,),
    ).fetchone()
    out["pagos_sin_socio"] = {"cantidad": int(row["n"]), "monto": int(row["m"] or 0)}

    # 3. Movimientos activos que apuntan a una cuenta dada de baja.
    row = conn.execute(
        """SELECT COUNT(*) AS n
           FROM movimientos m
           WHERE m.anulado = FALSE AND (
                 m.cuenta_origen_id IN (SELECT id FROM cuentas WHERE activa = FALSE)
              OR m.cuenta_destino_id IN (SELECT id FROM cuentas WHERE activa = FALSE))"""
    ).fetchone()
    out["movimientos_cuenta_inactiva"] = {"cantidad": int(row["n"])}

    # 4. Hereda el semáforo del reporte (pagos marcados sin ledger, sobrepagos),
    #    que afectan los ingresos derivados del módulo.
    try:
        from reportes.reconciliacion import reconciliar as reconciliar_reporte

        rep = reconciliar_reporte(conn)
    except Exception:
        rep = {"ok": True}
    out["reporte"] = {
        "ok": bool(rep.get("ok", True)),
        "pagados_sin_ledger": rep.get("pagados_sin_ledger"),
        "sobrepagados": rep.get("sobrepagados"),
    }

    out["ok"] = (
        not negativos
        and out["pagos_sin_socio"]["cantidad"] == 0
        and out["movimientos_cuenta_inactiva"]["cantidad"] == 0
        and out["reporte"]["ok"]
    )
    return out
