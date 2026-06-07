"""Libro de movimientos (#809) — el registro único de la plata que se mueve.

Cada fila mueve plata entre cuentas (o desde/hacia afuera). El **tipo** define qué
cuentas se usan:

| tipo          | origen | destino | categoría | qué es                                   |
|---------------|--------|---------|-----------|------------------------------------------|
| gasto         | ✓      | —       | ✓         | sale plata de una caja (con rubro)       |
| transferencia | ✓      | ✓       | —         | mueve plata entre dos cajas (cuadra)     |
| retiro        | ✓      | —       | —         | un socio saca su plata                   |
| aporte        | —      | ✓       | —         | un socio mete plata                      |
| ajuste        | ✓ o —  | ✓ o —   | —         | conciliación manual (con nota)           |

Los ingresos por alquiler NO viven acá: derivan de `alquiler_pagos` (Fase 1). El
saldo de cada cuenta se deriva de estos movimientos + esos cobros (`saldos.py`).

`validar_estructura_movimiento` es pura (testeable sin DB). El resto toca la
conexión. La plata nunca se borra: `anular_movimiento` hace soft-delete con motivo.
"""

TIPOS_MOVIMIENTO = ("gasto", "transferencia", "retiro", "aporte", "ajuste")
METODOS_MOVIMIENTO = ("transferencia", "efectivo")

# Campos que se pueden editar de un movimiento ya creado (el tipo no se cambia:
# cambiar de gasto a transferencia es otro movimiento, se anula y se rehace).
_CAMPOS_EDITABLES = ("monto", "cuenta_origen_id", "cuenta_destino_id", "categoria_id",
                     "metodo", "fecha", "nota", "beneficiario")


def validar_estructura_movimiento(tipo, monto, origen, destino, categoria_id) -> None:
    """Valida la coherencia tipo↔cuentas↔categoría de un movimiento. PURA.
    No chequea existencia en DB (eso lo hace `crear_movimiento`)."""
    if tipo not in TIPOS_MOVIMIENTO:
        raise ValueError(f"Tipo de movimiento inválido (debe ser uno de {', '.join(TIPOS_MOVIMIENTO)}).")
    if not isinstance(monto, int) or isinstance(monto, bool) or monto <= 0:
        raise ValueError("El monto debe ser un entero positivo (pesos, sin centavos).")
    if origen and destino and origen == destino:
        raise ValueError("El origen y el destino no pueden ser la misma cuenta.")

    if tipo == "gasto":
        if not origen:
            raise ValueError("Un gasto necesita la caja de la que sale la plata.")
        if destino:
            raise ValueError("Un gasto no tiene cuenta destino.")
        if not categoria_id:
            raise ValueError("Un gasto necesita una categoría.")
    elif tipo == "transferencia":
        if not (origen and destino):
            raise ValueError("Una transferencia necesita cuenta de origen y de destino.")
    elif tipo == "retiro":
        if not origen or destino:
            raise ValueError("Un retiro sale de una caja (origen), sin destino.")
    elif tipo == "aporte":
        if not destino or origen:
            raise ValueError("Un aporte entra a una caja (destino), sin origen.")
    elif tipo == "ajuste":
        if not (origen or destino):
            raise ValueError("Un ajuste necesita al menos una cuenta (origen o destino).")

    if tipo != "gasto" and categoria_id:
        raise ValueError("Solo los gastos llevan categoría.")


def _validar_metodo(metodo):
    if metodo and metodo not in METODOS_MOVIMIENTO:
        raise ValueError(f"Método inválido (debe ser uno de {', '.join(METODOS_MOVIMIENTO)}).")


def _cuentas_validas(conn) -> set[int]:
    rows = conn.execute("SELECT id FROM cuentas WHERE activa = TRUE").fetchall()
    return {r["id"] for r in rows}


def _mes_de_fecha(fecha) -> str:
    from datetime import date
    if not fecha:
        return date.today().strftime("%Y-%m")
    return str(fecha)[:7]


def _exigir_mes_abierto(conn, fecha) -> None:
    """Traba tocar un movimiento cuyo mes contable está cerrado (#809 Fase 6)."""
    from contabilidad.cierres import mes_cerrado

    mes = _mes_de_fecha(fecha)
    if mes_cerrado(conn, mes):
        raise ValueError(
            f"El mes {mes} está cerrado. Reabrilo desde Rendición para tocar movimientos de esa fecha."
        )


def listar_movimientos(conn, *, tipo=None, cuenta_id=None, categoria_id=None,
                       desde=None, hasta=None, beneficiario=None,
                       incluir_anulados=False, limit=500) -> list[dict]:
    """Movimientos con nombres de cuenta/categoría resueltos, filtrables. Más
    nuevos primero. Por defecto excluye los anulados."""
    from database import row_to_dict

    sql = """
        SELECT m.id, m.tipo, m.monto, m.cuenta_origen_id, m.cuenta_destino_id,
               m.categoria_id, m.metodo, m.fecha, m.nota, m.beneficiario,
               m.comprobante_url, m.es_rendicion, m.rendicion_mes,
               m.anulado, m.anulado_motivo, m.created_by, m.created_at,
               co.nombre AS cuenta_origen_nombre,
               cd.nombre AS cuenta_destino_nombre,
               COALESCE(co.moneda, cd.moneda) AS moneda,
               gc.nombre AS categoria_nombre
        FROM movimientos m
        LEFT JOIN cuentas co ON co.id = m.cuenta_origen_id
        LEFT JOIN cuentas cd ON cd.id = m.cuenta_destino_id
        LEFT JOIN gasto_categorias gc ON gc.id = m.categoria_id
        WHERE 1=1
    """
    params: list = []
    if not incluir_anulados:
        sql += " AND m.anulado = FALSE"
    if tipo:
        sql += " AND m.tipo = ?"
        params.append(tipo)
    if cuenta_id:
        sql += " AND (m.cuenta_origen_id = ? OR m.cuenta_destino_id = ?)"
        params.extend([cuenta_id, cuenta_id])
    if categoria_id:
        sql += " AND m.categoria_id = ?"
        params.append(categoria_id)
    if beneficiario:
        sql += " AND m.beneficiario = ?"
        params.append(beneficiario)
    if desde:
        sql += " AND m.fecha >= ?::date"
        params.append(desde)
    if hasta:
        sql += " AND m.fecha <= ?::date"
        params.append(hasta)
    sql += " ORDER BY m.fecha DESC, m.id DESC LIMIT ?"
    params.append(min(int(limit or 500), 2000))
    return [row_to_dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def obtener_movimiento(conn, mov_id: int) -> dict | None:
    from database import row_to_dict
    row = conn.execute(
        """SELECT id, tipo, monto, cuenta_origen_id, cuenta_destino_id, categoria_id,
                  metodo, fecha, nota, beneficiario, comprobante_url, comprobante_key, es_rendicion,
                  rendicion_mes, anulado, anulado_motivo, created_by, created_at
           FROM movimientos WHERE id = ?""",
        (mov_id,),
    ).fetchone()
    return row_to_dict(row) if row else None


def crear_movimiento(conn, *, tipo, monto, cuenta_origen_id=None, cuenta_destino_id=None,
                     categoria_id=None, metodo=None, fecha=None, nota=None, beneficiario=None,
                     por=None, es_rendicion=False, rendicion_mes=None) -> dict:
    """Crea un movimiento (valida estructura + existencia de cuentas/categoría).
    `fecha` None → hoy. `es_rendicion`/`rendicion_mes` marcan un saldado de
    rendición entre socios (lo usa `rendicion.saldar`, no la UI general).
    Devuelve el movimiento con nombres resueltos."""
    monto = int(monto or 0)
    validar_estructura_movimiento(tipo, monto, cuenta_origen_id, cuenta_destino_id, categoria_id)
    _validar_metodo(metodo)
    _exigir_mes_abierto(conn, fecha)

    validas = _cuentas_validas(conn)
    for cid in (cuenta_origen_id, cuenta_destino_id):
        if cid and cid not in validas:
            raise ValueError("La cuenta indicada no existe o está inactiva.")
    # Una transferencia/ajuste entre dos cuentas debe ser de la misma moneda
    # (no hay conversión automática; los saldos no se mezclan).
    if cuenta_origen_id and cuenta_destino_id:
        rows = conn.execute(
            "SELECT id, moneda FROM cuentas WHERE id IN (?, ?)",
            (cuenta_origen_id, cuenta_destino_id),
        ).fetchall()
        mon = {r["id"]: r["moneda"] for r in rows}
        if mon.get(cuenta_origen_id) != mon.get(cuenta_destino_id):
            raise ValueError("No se puede transferir entre cuentas de distinta moneda.")
    if categoria_id:
        ok = conn.execute(
            "SELECT 1 FROM gasto_categorias WHERE id = ? AND activa = TRUE", (categoria_id,)
        ).fetchone()
        if not ok:
            raise ValueError("La categoría indicada no existe o está inactiva.")

    beneficiario = (beneficiario or "").strip() or None
    cur = conn.execute(
        """INSERT INTO movimientos
               (tipo, monto, cuenta_origen_id, cuenta_destino_id, categoria_id,
                metodo, fecha, nota, beneficiario, es_rendicion, rendicion_mes, created_by, updated_by)
           VALUES (?, ?, ?, ?, ?, ?, COALESCE(?::date, CURRENT_DATE), ?, ?, ?, ?, ?, ?)
           RETURNING id""",
        (tipo, monto, cuenta_origen_id, cuenta_destino_id, categoria_id,
         metodo, fecha, nota, beneficiario, bool(es_rendicion), rendicion_mes, por, por),
    )
    new_id = cur.fetchone()[0]
    movs = listar_movimientos(conn, incluir_anulados=True)
    for m in movs:
        if m["id"] == new_id:
            return m
    return obtener_movimiento(conn, new_id)


def editar_movimiento(conn, mov_id: int, *, campos: dict, por=None) -> dict:
    """Edita un movimiento NO anulado. Revalida la estructura con el resultado.
    El `tipo` no se cambia."""
    actual = obtener_movimiento(conn, mov_id)
    if not actual:
        raise ValueError("El movimiento no existe.")
    if actual["anulado"]:
        raise ValueError("No se puede editar un movimiento anulado.")
    _exigir_mes_abierto(conn, actual["fecha"])
    if "fecha" in campos:
        _exigir_mes_abierto(conn, campos["fecha"])

    propuesta = dict(actual)
    for k in _CAMPOS_EDITABLES:
        if k in campos:
            propuesta[k] = campos[k]
    monto = int(propuesta.get("monto") or 0)
    validar_estructura_movimiento(
        actual["tipo"], monto, propuesta.get("cuenta_origen_id"),
        propuesta.get("cuenta_destino_id"), propuesta.get("categoria_id"),
    )
    _validar_metodo(propuesta.get("metodo"))

    sets, params = [], []
    for k in _CAMPOS_EDITABLES:
        if k not in campos:
            continue
        if k == "fecha":
            sets.append("fecha = ?::date")
        elif k == "monto":
            sets.append("monto = ?")
            campos[k] = int(campos[k] or 0)
        else:
            sets.append(f"{k} = ?")
        params.append(campos[k])
    if not sets:
        return actual
    sets.append("updated_by = ?")
    params.append(por)
    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(mov_id)
    conn.execute(f"UPDATE movimientos SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return obtener_movimiento(conn, mov_id)


def anular_movimiento(conn, mov_id: int, *, motivo, por=None) -> dict:
    """Soft-delete: marca el movimiento como anulado (la plata nunca se borra).
    Exige un motivo. Un movimiento anulado deja de contar para los saldos."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Para anular un movimiento hay que indicar un motivo.")
    actual = obtener_movimiento(conn, mov_id)
    if not actual:
        raise ValueError("El movimiento no existe.")
    if actual["anulado"]:
        return actual
    _exigir_mes_abierto(conn, actual["fecha"])
    conn.execute(
        """UPDATE movimientos
           SET anulado = TRUE, anulado_por = ?, anulado_at = CURRENT_TIMESTAMP, anulado_motivo = ?
           WHERE id = ?""",
        (por, motivo, mov_id),
    )
    return obtener_movimiento(conn, mov_id)


def gastos_por_categoria(conn, desde=None, hasta=None) -> list[dict]:
    """Σ de gastos en PESOS (no anulados) agrupados por categoría, en la ventana.
    Para el tablero / P&L (que es en ARS). Filtra por la moneda de la caja de
    origen: un gasto pagado desde una caja USD NO se suma al P&L en pesos (no se
    mezclan monedas). Más gastado primero."""
    from database import row_to_dict
    sql = """
        SELECT gc.nombre AS categoria, COALESCE(SUM(m.monto), 0) AS monto
        FROM movimientos m
        JOIN gasto_categorias gc ON gc.id = m.categoria_id
        JOIN cuentas co ON co.id = m.cuenta_origen_id
        WHERE m.tipo = 'gasto' AND m.anulado = FALSE AND co.moneda = 'ARS'
    """
    params: list = []
    if desde:
        sql += " AND m.fecha >= ?::date"
        params.append(desde)
    if hasta:
        sql += " AND m.fecha <= ?::date"
        params.append(hasta)
    sql += " GROUP BY gc.nombre ORDER BY monto DESC"
    return [row_to_dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def cobros_mensuales(conn, desde=None, hasta=None, cobrador=None) -> list[dict]:
    """Cobros de pedidos (de `alquiler_pagos`) agregados por mes — una línea por
    mes con el total cobrado. Es la cara READ-ONLY de los cobros dentro de la vista
    unificada de movimientos: la plata entra, pero se carga desde el pedido (Pagos),
    no se edita acá. Mismo recorte que los saldos (≥ clean start, destinatario
    asignado). Si `cobrador` se pasa, solo los de ese cobrador. Devuelve filas
    {mes:'YYYY-MM', monto, cantidad} más nuevas primero."""
    from database import row_to_dict
    from reportes.liquidacion import LIQUIDACION_INICIO

    sql = """
        SELECT to_char(fecha, 'YYYY-MM') AS mes,
               COALESCE(SUM(monto), 0) AS monto,
               COUNT(*) AS cantidad
        FROM alquiler_pagos
        WHERE destinatario IS NOT NULL AND fecha::date >= ?::date
    """
    params: list = [LIQUIDACION_INICIO]
    if cobrador:
        sql += " AND destinatario = ?"
        params.append(cobrador)
    if desde:
        sql += " AND fecha::date >= ?::date"
        params.append(desde)
    if hasta:
        sql += " AND fecha::date <= ?::date"
        params.append(hasta)
    sql += " GROUP BY 1 ORDER BY 1 DESC"
    return [row_to_dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def beneficiarios_usados(conn) -> list[str]:
    """Beneficiarios ya usados (distintos, no anulados), para el autocompletado del
    formulario — así "Jimena" se elige en vez de reescribirse."""
    rows = conn.execute(
        """SELECT DISTINCT beneficiario FROM movimientos
           WHERE beneficiario IS NOT NULL AND beneficiario <> '' AND NOT anulado
           ORDER BY beneficiario"""
    ).fetchall()
    return [r["beneficiario"] for r in rows]
