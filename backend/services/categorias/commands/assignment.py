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
    Solo escribe lo que cambió (diff contra el estado actual): el form de
    equipo llama esto en cada save aunque no se haya tocado la sección de
    categorías, y un DELETE+INSERT incondicional generaba dead rows en cada
    guardado sin cambios reales.
    Side effect: regenera el nombre público (best-effort), solo si algo cambió."""
    ordered = _expandir_y_ordenar(conn, categoria_ids)

    actuales = conn.execute(
        "SELECT categoria_id, orden FROM equipo_categorias WHERE equipo_id = %s",
        (equipo_id,),
    ).fetchall()
    orden_actual = {row["categoria_id"]: row["orden"] for row in actuales}
    nuevo_set = {cid: orden for orden, cid in enumerate(ordered)}

    a_borrar = [cid for cid in orden_actual if cid not in nuevo_set]
    a_escribir = [
        (cid, orden) for cid, orden in nuevo_set.items() if orden_actual.get(cid) != orden
    ]

    if not a_borrar and not a_escribir:
        return

    if a_borrar:
        placeholders = ",".join(["%s"] * len(a_borrar))
        conn.execute(
            f"DELETE FROM equipo_categorias WHERE equipo_id = %s AND categoria_id IN ({placeholders})",
            (equipo_id, *a_borrar),
        )
    for cid_int, orden in a_escribir:
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
