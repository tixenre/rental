"""Escritura de categorías de gasto (#809) — única puerta de mutación.

Tabla `gasto_categorias` (creada en Fase 1). Los gastos (`movimientos.tipo='gasto'`)
referencian una categoría por FK. Lectura → `queries/categorias.py`.
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


def crear_categoria(conn, nombre) -> dict:
    """Crea una categoría de gasto (idempotente por nombre). Devuelve la fila."""
    from database import row_to_dict

    nombre = validar_categoria(nombre)
    conn.execute(
        """INSERT INTO gasto_categorias (nombre, orden)
           VALUES (%s, 50) ON CONFLICT (nombre) DO NOTHING""",
        (nombre,),
    )
    row = conn.execute(
        "SELECT id, nombre, activa, orden FROM gasto_categorias WHERE nombre = %s", (nombre,)
    ).fetchone()
    return row_to_dict(row)
