"""
services/nombre_service.py — Wrapper que lee de DB y persiste nombre_publico.

Encapsula la lógica de:
  1. Recolectar marca/modelo/categoría/specs de un equipo desde la DB.
  2. Llamar a `construir_nombre_publico` (función pura).
  3. Persistir en `equipos.nombre_publico` y `equipos.nombre_publico_largo`.

Lo importa quien quiera recalcular nombres:
  - Hook automático en update_equipo (recalcula 1 equipo)
  - Endpoint POST /admin/equipos/regenerar-nombres (recalcula todos)
  - Hook en setFicha / setCategorias (recalcula 1 equipo)
"""

from typing import Optional

from .nombre_builder import construir_nombre_publico


def _categorias_de(conn, equipo_id: int) -> tuple[Optional[str], Optional[str]]:
    """Devuelve (raíz, sub) — el nombre de la categoría raíz y la
    subcategoría más específica a la que pertenece el equipo.

    Si está asignado a raíz Y subcategoría (caso típico tras la
    clasificación masiva), prioriza la subcategoría como la "asignación
    real". Si solo está en la raíz, sub es None.
    """
    # Preferir subcategoría (parent_id NOT NULL) si existe.
    row = conn.execute(
        """
        WITH cat_eq AS (
            SELECT c.id, c.nombre, c.parent_id, c.prioridad, ec.orden
            FROM equipo_categorias ec
            JOIN categorias c ON c.id = ec.categoria_id
            WHERE ec.equipo_id = ?
        )
        SELECT nombre, parent_id,
               (SELECT nombre FROM categorias WHERE id = ce.parent_id) AS parent_nombre
        FROM cat_eq ce
        ORDER BY
            (parent_id IS NULL),    -- false (sub) primero, true (raíz) después
            orden, prioridad, nombre
        LIMIT 1
        """,
        (equipo_id,),
    ).fetchone()
    if not row:
        return None, None
    if row["parent_id"] is None:
        return row["nombre"], None
    return row["parent_nombre"], row["nombre"]


def _specs_en_nombre_de(conn, equipo_id: int) -> list[tuple[str, str]]:
    """Devuelve las specs marcadas `visible_en_nombre` para este equipo,
    ordenadas por prioridad. Post refactor unificar_specs_definitions:
    JOIN va sobre spec_def_id y los campos descriptivos vienen de
    spec_definitions."""
    rows = conn.execute(
        """
        SELECT sd.label, sd.spec_key, es.value, t.prioridad
        FROM equipo_specs es
        JOIN equipo_categorias ec ON ec.equipo_id = es.equipo_id
        JOIN categoria_spec_templates t
          ON t.categoria_id = ec.categoria_id AND t.spec_def_id = es.spec_def_id
        JOIN spec_definitions sd ON sd.id = es.spec_def_id
        WHERE es.equipo_id = ?
          AND t.visible_en_nombre = TRUE
        ORDER BY t.prioridad, sd.label
        """,
        (equipo_id,),
    ).fetchall()
    return [(r["label"], r["value"] or "") for r in rows]


def _ficha_template_de(conn, equipo_id: int) -> Optional[str]:
    """Lee el `nombre_publico_template` de la ficha (si existe)."""
    row = conn.execute(
        "SELECT nombre_publico_template FROM equipo_fichas WHERE equipo_id = ?",
        (equipo_id,),
    ).fetchone()
    if not row:
        return None
    return row["nombre_publico_template"]


def calcular_nombres_para(conn, equipo_id: int) -> tuple[str, str]:
    """Calcula los dos nombres públicos para un equipo (NO persiste).

    Devuelve (corto, largo). Útil para preview/dry-run."""
    eq = conn.execute(
        "SELECT id, nombre, marca, modelo, "
        "       nombre_publico_override, nombre_publico_revisado "
        "FROM equipos WHERE id = ?",
        (equipo_id,),
    ).fetchone()
    if not eq:
        raise ValueError(f"Equipo {equipo_id} no encontrado")

    raiz, sub = _categorias_de(conn, equipo_id)

    # nombre_publico_override y nombre_publico_revisado pueden no existir
    # si la columna se agrega en una migración posterior — manejamos eso.
    override = None
    try:
        override = eq["nombre_publico_override"]
    except (KeyError, IndexError):
        pass

    return construir_nombre_publico(
        nombre_interno=eq["nombre"] or "",
        marca=eq["marca"],
        modelo=eq["modelo"],
        categoria_raiz=raiz,
        categoria_sub=sub,
        specs_en_nombre=_specs_en_nombre_de(conn, equipo_id),
        template_override=_ficha_template_de(conn, equipo_id),
        nombre_publico_override=override,
    )


def actualizar_nombres_de(conn, equipo_id: int, *, commit: bool = True) -> tuple[str, str]:
    """Calcula y PERSISTE los nombres públicos de un equipo. Devuelve (corto, largo).

    Si `commit=True`, hace commit. Si False, deja la transacción abierta para
    que el caller decida (útil cuando este recálculo va dentro de otra
    transacción más grande).
    """
    corto, largo = calcular_nombres_para(conn, equipo_id)
    conn.execute(
        "UPDATE equipos SET nombre_publico = ?, nombre_publico_largo = ? WHERE id = ?",
        (corto, largo, equipo_id),
    )
    if commit:
        conn.commit()
    return corto, largo


def regenerar_nombres_todos(conn, *, dry_run: bool = False) -> dict:
    """Recalcula nombres para todos los equipos. Devuelve un reporte con
    los cambios. Si `dry_run=True`, no escribe nada.

    Returns:
        {
            "total": int,
            "cambios": [{id, nombre_actual, nombre_nuevo, largo_nuevo}, ...],
            "sin_cambios": int,
            "errores": [{id, error}, ...],
        }
    """
    rows = conn.execute(
        "SELECT id, nombre, nombre_publico FROM equipos ORDER BY id"
    ).fetchall()

    cambios: list[dict] = []
    sin_cambios = 0
    errores: list[dict] = []

    for r in rows:
        try:
            corto, largo = calcular_nombres_para(conn, r["id"])
            if corto != (r["nombre_publico"] or ""):
                cambios.append({
                    "id": r["id"],
                    "nombre_interno": r["nombre"],
                    "actual": r["nombre_publico"],
                    "nuevo": corto,
                    "largo": largo,
                })
                if not dry_run:
                    conn.execute(
                        "UPDATE equipos SET nombre_publico = ?, "
                        "nombre_publico_largo = ? WHERE id = ?",
                        (corto, largo, r["id"]),
                    )
            else:
                sin_cambios += 1
        except Exception as e:
            errores.append({"id": r["id"], "error": str(e)})

    if not dry_run:
        conn.commit()

    return {
        "total": len(rows),
        "cambios": cambios,
        "sin_cambios": sin_cambios,
        "errores": errores,
        "dry_run": dry_run,
    }
