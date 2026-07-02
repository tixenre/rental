"""commands/crud.py — Alta/baja/modificación de categorías individuales.

Para asignar/desasignar categorías A equipos (la tabla `equipo_categorias`),
ver `commands/assignment.py`. Todo lo de acá valida vía `queries/validation.py`
antes de tocar la fila (nombre único, profundidad ≤ 3 niveles, sin ciclos)."""
import logging

from services.nombre_service import actualizar_nombres_de
from ..queries.ancestry import expandir_a_descendientes, buscar_id_por_nombre
from ..errors import ErrorValidacion, CategoriaNoExiste
from ..queries.validation import (
    validar_profundidad, detectar_ciclo, validar_nombre_unico, validar_existe,
)

logger = logging.getLogger(__name__)


def _validar_padre(conn, parent_id: int, node_id: int | None = None) -> None:
    """Valida que `parent_id` exista y que asignarlo no exceda 3 niveles.
    `node_id` es el nodo que se está moviendo (None si es una creación)."""
    validar_existe(conn, parent_id)
    validar_profundidad(conn, parent_id, node_id=node_id)


def crear(conn, nombre: str, prioridad: int = 100, parent_id: int | None = None) -> dict:
    """Crea una categoría raíz (parent_id=None) o hija. Nombre único
    case-insensitive (levanta NombreDuplicado si choca); si lleva parent_id,
    valida que exista y que no exceda 3 niveles de profundidad."""
    validar_nombre_unico(conn, nombre)

    if parent_id is not None:
        _validar_padre(conn, parent_id)

    cur = conn.execute("""
        INSERT INTO categorias (nombre, prioridad, parent_id)
        VALUES (%s, %s, %s)
        RETURNING id, nombre, prioridad, parent_id
    """, (nombre, prioridad, parent_id))
    row = cur.fetchone()
    return {
        "id": row["id"], "nombre": row["nombre"],
        "prioridad": row["prioridad"], "parent_id": row["parent_id"], "total": 0,
    }


def _side_effects(conn, cid: int, nombre_publico_template: str | None) -> int:
    """Side effect best-effort tras actualizar una categoría: regenerar
    nombres públicos si cambió el template. Nunca aborta la operación
    principal."""
    nombres_regen = 0
    if nombre_publico_template is not None:
        sub_ids = expandir_a_descendientes(conn, cid)
        placeholders = ",".join(["%s"] * len(sub_ids))
        eq_rows = conn.execute(
            f"SELECT DISTINCT ec.equipo_id FROM equipo_categorias ec WHERE ec.categoria_id IN ({placeholders})",
            sub_ids,
        ).fetchall()
        for r in eq_rows:
            try:
                actualizar_nombres_de(conn, r["equipo_id"], commit=False)
                nombres_regen += 1
            except Exception:
                logger.warning(
                    "actualizar_nombres_de falló para equipo %s tras cambio de template cat %s",
                    r["equipo_id"], cid, exc_info=True,
                )
    return nombres_regen


def actualizar(conn, cid: int, *, nombre: str | None = None,
               prioridad: int | None = None, visible: bool | None = None,
               parent_id: int | None = None, set_parent_null: bool = False,
               nombre_publico_template: str | None = None) -> dict:
    """Actualiza los campos provistos (None = no tocar). `set_parent_null=True`
    desengancha la categoría a raíz (gana sobre `parent_id` si ambos vienen).
    Cambio de template dispara side effect best-effort — ver `_side_effects`.
    Levanta ErrorValidacion si no se pasó ningún campo."""
    validar_existe(conn, cid)

    sets, vals = [], []
    nuevo_nombre = None
    if nombre is not None:
        nuevo_nombre = nombre.strip()
        if not nuevo_nombre:
            raise ErrorValidacion("El nombre no puede estar vacío")
        sets.append("nombre = %s"); vals.append(nuevo_nombre)
    if prioridad is not None:
        sets.append("prioridad = %s"); vals.append(int(prioridad))
    if visible is not None:
        sets.append("visible = %s"); vals.append(bool(visible))
    if nombre_publico_template is not None:
        tpl = nombre_publico_template.strip()
        sets.append("nombre_publico_template = %s"); vals.append(tpl or None)
    if set_parent_null:
        sets.append("parent_id = NULL")
    elif parent_id is not None:
        if parent_id == cid:
            raise ErrorValidacion("Una categoría no puede ser su propio padre")
        _validar_padre(conn, parent_id, node_id=cid)
        detectar_ciclo(conn, cid, parent_id)
        sets.append("parent_id = %s"); vals.append(int(parent_id))
    if not sets:
        raise ErrorValidacion("Sin cambios")

    if nuevo_nombre is not None:
        validar_nombre_unico(conn, nuevo_nombre, exclude_id=cid)

    vals.append(cid)
    conn.execute(f"UPDATE categorias SET {', '.join(sets)} WHERE id = %s", tuple(vals))
    nombres_regen = _side_effects(conn, cid, nombre_publico_template)
    return {"ok": True, "nombres_regenerados": nombres_regen}


def eliminar(conn, cid: int) -> None:
    """Borra una categoría. Rechaza (ErrorValidacion) si tiene sub-categorías:
    `categorias.parent_id` es ON DELETE SET NULL, así que sin este guard las
    hijas quedarían huerfanadas a raíz en silencio — hay que reasignarlas o
    borrarlas primero, a propósito."""
    validar_existe(conn, cid)
    tiene_hijas = conn.execute(
        "SELECT 1 FROM categorias WHERE parent_id = %s LIMIT 1", (cid,)
    ).fetchone()
    if tiene_hijas:
        raise ErrorValidacion(
            "No se puede eliminar: tiene sub-categorías. "
            "Reasignalas a otro padre o eliminalas primero."
        )
    conn.execute("DELETE FROM categorias WHERE id = %s", (cid,))


def reordenar(conn, ids: list[int]) -> int:
    """Reasigna prioridad secuencial (10, 20, 30, ...) según el orden de
    `ids`. Ids repetidos se dedupean (gana la primera aparición). Valida que
    todos existan antes de escribir nada — 2 round-trips, no 2N."""
    seen: set[int] = set()
    ordered = [cid for cid in ids if not (cid in seen or seen.add(cid))]
    if not ordered:
        return 0

    rows = conn.execute(
        "SELECT id FROM categorias WHERE id = ANY(%s)", (ordered,)
    ).fetchall()
    existentes = {r["id"] for r in rows}
    faltante = next((cid for cid in ordered if cid not in existentes), None)
    if faltante is not None:
        raise CategoriaNoExiste(f"Categoría {faltante} no existe")

    values_sql = ", ".join(["(%s::int, %s::int)"] * len(ordered))
    params = [p for idx, cid in enumerate(ordered) for p in (cid, (idx + 1) * 10)]
    conn.execute(
        f"""UPDATE categorias AS c SET prioridad = v.prioridad
            FROM (VALUES {values_sql}) AS v(id, prioridad)
            WHERE c.id = v.id""",
        params,
    )
    return len(ordered)


def actualizar_ranking(conn, cid: int, score: int, pedidos: int, ingreso: int) -> None:
    """Escribe métricas de popularidad ya calculadas (no calcula nada acá —
    ver `services/ranking_service.py`, que es quien decide score/pedidos/
    ingreso y llama a esto por cada categoría recalculada)."""
    conn.execute(
        """UPDATE categorias
           SET popularidad_score = %s,
               cant_pedidos = %s,
               ingreso_total_ars = %s,
               ranking_actualizado = CURRENT_TIMESTAMP
           WHERE id = %s""",
        (score, pedidos, ingreso, cid),
    )


def crear_si_no_existe(conn, nombre: str, prioridad: int = 100,
                       visible: bool = True, grupo_visual: str | None = None,
                       nombre_publico_template: str | None = None) -> tuple[int, bool]:
    """Crea la categoría si no existe. Returns (id, was_inserted).
    Never raises NombreDuplicado. Útil para seed/import donde la
    idempotencia es por nombre."""
    cur = conn.execute(
        """INSERT INTO categorias (nombre, prioridad, parent_id, visible,
                                   grupo_visual, nombre_publico_template)
           VALUES (%s, %s, NULL, %s, %s, %s)
           ON CONFLICT (nombre) DO NOTHING
           RETURNING id""",
        (nombre, prioridad, visible, grupo_visual, nombre_publico_template),
    )
    row = cur.fetchone()
    if row:
        return row["id"], True
    cid = buscar_id_por_nombre(conn, nombre)
    return cid, False


def asignar_padre_si_no_tiene(conn, nombre: str, parent_id: int) -> None:
    """Asigna parent_id por nombre solo si la categoría aún no tiene padre.
    Útil para seed/import donde se bootstrap la jerarquía sin pisar
    cambios hechos en la web."""
    conn.execute(
        "UPDATE categorias SET parent_id = %s WHERE nombre = %s AND parent_id IS NULL",
        (parent_id, nombre),
    )
