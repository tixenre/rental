"""Categorías de gasto (#809) — rubros editables para clasificar egresos.

Tabla `gasto_categorias` (creada en Fase 1). Acá viven el listado y el alta. Los
gastos (`movimientos.tipo='gasto'`) referencian una categoría por FK.
"""


def validar_categoria(nombre) -> str:
    """Normaliza y valida el nombre de una categoría. Devuelve el nombre limpio.
    Lanza ValueError si es inválido. PURA."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre de la categoría es obligatorio.")
    if len(nombre) > 80:
        raise ValueError("El nombre de la categoría es demasiado largo.")
    return nombre


def listar_categorias(conn, incluir_inactivas: bool = False) -> list[dict]:
    """Categorías de gasto ordenadas por `orden, nombre`."""
    from database import row_to_dict

    sql = "SELECT id, nombre, activa, orden FROM gasto_categorias"
    if not incluir_inactivas:
        sql += " WHERE activa = TRUE"
    sql += " ORDER BY orden, nombre"
    return [row_to_dict(r) for r in conn.execute(sql).fetchall()]


def crear_categoria(conn, nombre) -> dict:
    """Crea una categoría de gasto (idempotente por nombre). Devuelve la fila."""
    from database import row_to_dict

    nombre = validar_categoria(nombre)
    conn.execute(
        """INSERT INTO gasto_categorias (nombre, orden)
           VALUES (?, 50) ON CONFLICT (nombre) DO NOTHING""",
        (nombre,),
    )
    row = conn.execute(
        "SELECT id, nombre, activa, orden FROM gasto_categorias WHERE nombre = ?", (nombre,)
    ).fetchone()
    return row_to_dict(row)
