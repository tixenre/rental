"""queries/ancestry.py — Traversal del árbol (ancestros/descendientes) y
lecturas de la relación equipo↔categoria (`equipo_categorias`).

Lookups directos sobre `categorias` sola (sin traversal, sin join a equipos)
viven en read.py."""
from typing import Literal


def expandir_a_ancestros(conn, ids: list[int]) -> list[int]:
    """Dado un set de IDs, devuelve esos IDs MÁS todos sus ancestros (padre,
    abuelo, ...) hasta la raíz. Usado antes de escribir en equipo_categorias:
    si el equipo se asigna a una hoja, también queda asignado a sus padres
    (así el filtro por categoría padre lo encuentra)."""
    if not ids:
        return []
    out: set[int] = set()
    pending: list[int] = []
    for iv in ids:
        if iv not in out:
            out.add(iv)
            pending.append(iv)

    while pending:
        placeholders = ",".join(["%s"] * len(pending))
        rows = conn.execute(
            f"SELECT id, parent_id FROM categorias WHERE id IN ({placeholders})",
            pending,
        ).fetchall()
        next_pending: list[int] = []
        for row in rows:
            pid = row["parent_id"]
            if pid is not None and pid not in out:
                out.add(pid)
                next_pending.append(pid)
        pending = next_pending

    return list(out)


def expandir_a_descendientes(conn, categoria_id: int) -> list[int]:
    """Devuelve todos los IDs de categorías descendientes (incluyendo la propia).
    Solo acepta ID numérico. Para lookup por nombre usar buscar_id_por_nombre antes."""
    rows = conn.execute("""
        WITH RECURSIVE sub AS (
            SELECT id FROM categorias WHERE id = %s
            UNION ALL
            SELECT c.id FROM categorias c JOIN sub ON c.parent_id = sub.id
        )
        SELECT id FROM sub
    """, (categoria_id,)).fetchall()
    return [r["id"] for r in rows]


def root_of_categoria(conn, categoria_id: int) -> int | None:
    """Devuelve el ID de la categoría raíz del árbol al que pertenece
    categoria_id. None si la categoría no existe."""
    row = conn.execute("""
        WITH RECURSIVE up AS (
            SELECT id, parent_id FROM categorias WHERE id = %s
            UNION
            SELECT c.id, c.parent_id FROM categorias c
            JOIN up ON up.parent_id = c.id
        )
        SELECT id FROM up WHERE parent_id IS NULL LIMIT 1
    """, (categoria_id,)).fetchone()
    return row["id"] if row else None


def expandir_a_ancestros_por_equipo(conn, equipo_ids: list[int]) -> dict[int, list[int]]:
    """Returns {equipo_id: [ancestor_id, ...]} for all ancestors of each
    category assigned to each equipo. More efficient than per-equipo
    expandir_a_ancestros calls for batch operations."""
    if not equipo_ids:
        return {}
    rows = conn.execute("""
        WITH RECURSIVE up AS (
            SELECT ec.equipo_id, c.id, c.parent_id
            FROM equipo_categorias ec
            JOIN categorias c ON c.id = ec.categoria_id
            WHERE ec.equipo_id = ANY(%s)
            UNION
            SELECT up.equipo_id, p.id, p.parent_id
            FROM categorias p
            JOIN up ON up.parent_id = p.id
        )
        SELECT DISTINCT equipo_id, id FROM up
    """, (equipo_ids,)).fetchall()
    result: dict[int, set[int]] = {}
    for r in rows:
        result.setdefault(r["equipo_id"], set()).add(r["id"])
    return {k: list(v) for k, v in result.items()}


def buscar_id_por_nombre(conn, nombre: str) -> int | None:
    """Devuelve el ID de una categoría por su nombre exacto, o None si no existe."""
    row = conn.execute(
        "SELECT id FROM categorias WHERE nombre = %s", (nombre,)
    ).fetchone()
    return row["id"] if row else None


def categoria_ids_de_equipo(conn, equipo_id: int) -> list[int]:
    """IDs de categoría de UN equipo, en orden (`orden` de equipo_categorias).

    Solo IDs — para el objeto completo {id, nombre, parent_id} de varios
    equipos a la vez, usar `categorias_de_equipos` (batch, justo abajo)."""
    rows = conn.execute(
        "SELECT categoria_id FROM equipo_categorias WHERE equipo_id = %s ORDER BY orden",
        (equipo_id,),
    ).fetchall()
    return [r["categoria_id"] for r in rows]


_CATEGORIAS_DE_EQUIPOS_SQL = """
    SELECT ec.equipo_id, c.id, c.nombre, c.parent_id
    FROM equipo_categorias ec
    JOIN categorias c ON c.id = ec.categoria_id
    WHERE ec.equipo_id = ANY(%s)
    ORDER BY ec.equipo_id, ec.orden
"""


def query_categorias_de_equipos(equipo_ids: list[int]) -> tuple[str, tuple] | None:
    """SQL + params de `categorias_de_equipos` — separado de la ejecución para
    que un caller que ya corre OTRAS queries independientes (ej. el pipeline
    de `services.catalogo.proyeccion.proyectar_lista`, #1240) pueda incluir
    esta en el mismo lote sin reimplementar el SQL. `None` si `equipo_ids`
    está vacío."""
    if not equipo_ids:
        return None
    return _CATEGORIAS_DE_EQUIPOS_SQL, (equipo_ids,)


def shape_categorias_de_equipos_rows(rows) -> dict[int, list[dict]]:
    """Da forma `{equipo_id: [{id, nombre, parent_id}, ...]}` a filas YA
    obtenidas de `query_categorias_de_equipos`."""
    result: dict[int, list[dict]] = {}
    for r in rows:
        result.setdefault(r["equipo_id"], []).append({
            "id": r["id"], "nombre": r["nombre"], "parent_id": r["parent_id"],
        })
    return result


def categorias_de_equipos(conn, equipo_ids: list[int]) -> dict[int, list[dict]]:
    """Returns {equipo_id: [{id, nombre, parent_id}, ...]} for each equipo.
    Useful for attaching category info to equipos lists.

    Batch, objeto completo por categoría. Para un solo equipo y solo los IDs
    (más liviano), usar `categoria_ids_de_equipo` (arriba)."""
    query = query_categorias_de_equipos(equipo_ids)
    if query is None:
        return {}
    sql, params = query
    rows = conn.execute(sql, params).fetchall()
    return shape_categorias_de_equipos_rows(rows)


def sql_filtro_categoria(table_alias: Literal["e"] = "e") -> str:
    """Fragmento SQL para filtrar equipos sin categoría. Se compone en el WHERE
    de list_equipos."""
    return f" AND NOT EXISTS (SELECT 1 FROM equipo_categorias ec WHERE ec.equipo_id = {table_alias}.id)"


def sql_filtro_equipos_por_categoria(table_alias: Literal["e"], sub_ids: list[int]) -> tuple[str, list[int]]:
    """SQL fragment + params para filtrar equipos que pertenecen a una o varias
    categorías. Se compone en el WHERE de list_equipos.

    Uso:
        fragment, params = sql_filtro_equipos_por_categoria("e", [1, 2, 3])
        base_sql += fragment
        params += params
    """
    placeholders = ",".join(["%s"] * len(sub_ids))
    return (
        f" AND {table_alias}.id IN (SELECT ec.equipo_id FROM equipo_categorias ec WHERE ec.categoria_id IN ({placeholders}))",
        sub_ids,
    )
