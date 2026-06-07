"""Rendición de cuentas mensual (#809) — quién le debe a quién entre los socios.

Cruza, para un mes, lo que **le corresponde** a cada parte (del reporte de
liquidación: `reportes/liquidacion`) contra lo que **cobró** físicamente (del
ledger `alquiler_pagos`, por destinatario). Está atada al MISMO universo de
pedidos saldados del mes que el reporte → los dos lados suman el mismo total y la
rendición cierra en cero.

Las partes son tres: **Pablo** y **Tincho** (los que cobran físicamente) y
**Rambla** (el fondo de la empresa, que no cobra: su parte la tienen los socios en
exceso y hay que apartarla). El netting dice qué transferencias saldan el mes; al
registrarlas (`saldar`) se crean como `transferencia` en el libro de movimientos
con `es_rendicion=True` — NO es un sistema paralelo.

El núcleo (`_netting`) es puro y testeable sin DB.
"""

from reportes.liquidacion import SALDADO_CTE, liquidar
from reportes.cierres import rango_mes, snapshot_de, validar_mes

PARTES = ("Pablo", "Tincho", "Rambla")
_SOCIOS = ("Pablo", "Tincho")


def _netting(corresponde: dict, cobrado: dict, ya_transferido: dict) -> dict:
    """PURA. Calcula, por parte, lo que falta rendir y los movimientos sugeridos
    para saldar. Determinístico (orden fijo de PARTES).

    `pendiente[p] = le_corresponde - cobró - ya_rindió`:
      > 0  → a `p` le falta recibir.
      < 0  → `p` tiene de más y debe pagar.
    """
    saldo = {p: int(corresponde.get(p, 0)) - int(cobrado.get(p, 0)) - int(ya_transferido.get(p, 0))
             for p in PARTES}

    receptores = [[p, saldo[p]] for p in PARTES if saldo[p] > 0]
    pagadores = [[p, -saldo[p]] for p in PARTES if saldo[p] < 0]

    sugeridos = []
    i = j = 0
    while i < len(pagadores) and j < len(receptores):
        monto = min(pagadores[i][1], receptores[j][1])
        if monto > 0:
            sugeridos.append({"de": pagadores[i][0], "a": receptores[j][0], "monto": monto})
        pagadores[i][1] -= monto
        receptores[j][1] -= monto
        if pagadores[i][1] == 0:
            i += 1
        if receptores[j][1] == 0:
            j += 1

    personas = [
        {
            "persona": p,
            "le_corresponde": int(corresponde.get(p, 0)),
            "cobro": int(cobrado.get(p, 0)),
            "ya_rindio": int(ya_transferido.get(p, 0)),
            "pendiente": saldo[p],
        }
        for p in PARTES
    ]
    return {"personas": personas, "sugeridos": sugeridos}


def cobrado_por_socio(conn, desde: str, hasta: str) -> dict:
    """Σ `alquiler_pagos.monto` por destinatario, SOLO sobre los pedidos saldados
    del mes (mismo `SALDADO_CTE` que el reporte). Devuelve
    {'Pablo', 'Tincho', 'sin_asignar', 'total'}."""
    sql = f"""
        WITH {SALDADO_CTE},
        en_rango AS (
            SELECT pedido_id FROM saldado
            WHERE fecha_saldado::date BETWEEN ?::date AND ?::date
        )
        SELECT COALESCE(ap.destinatario, '__sin__') AS quien, COALESCE(SUM(ap.monto), 0) AS monto
        FROM alquiler_pagos ap
        JOIN en_rango r ON r.pedido_id = ap.pedido_id
        GROUP BY 1
    """
    out = {"Pablo": 0, "Tincho": 0, "sin_asignar": 0}
    for row in conn.execute(sql, (desde, hasta)).fetchall():
        quien, monto = row["quien"], int(row["monto"] or 0)
        if quien in _SOCIOS:
            out[quien] += monto
        else:
            out["sin_asignar"] += monto
    out["total"] = out["Pablo"] + out["Tincho"] + out["sin_asignar"]
    return out


def _parte_de_cuenta(socio, tipo, nombre) -> str | None:
    """Mapea una cuenta a su parte de rendición (Pablo/Tincho/Rambla) o None."""
    if socio in _SOCIOS:
        return socio
    if tipo == "fondo" or (nombre or "").strip().lower() == "fondo rambla":
        return "Rambla"
    return None


def ya_transferido(conn, mes: str) -> dict:
    """Neto ya rendido por parte este mes (de los movimientos `es_rendicion` no
    anulados): positivo = recibió, negativo = pagó."""
    rows = conn.execute(
        """SELECT m.monto,
                  co.socio AS o_socio, co.tipo AS o_tipo, co.nombre AS o_nombre,
                  cd.socio AS d_socio, cd.tipo AS d_tipo, cd.nombre AS d_nombre
           FROM movimientos m
           LEFT JOIN cuentas co ON co.id = m.cuenta_origen_id
           LEFT JOIN cuentas cd ON cd.id = m.cuenta_destino_id
           WHERE m.es_rendicion = TRUE AND m.anulado = FALSE AND m.rendicion_mes = ?""",
        (mes,),
    ).fetchall()
    t = {p: 0 for p in PARTES}
    for r in rows:
        monto = int(r["monto"] or 0)
        po = _parte_de_cuenta(r["o_socio"], r["o_tipo"], r["o_nombre"])
        pd = _parte_de_cuenta(r["d_socio"], r["d_tipo"], r["d_nombre"])
        if po in t:
            t[po] -= monto
        if pd in t:
            t[pd] += monto
    return t


def _movimientos_rendicion(conn, mes: str) -> list[dict]:
    """Los saldados de rendición registrados este mes (para el libro de la UI)."""
    from database import row_to_dict
    rows = conn.execute(
        """SELECT m.id, m.monto, m.fecha, m.metodo, m.nota, m.anulado, m.created_by, m.created_at,
                  co.nombre AS origen, cd.nombre AS destino
           FROM movimientos m
           LEFT JOIN cuentas co ON co.id = m.cuenta_origen_id
           LEFT JOIN cuentas cd ON cd.id = m.cuenta_destino_id
           WHERE m.es_rendicion = TRUE AND m.rendicion_mes = ?
           ORDER BY m.fecha DESC, m.id DESC""",
        (mes,),
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def cuenta_de_parte(conn, parte: str) -> int | None:
    """La cuenta que representa a una parte: Caja del socio, o el Fondo Rambla."""
    if parte in _SOCIOS:
        row = conn.execute(
            "SELECT id FROM cuentas WHERE socio = ? AND activa = TRUE", (parte,)
        ).fetchone()
    elif parte == "Rambla":
        row = conn.execute(
            """SELECT id FROM cuentas
               WHERE activa = TRUE AND (tipo = 'fondo' OR nombre = 'Fondo Rambla')
               ORDER BY id LIMIT 1"""
        ).fetchone()
    else:
        return None
    return row[0] if row else None


def rendicion(conn, mes: str) -> dict:
    """Arma la rendición completa del mes: cuánto le corresponde y cuánto cobró
    cada parte, el saldo pendiente, los movimientos sugeridos para saldar, lo ya
    rendido y las advertencias (si no cuadra contra el reporte)."""
    validar_mes(mes)
    desde, hasta = rango_mes(mes)

    snap = snapshot_de(conn, mes)
    data = snap if snap is not None else liquidar(conn, desde, hasta)
    por_benef = data["resumen"]["por_beneficiario"]
    corresponde = {p: int(por_benef.get(p, 0)) for p in PARTES}
    total_reporte = int(data["resumen"]["total"])

    cob = cobrado_por_socio(conn, desde, hasta)
    cobrado = {"Pablo": cob["Pablo"], "Tincho": cob["Tincho"], "Rambla": 0}
    ya = ya_transferido(conn, mes)

    net = _netting(corresponde, cobrado, ya)

    advertencias = []
    if cob["sin_asignar"] > 0:
        advertencias.append(
            f"Hay cobros sin asignar a un socio en pedidos de este mes "
            f"(${cob['sin_asignar']:,}). Asignales el destinatario en Pagos."
        )
    cuadra = cob["total"] == total_reporte
    if not cuadra:
        advertencias.append(
            f"Lo cobrado (${cob['total']:,}) no coincide con el total del reporte "
            f"(${total_reporte:,}) — revisá pedidos sobrepagados."
        )

    return {
        "mes": mes,
        "desde": desde,
        "hasta": hasta,
        "cerrado": snap is not None,
        "corresponde": corresponde,
        "cobrado": cobrado,
        "sin_asignar": cob["sin_asignar"],
        "ya_transferido": ya,
        "personas": net["personas"],
        "sugeridos": net["sugeridos"],
        "total_reporte": total_reporte,
        "total_cobrado": cob["total"],
        "cuadra": cuadra,
        "advertencias": advertencias,
        "movimientos": _movimientos_rendicion(conn, mes),
    }


def saldar(conn, mes: str, *, de: str, a: str, monto: int,
           metodo=None, fecha=None, nota=None, por=None) -> dict:
    """Registra un saldado de rendición: una transferencia entre las cajas de las
    partes, marcada `es_rendicion`. Reusa el libro de movimientos (no duplica)."""
    validar_mes(mes)
    if de not in PARTES or a not in PARTES:
        raise ValueError("Las partes de la rendición son Pablo, Tincho o Rambla.")
    if de == a:
        raise ValueError("El que paga y el que recibe no pueden ser la misma parte.")
    monto = int(monto or 0)
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero.")

    origen = cuenta_de_parte(conn, de)
    destino = cuenta_de_parte(conn, a)
    if not origen or not destino:
        raise ValueError("Falta la caja de alguna de las partes (Caja del socio o Fondo Rambla).")

    from contabilidad.movimientos import crear_movimiento

    return crear_movimiento(
        conn, tipo="transferencia", monto=monto,
        cuenta_origen_id=origen, cuenta_destino_id=destino,
        metodo=metodo, fecha=fecha,
        nota=nota or f"Rendición {mes}: {de} → {a}", por=por,
        es_rendicion=True, rendicion_mes=mes,
    )
