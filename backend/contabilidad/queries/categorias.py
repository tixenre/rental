"""Lectura de categorías de gasto (#809). Nunca muta — ver `commands/categorias.py`."""


def listar_categorias(conn, incluir_inactivas: bool = False) -> list[dict]:
    """Categorías de gasto ordenadas por `orden, nombre`."""
    from database import row_to_dict

    sql = "SELECT id, nombre, activa, orden FROM gasto_categorias"
    if not incluir_inactivas:
        sql += " WHERE activa = TRUE"
    sql += " ORDER BY orden, nombre"
    return [row_to_dict(r) for r in conn.execute(sql).fetchall()]
