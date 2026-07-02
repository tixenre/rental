"""Escritura del libro de movimientos (#809) — única puerta de mutación.

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
saldo de cada cuenta se deriva de estos movimientos + esos cobros
(`queries/saldos.py`).

`validar_estructura_movimiento` es pura (testeable sin DB). El resto toca la
conexión. La plata nunca se borra: `anular_movimiento` hace soft-delete con motivo.
Lectura → `queries/movimientos.py`.

**Ambigüedad conocida, sin resolver a propósito (auditoría 2026-07-02):** la tabla de
arriba dice contra qué CANTIDAD de cuentas es válido cada tipo, pero no restringe el
TIPO de cuenta (`caja`/`banco`/`fondo` vs `socio`, cuenta corriente). Una
`transferencia` DEBE poder tocar una cuenta `socio` (así funciona
`commands/rendicion.py::saldar`, que arma transferencias Caja↔Fondo Rambla), y un
`ajuste` contra una cuenta `socio` puede ser una corrección legítima de arranque de
cuenta corriente — así que no se agregó una validación dura acá. Ojo: usar
`retiro`/`aporte`/`gasto` contra una cuenta `socio` (en vez de una caja real) mueve el
signo de forma CONTRAINTUITIVA respecto del nombre del tipo (ver la fórmula de
cuenta corriente en `queries/saldos.py`: un "retiro" contra la cuenta de un socio en
realidad BAJA su deuda, no la sube, porque `egresos` resta en esa fórmula). El
comportamiento actual (permitido, sin restricción) está fijado por
`test_movimiento_tipo_vs_tipo_cuenta` — si algún día se agrega la validación dura,
ese test debe fallar y avisar que es un cambio deliberado, no una regresión.
"""

from contabilidad.constants import METODOS_MOVIMIENTO, TIPOS_MOVIMIENTO
from contabilidad.queries.movimientos import listar_movimientos, obtener_movimiento

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


def _validar_cuentas_y_categoria(conn, cuenta_origen_id, cuenta_destino_id, categoria_id) -> None:
    """Existencia+actividad de las cuentas, misma moneda si hay origen y destino,
    categoría existente+activa. Toca DB (a diferencia de `validar_estructura_movimiento`,
    que es pura). La usan `crear_movimiento` Y `editar_movimiento` — antes solo la
    tenía crear, así que editar podía dejar un movimiento apuntando a una cuenta
    inactiva/inexistente o mezclando monedas (auditoría 2026-07-02)."""
    validas = _cuentas_validas(conn)
    for cid in (cuenta_origen_id, cuenta_destino_id):
        if cid and cid not in validas:
            raise ValueError("La cuenta indicada no existe o está inactiva.")
    # Una transferencia/ajuste entre dos cuentas debe ser de la misma moneda
    # (no hay conversión automática; los saldos no se mezclan).
    if cuenta_origen_id and cuenta_destino_id:
        rows = conn.execute(
            "SELECT id, moneda FROM cuentas WHERE id IN (%s, %s)",
            (cuenta_origen_id, cuenta_destino_id),
        ).fetchall()
        mon = {r["id"]: r["moneda"] for r in rows}
        if mon.get(cuenta_origen_id) != mon.get(cuenta_destino_id):
            raise ValueError("No se puede transferir entre cuentas de distinta moneda.")
    if categoria_id:
        ok = conn.execute(
            "SELECT 1 FROM gasto_categorias WHERE id = %s AND activa = TRUE", (categoria_id,)
        ).fetchone()
        if not ok:
            raise ValueError("La categoría indicada no existe o está inactiva.")


def _mes_de_fecha(fecha) -> str:
    if not fecha:
        from services.fechas import mes_actual_ar
        return mes_actual_ar()
    return str(fecha)[:7]


# Namespace del advisory lock para serializar cerrar_mes/reabrir_mes contra
# crear/editar/anular movimiento (y actualizar_comprobante) del mismo mes
# contable. Arbitrario y privado de este flujo — mismo patrón que
# _ADVISORY_NS_PEDIDO (routes/alquileres/core.py, 5390412) y
# _ADVISORY_NS_ESTUDIO (routes/estudio.py, 5390413); siguiente número libre.
_ADVISORY_NS_CONTAB_MES = 5390420


def _lock_mes(conn, mes: str) -> None:
    """xact-scoped (se libera solo al commit/rollback de `conn`): sin esto, un
    `cerrar_mes` puede leer los movimientos de un mes en T0 y commitear su foto
    DESPUÉS de que otro request haya insertado un movimiento con fecha de ese
    mismo mes (que pasó `_exigir_mes_abierto` porque el cierre todavía no había
    commiteado) — el mes queda "cerrado" con una foto que no incluye ese
    movimiento, que además ya no se puede tocar (auditoría 2026-07-02)."""
    try:
        anio, mo = mes.split("-")
        key = int(anio) * 100 + int(mo)   # 'YYYY-MM' → YYYYMM, key natural
    except (ValueError, AttributeError):
        key = 0
    conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_ADVISORY_NS_CONTAB_MES, key))


def _exigir_mes_abierto(conn, fecha) -> None:
    """Traba tocar un movimiento cuyo mes contable está cerrado (#809 Fase 6)."""
    from contabilidad.queries.cierres import mes_cerrado

    mes = _mes_de_fecha(fecha)
    _lock_mes(conn, mes)
    if mes_cerrado(conn, mes):
        raise ValueError(
            f"El mes {mes} está cerrado. Reabrilo desde Rendición para tocar movimientos de esa fecha."
        )


def crear_movimiento(conn, *, tipo, monto, cuenta_origen_id=None, cuenta_destino_id=None,
                     categoria_id=None, metodo=None, fecha=None, nota=None, beneficiario=None,
                     por=None, es_rendicion=False, rendicion_mes=None) -> dict:
    """Crea un movimiento (valida estructura + existencia de cuentas/categoría).
    `fecha` None → hoy. `es_rendicion`/`rendicion_mes` marcan un saldado de
    rendición entre socios (lo usa `commands/rendicion.py::saldar`, no la UI
    general). Devuelve el movimiento con nombres resueltos."""
    monto = int(monto or 0)
    validar_estructura_movimiento(tipo, monto, cuenta_origen_id, cuenta_destino_id, categoria_id)
    _validar_metodo(metodo)
    _exigir_mes_abierto(conn, fecha)
    _validar_cuentas_y_categoria(conn, cuenta_origen_id, cuenta_destino_id, categoria_id)

    beneficiario = (beneficiario or "").strip() or None
    cur = conn.execute(
        """INSERT INTO movimientos
               (tipo, monto, cuenta_origen_id, cuenta_destino_id, categoria_id,
                metodo, fecha, nota, beneficiario, es_rendicion, rendicion_mes, created_by, updated_by)
           VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s::date, CURRENT_DATE), %s, %s, %s, %s, %s, %s)
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
    _validar_cuentas_y_categoria(
        conn, propuesta.get("cuenta_origen_id"),
        propuesta.get("cuenta_destino_id"), propuesta.get("categoria_id"),
    )

    sets, params = [], []
    for k in _CAMPOS_EDITABLES:
        if k not in campos:
            continue
        if k == "fecha":
            sets.append("fecha = %s::date")
        elif k == "monto":
            sets.append("monto = %s")
            campos[k] = int(campos[k] or 0)
        elif k == "beneficiario":
            sets.append("beneficiario = %s")
            campos[k] = (campos[k] or "").strip() or None  # mismo saneo que al crear
        else:
            sets.append(f"{k} = %s")
        params.append(campos[k])
    if not sets:
        return actual
    sets.append("updated_by = %s")
    params.append(por)
    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(mov_id)
    conn.execute(f"UPDATE movimientos SET {', '.join(sets)} WHERE id = %s", tuple(params))
    return obtener_movimiento(conn, mov_id)


def actualizar_comprobante(conn, mov_id: int, *, key: str, por=None) -> dict:
    """Persiste la key del comprobante ya subido a storage (el upload en sí es
    infra HTTP, se queda en el route). Pasa por el mismo candado que
    crear/editar/anular — antes el route hacía un UPDATE directo, saltándose
    `_exigir_mes_abierto` y el chequeo de `anulado` (auditoría 2026-07-02)."""
    actual = obtener_movimiento(conn, mov_id)
    if not actual:
        raise ValueError("El movimiento no existe.")
    if actual["anulado"]:
        raise ValueError("No se puede adjuntar un comprobante a un movimiento anulado.")
    _exigir_mes_abierto(conn, actual["fecha"])
    conn.execute(
        "UPDATE movimientos SET comprobante_url = NULL, comprobante_key = %s, "
        "updated_by = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (key, por, mov_id),
    )
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
           SET anulado = TRUE, anulado_por = %s, anulado_at = CURRENT_TIMESTAMP, anulado_motivo = %s
           WHERE id = %s""",
        (por, motivo, mov_id),
    )
    return obtener_movimiento(conn, mov_id)
