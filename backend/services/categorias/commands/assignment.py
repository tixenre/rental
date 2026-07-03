"""commands/assignment.py — Asignar/desasignar categorías A equipos
(la tabla `equipo_categorias`). Para CRUD de la categoría en sí (nombre,
padre, prioridad), ver `commands/crud.py`.

Las funciones `_masivo` no lanzan si `equipo_ids` viene vacío: son no-op
(devuelven sin tocar la tabla) en vez de fallar, así los callers no necesitan
chequear `if ids:` antes de llamarlas."""
import logging

from services.nombre_service import actualizar_nombres_de
from ..queries.ancestry import expandir_a_ancestros
from ..queries.validation import validar_existe

logger = logging.getLogger(__name__)


def _expandir_y_ordenar(conn, ids: list[int]) -> list[int]:
    """Expande a ancestros y preserva orden: las del input primero, las agregadas al final."""
    expanded = expandir_a_ancestros(conn, ids)
    seen: set[int] = set()
    ordered: list[int] = []
    for raw in ids:
        try:
            iv = int(raw)
        except (TypeError, ValueError):
            continue
        if iv not in seen:
            seen.add(iv)
            ordered.append(iv)
    for iv in expanded:
        if iv not in seen:
            seen.add(iv)
            ordered.append(iv)
    return ordered


def asignar_categorias(conn, equipo_id: int, categoria_ids: list[int]) -> None:
    """Reemplaza todas las categorías de un equipo. Expande ancestros.
    Side effect: regenera el nombre público (best-effort)."""
    ordered = _expandir_y_ordenar(conn, categoria_ids)

    conn.execute("DELETE FROM equipo_categorias WHERE equipo_id = %s", (equipo_id,))
    for orden, cid_int in enumerate(ordered):
        conn.execute(
            "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (equipo_id, categoria_id) DO UPDATE SET orden = EXCLUDED.orden",
            (equipo_id, cid_int, orden),
        )

    try:
        actualizar_nombres_de(conn, equipo_id, commit=False)
    except Exception:
        logger.warning("actualizar_nombres_de falló para equipo %s", equipo_id, exc_info=True)


def set_categoria_masivo(conn, equipo_ids: list[int], categoria_id: int) -> None:
    """Reemplaza las categorías de N equipos con el set expandido de categoria_id.
    No-op si equipo_ids está vacío (valida categoria_id igual, antes de mirar
    equipo_ids, para levantar CategoriaNoExiste consistentemente)."""
    validar_existe(conn, categoria_id)
    if not equipo_ids:
        return
    ancestor_ids = expandir_a_ancestros(conn, [categoria_id])

    placeholders = ",".join(["%s"] * len(equipo_ids))
    conn.execute(
        f"DELETE FROM equipo_categorias WHERE equipo_id IN ({placeholders})",
        equipo_ids,
    )
    conn.executemany(
        "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s, %s, %s)",
        [(eid, cid_int, orden) for eid in equipo_ids for orden, cid_int in enumerate(ancestor_ids)],
    )


def add_categoria_masivo(conn, equipo_ids: list[int], categoria_id: int) -> None:
    """Agrega categoria_id (expandida) a N equipos sin borrar las existentes.
    No-op si equipo_ids está vacío (valida categoria_id igual)."""
    validar_existe(conn, categoria_id)
    if not equipo_ids:
        return
    ancestor_ids = expandir_a_ancestros(conn, [categoria_id])

    conn.executemany(
        "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) "
        "VALUES (%s, %s, %s) "
        "ON CONFLICT (equipo_id, categoria_id) DO NOTHING",
        [(eid, cid_int, orden) for eid in equipo_ids for orden, cid_int in enumerate(ancestor_ids)],
    )


def remove_categoria_masivo(conn, equipo_ids: list[int], categoria_id: int) -> None:
    """Saca UNA categoría de N equipos sin tocar las otras categorías.
    No-op si equipo_ids está vacío. No valida que categoria_id exista —
    borrar una asignación a una categoría ya borrada es un no-op válido."""
    if not equipo_ids:
        return
    placeholders = ",".join(["%s"] * len(equipo_ids))
    conn.execute(
        f"DELETE FROM equipo_categorias WHERE categoria_id = %s AND equipo_id IN ({placeholders})",
        [categoria_id, *equipo_ids],
    )


def copiar_categorias(conn, source_id: int, target_id: int) -> None:
    """Copia las categorías de un equipo a otro (duplicar equipo)."""
    cats = conn.execute(
        "SELECT categoria_id, orden FROM equipo_categorias WHERE equipo_id=%s", (source_id,)
    ).fetchall()
    conn.executemany(
        "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s, %s, %s)",
        [(target_id, cat["categoria_id"], cat["orden"]) for cat in cats],
    )
