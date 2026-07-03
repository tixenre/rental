"""Lectura de cuentas/cajas (#809). Nunca muta — ver `commands/cuentas.py`."""


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
           FROM cuentas WHERE id = %s""",
        (cuenta_id,),
    ).fetchone()
    return row_to_dict(row) if row else None
