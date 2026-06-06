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
from database import marca_subquery


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


def _specs_en_nombre_de(conn, equipo_id: int) -> list[dict]:
    """Devuelve los specs del equipo marcados `en_nombre=true` en el registry,
    con sus valores actuales del equipo + metadata para el render.

    Lee directo de `spec_definitions` (single source of truth) + LEFT JOIN
    con `equipo_specs` para traer el valor. No depende de
    `categoria_spec_templates` (que puede estar incompleto tras migraciones
    del registry — mismo bug que resolvimos en PR #410 para listar templates).

    Cada item: `{label, spec_key, value, tipo, unidad, tabla_columnas,
    output_config}`. Ordenados por `sd.prioridad`.

    El builder los usa en `_render_template`: cada placeholder `{spec:Label}`
    busca por label y aplica `render_spec_placeholder` (que respeta
    `output_config.name_format` y formatea tipos no-string).
    """
    import json as _json
    rows = conn.execute(
        """
        SELECT
          sd.label, sd.spec_key, sd.tipo, sd.unidad,
          sd.tabla_columnas, sd.output_config,
          COALESCE(es.value, '') AS value,
          COALESCE(sd.prioridad, 100) AS prioridad
        FROM spec_definitions sd
        JOIN equipo_categorias ec ON ec.equipo_id = ?
        JOIN categorias c ON c.id = ec.categoria_id
        LEFT JOIN equipo_specs es
          ON es.equipo_id = ec.equipo_id AND es.spec_def_id = sd.id
        WHERE COALESCE(sd.en_nombre, FALSE) = TRUE
          AND sd.categoria_raiz_id IS NOT NULL
          AND (sd.categoria_raiz_id = c.id OR sd.categoria_raiz_id = c.parent_id)
        ORDER BY COALESCE(sd.prioridad, 100), sd.label
        """,
        (equipo_id,),
    ).fetchall()
    out: list[dict] = []
    seen_labels: set[str] = set()
    for r in rows:
        label = r["label"]
        # Dedupe por label (un equipo puede estar en varias cats de la misma raíz)
        key = (label or "").lower().strip()
        if key in seen_labels:
            continue
        seen_labels.add(key)
        cols = r["tabla_columnas"]
        if isinstance(cols, str):
            try:
                cols = _json.loads(cols)
            except Exception:
                cols = None
        oc = r["output_config"]
        if isinstance(oc, str):
            try:
                oc = _json.loads(oc)
            except Exception:
                oc = None
        out.append({
            "label": label,
            "spec_key": r["spec_key"],
            "value": r["value"] or "",
            "tipo": r["tipo"],
            "unidad": r["unidad"],
            "tabla_columnas": cols,
            "output_config": oc,
        })
    return out


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
        f"SELECT id, nombre, {marca_subquery('equipos')}, modelo, "
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
