"""queries/read.py — Direct lookups on `categorias` (by id/nombre, no traversal).

Functions here never join `equipo_categorias` — a category's own fields only.
For anything that reads the equipo↔categoria relationship (single equipo or
batch), see `categoria_ids_de_equipo` / `categorias_de_equipos` in ancestry.py.
Tree traversal (ancestors/descendants) lives in ancestry.py; audit-style
aggregate reports (equipos sin categoría, categorías sin equipos) in audit.py.
"""


def categoria_por_id(conn, cid: int) -> dict | None:
    """Returns {id, nombre, parent_id} for a single category, or None."""
    row = conn.execute(
        "SELECT id, nombre, parent_id FROM categorias WHERE id = %s", (cid,)
    ).fetchone()
    return {"id": row["id"], "nombre": row["nombre"], "parent_id": row["parent_id"]} if row else None


def categoria_por_nombre(conn, nombre: str) -> dict | None:
    """Returns {id, nombre, parent_id} for a category by exact name, or None."""
    row = conn.execute(
        "SELECT id, nombre, parent_id FROM categorias WHERE nombre = %s", (nombre,)
    ).fetchone()
    return {"id": row["id"], "nombre": row["nombre"], "parent_id": row["parent_id"]} if row else None


def categorias_por_ids(conn, ids: list[int]) -> list[dict]:
    """Returns [{id, nombre, prioridad, parent_id}, ...] for given IDs.
    Empty list if ids is empty or no matches."""
    if not ids:
        return []
    ph = ",".join(["%s"] * len(ids))
    rows = conn.execute(
        f"SELECT id, nombre, COALESCE(prioridad, 999) AS prioridad FROM categorias WHERE id IN ({ph})",
        ids,
    ).fetchall()
    return [{"id": r["id"], "nombre": r["nombre"], "prioridad": r["prioridad"]} for r in rows]


def categoria_nombres_por_ids(conn, ids: list[int]) -> dict[int, str]:
    """Returns {id: nombre, ...} for fast lookups of category names."""
    if not ids:
        return {}
    ph = ",".join(["%s"] * len(ids))
    rows = conn.execute(
        f"SELECT id, nombre FROM categorias WHERE id IN ({ph})",
        list(ids),
    ).fetchall()
    return {r["id"]: r["nombre"] for r in rows}


def listar_categorias_flat(conn) -> list[dict]:
    """All categories flat: {id, nombre, total, prioridad, parent_id}, ordered.

    ⚠️ `total` viene de la columna `categorias.total` (#131, ranking), que HOY
    no la escribe nada — `commands/crud.py::actualizar_ranking` solo toca
    popularidad_score/cant_pedidos/ingreso_total_ars. En la práctica `total`
    siempre da 0 acá. Si necesitás un conteo real de equipos por categoría,
    usar `queries/tree.py::listar_arbol_admin` (lo calcula en vivo con
    COUNT/JOIN). No "arreglar" escribiendo la columna sin confirmar primero
    si algo de afuera ya la lee esperando que sea 0 (proyeccion.py del
    catálogo público consume este `total` tal cual)."""
    rows = conn.execute(
        "SELECT id, nombre, COALESCE(total, 0) AS total, prioridad, parent_id "
        "FROM categorias ORDER BY COALESCE(prioridad, 999), nombre"
    ).fetchall()
    return [
        {
            "id": r["id"], "nombre": r["nombre"],
            "total": r["total"], "prioridad": r["prioridad"],
            "parent_id": r["parent_id"],
        }
        for r in rows
    ]
