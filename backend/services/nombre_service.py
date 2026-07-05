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
    from services.categorias import categorias_de_equipos, categoria_por_id, root_of_categoria
    cat_map = categorias_de_equipos(conn, [equipo_id])
    cats = cat_map.get(equipo_id, [])
    if not cats:
        return None, None
    first = cats[0]
    if first["parent_id"] is None:
        return first["nombre"], None
    root_id = root_of_categoria(conn, first["id"])
    root = categoria_por_id(conn, root_id) if root_id else None
    root_name = root["nombre"] if root else None
    return root_name, first["nombre"]


def _specs_en_nombre_de(conn, equipo_id: int) -> list[dict]:
    """Specs `en_nombre=true` del equipo para el render del nombre. Puerta única:
    `services.specs.specs_en_nombre_de_equipo` (resuelve por `categoria_specs`,
    no por el árbol de catálogo — arregla nombres vacíos por mal-tageo). El
    builder los usa en `_render_template`: cada `{spec:Label}` busca por label."""
    from services.specs import specs_en_nombre_de_equipo
    return specs_en_nombre_de_equipo(conn, equipo_id)


def _ficha_template_de(conn, equipo_id: int) -> Optional[str]:
    """Lee el `nombre_publico_template` de la ficha (si existe) — template
    por-equipo, fallback cuando la categoría no tiene molde."""
    row = conn.execute(
        "SELECT nombre_publico_template FROM equipo_fichas WHERE equipo_id = %s",
        (equipo_id,),
    ).fetchone()
    if not row:
        return None
    return row["nombre_publico_template"]


def _categoria_template_de(conn, equipo_id: int) -> Optional[str]:
    """Lee el molde de nombre de la CATEGORÍA DE SPECS del equipo
    (`categorias.nombre_publico_template` de la categoría cuyo nombre ==
    `equipos.categoria_specs`). Es la fuente VIVA del nombre: se define una vez
    por categoría y aplica a todos sus equipos (a diferencia del template por-
    ficha, que es una excepción por-equipo). None si el equipo no tiene
    `categoria_specs`, si su nombre no resuelve, o si la categoría no tiene molde."""
    cs_row = conn.execute(
        "SELECT categoria_specs FROM equipos WHERE id = %s", (equipo_id,)
    ).fetchone()
    categoria_specs = cs_row["categoria_specs"] if cs_row else None
    if not categoria_specs:
        return None
    from services.categorias import buscar_id_por_nombre
    cat_id = buscar_id_por_nombre(conn, categoria_specs)
    if not cat_id:
        return None
    row = conn.execute(
        "SELECT nombre_publico_template FROM categorias WHERE id = %s", (cat_id,)
    ).fetchone()
    return row["nombre_publico_template"] if row else None


def calcular_nombres_para(conn, equipo_id: int) -> tuple[str, str]:
    """Calcula los dos nombres públicos para un equipo (NO persiste).

    Devuelve (corto, largo). Útil para preview/dry-run."""
    eq = conn.execute(
        f"SELECT id, nombre, {marca_subquery('equipos')}, modelo, "
        "       nombre_publico_override, nombre_publico_revisado "
        "FROM equipos WHERE id = %s",
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
        categoria_template=_categoria_template_de(conn, equipo_id),
        template_override=_ficha_template_de(conn, equipo_id),
        nombre_publico_override=override,
    )


def actualizar_nombres_de(conn, equipo_id: int, *, commit: bool = True) -> tuple[str, str]:
    """Calcula y PERSISTE los nombres públicos de un equipo. Devuelve (corto, largo).
    No escribe si ambos valores ya coinciden con los guardados — se llama desde
    8 hooks distintos (setFicha, setCategorias, update_equipo, specs, ...) y la
    mayoría de las veces el nombre no cambia; un UPDATE incondicional generaba
    dead rows en `equipos` en cada guardado sin cambio real (mismo criterio que
    ya usa `regenerar_nombres_todos` para decidir sus "cambios").

    Si `commit=True`, hace commit. Si False, deja la transacción abierta para
    que el caller decida (útil cuando este recálculo va dentro de otra
    transacción más grande).
    """
    corto, largo = calcular_nombres_para(conn, equipo_id)

    actual = conn.execute(
        "SELECT nombre_publico, nombre_publico_largo FROM equipos WHERE id = %s",
        (equipo_id,),
    ).fetchone()
    if actual and (actual["nombre_publico"] or "") == corto and (actual["nombre_publico_largo"] or "") == largo:
        if commit:
            conn.commit()
        return corto, largo

    conn.execute(
        "UPDATE equipos SET nombre_publico = %s, nombre_publico_largo = %s WHERE id = %s",
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
                        "UPDATE equipos SET nombre_publico = %s, "
                        "nombre_publico_largo = %s WHERE id = %s",
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
