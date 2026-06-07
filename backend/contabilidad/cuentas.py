"""Cuentas/cajas con saldo (#809) — CRUD + validación pura.

Una cuenta es una caja física/financiera (Efectivo, Banco), la "mano" de un socio
(Caja Pablo / Caja Tincho) o el fondo de la empresa (Fondo Rambla). La columna
`socio` es el puente 1:1 con `alquiler_pagos.destinatario`: la caja con
`socio='Tincho'` recibe automáticamente (vía derivación en `saldos.py`) todo pago
cobrado por Tincho. Por eso `socio` solo es válido cuando `tipo='socio'`, y solo
puede valer uno de los socios físicos.

El nombre es único SOLO entre cuentas ACTIVAS (índice parcial `cuentas_nombre_activa_uq`):
una cuenta dada de baja (baja lógica) deja de bloquear su nombre y se puede reusar.

`validar_cuenta` es pura (testeable sin DB). El resto toca la conexión.
"""

TIPOS_CUENTA = ("caja", "banco", "socio", "fondo")

# Cobradores = quiénes pueden cobrar un pago de cliente (el `destinatario` del
# pago). Fuente única — `routes.alquileres` importa de acá como DESTINATARIOS_PAGO.
# Cada uno se vincula a una caja (la columna `socio` de `cuentas` guarda a
# qué cobrador representa): Pablo/Tincho → su caja de socio; Rambla → Fondo Rambla.
COBRADORES = ("Rambla", "Tincho", "Pablo")
# Socios humanos (subconjunto): los únicos válidos para una caja de tipo 'socio'.
SOCIOS_HUMANOS = ("Pablo", "Tincho")

# Monedas soportadas. Una caja es en pesos (default) o en dólares; los saldos NO
# se mezclan entre monedas y las transferencias deben ser de la misma moneda.
MONEDAS = ("ARS", "USD")

# `moneda` se fija al crear (cambiarla con movimientos cargados rompería el saldo).
_CAMPOS_EDITABLES = ("nombre", "saldo_inicial", "fecha_apertura", "orden", "activa")


def validar_cuenta(data: dict) -> None:
    """Valida la forma de una cuenta. Lanza ValueError si es inválida. PURA.

    - `nombre`: string no vacío.
    - `tipo`: uno de TIPOS_CUENTA.
    - `socio` (= el cobrador que la caja representa): si viene, uno de COBRADORES;
      una caja de tipo 'socio' debe representar a un socio humano (Pablo/Tincho).
    - `saldo_inicial`: entero (ARS, sin centavos).
    """
    nombre = (data.get("nombre") or "").strip()
    if not nombre:
        raise ValueError("El nombre de la cuenta es obligatorio.")

    tipo = data.get("tipo")
    if tipo not in TIPOS_CUENTA:
        raise ValueError(f"Tipo de cuenta inválido (debe ser uno de {', '.join(TIPOS_CUENTA)}).")

    socio = data.get("socio")
    socio = socio.strip() if isinstance(socio, str) else socio
    if socio and socio not in COBRADORES:
        raise ValueError(f"El cobrador debe ser uno de {', '.join(COBRADORES)}.")
    # Cada tipo acota qué cobrador puede representar: socio → Pablo/Tincho;
    # fondo → Rambla (o ninguno); caja/banco → ningún cobrador.
    if tipo == "socio":
        if socio not in SOCIOS_HUMANOS:
            raise ValueError(f"Una cuenta de socio debe representar a {', '.join(SOCIOS_HUMANOS)}.")
    elif tipo == "fondo":
        if socio and socio != "Rambla":
            raise ValueError("Un fondo solo puede representar a Rambla (o a nadie).")
    elif socio:
        raise ValueError("Solo una caja de socio (Pablo/Tincho) o el fondo (Rambla) tienen cobrador.")

    si = data.get("saldo_inicial", 0)
    if si is None:
        si = 0
    if isinstance(si, bool) or not isinstance(si, int):
        raise ValueError("El saldo inicial debe ser un número entero (sin centavos).")

    moneda = data.get("moneda")
    if moneda is not None and moneda not in MONEDAS:
        raise ValueError(f"La moneda debe ser una de {', '.join(MONEDAS)}.")


def listar_cuentas(conn, incluir_inactivas: bool = False) -> list[dict]:
    """Cuentas ordenadas por `orden, nombre`. Por defecto solo las activas."""
    from database import row_to_dict

    sql = """
        SELECT id, nombre, tipo, socio, moneda, saldo_inicial, fecha_apertura, activa, orden,
               created_by, created_at, updated_by, updated_at
        FROM cuentas
    """
    if not incluir_inactivas:
        sql += " WHERE activa = TRUE"
    sql += " ORDER BY orden, nombre"
    return [row_to_dict(r) for r in conn.execute(sql).fetchall()]


def obtener_cuenta(conn, cuenta_id: int) -> dict | None:
    """Una cuenta por id (dict), o None si no existe."""
    from database import row_to_dict

    row = conn.execute(
        """SELECT id, nombre, tipo, socio, moneda, saldo_inicial, fecha_apertura, activa, orden,
                  created_by, created_at, updated_by, updated_at
           FROM cuentas WHERE id = ?""",
        (cuenta_id,),
    ).fetchone()
    return row_to_dict(row) if row else None


def crear_cuenta(conn, *, nombre, tipo, socio=None, moneda="ARS", saldo_inicial=0,
                 fecha_apertura=None, orden=0, por=None) -> dict:
    """Crea una cuenta (valida primero). Devuelve la cuenta creada.

    `fecha_apertura` None → default de la tabla (clean start 2026-06-01).
    `moneda` ARS (default) o USD.
    """
    moneda = (moneda or "ARS")
    data = {"nombre": (nombre or "").strip(), "tipo": tipo, "moneda": moneda,
            "socio": (socio or None), "saldo_inicial": int(saldo_inicial or 0)}
    validar_cuenta(data)
    socio_val = data["socio"] if tipo == "socio" else None

    cur = conn.execute(
        """INSERT INTO cuentas (nombre, tipo, socio, moneda, saldo_inicial, fecha_apertura, orden, created_by, updated_by)
           VALUES (?, ?, ?, ?, ?, COALESCE(?::date, '2026-06-01'::date), ?, ?, ?)
           RETURNING id""",
        (data["nombre"], tipo, socio_val, moneda, data["saldo_inicial"], fecha_apertura,
         int(orden or 0), por, por),
    )
    new_id = cur.fetchone()[0]
    return obtener_cuenta(conn, new_id)


def editar_cuenta(conn, cuenta_id: int, *, campos: dict, por=None) -> dict:
    """Edita una cuenta. NO permite cambiar `tipo` ni `socio` (reasignaría
    histórico). Solo toca los campos en _CAMPOS_EDITABLES presentes en `campos`.
    """
    actual = obtener_cuenta(conn, cuenta_id)
    if not actual:
        raise ValueError("La cuenta no existe.")

    # Construir el set de cambios validando el resultado final.
    propuesta = dict(actual)
    sets, params = [], []
    for campo in _CAMPOS_EDITABLES:
        if campo not in campos:
            continue
        valor = campos[campo]
        if campo == "saldo_inicial":
            valor = int(valor or 0)
        if campo == "nombre":
            valor = (valor or "").strip()
        propuesta[campo] = valor
        if campo == "fecha_apertura":
            sets.append("fecha_apertura = ?::date")
        else:
            sets.append(f"{campo} = ?")
        params.append(valor)

    if not sets:
        return actual

    validar_cuenta(propuesta)  # tipo/socio se conservan del actual → valida coherencia
    sets.append("updated_by = ?")
    params.append(por)
    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(cuenta_id)
    conn.execute(f"UPDATE cuentas SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return obtener_cuenta(conn, cuenta_id)


def desactivar_cuenta(conn, cuenta_id: int, por=None) -> dict:
    """Baja lógica de una cuenta. Falla si su saldo actual no es cero (no se da de
    baja una caja con plata adentro). Devuelve la cuenta desactivada."""
    from .saldos import saldo_de_cuenta

    actual = obtener_cuenta(conn, cuenta_id)
    if not actual:
        raise ValueError("La cuenta no existe.")
    if not actual["activa"]:
        return actual

    saldo = saldo_de_cuenta(conn, cuenta_id)
    if saldo != 0:
        raise ValueError(
            f"No se puede desactivar una cuenta con saldo (${saldo:,}). "
            "Transferí o ajustá su saldo a cero primero."
        )

    conn.execute(
        "UPDATE cuentas SET activa = FALSE, updated_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (por, cuenta_id),
    )
    return obtener_cuenta(conn, cuenta_id)
