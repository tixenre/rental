"""Asignación de specs a categorías (templates) (#501 — extraído del god-module
`routes/specs.py`).

CRUD de las asignaciones de `spec_definitions` a categorías (resumen, listado por
categoría, huérfanas, asignar/actualizar/borrar/reordenar) con sus flags de
visibilidad/prioridad/destacado. Registra sus rutas en el router compartido del
paquete `routes.specs`. `_require_admin` (guard) vive en `core`.
"""
import logging
from typing import Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel

from database import get_db, row_to_dict
from routes.specs.core import router, _require_admin

logger = logging.getLogger(__name__)


# Asignación de una spec_def a una categoría con flags propios.
class SpecAssignmentInput(BaseModel):
    spec_def_id: int
    prioridad: int = 100
    destacado: bool = False
    obligatorio: bool = False
    visible_en_card: bool = False
    visible_en_filtros: bool = False
    visible_en_nombre: bool = False
    ayuda: Optional[str] = None   # override de ayuda por categoría
    rol_compatibilidad: Optional[str] = None  # NULL | "contenedor" | "contenido"


class SpecAssignmentUpdate(BaseModel):
    prioridad: Optional[int] = None
    destacado: Optional[bool] = None
    obligatorio: Optional[bool] = None
    visible_en_card: Optional[bool] = None
    visible_en_filtros: Optional[bool] = None
    visible_en_nombre: Optional[bool] = None
    ayuda: Optional[str] = None
    rol_compatibilidad: Optional[str] = None


# ── CRUD: Asignaciones de spec_definitions a categorías ────────────────

@router.get("/admin/spec-templates/resumen")
def resumen_templates(request: Request):
    """Devuelve conteo de specs por categoría para el overview del editor."""
    _require_admin(request)
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT categoria_id, COUNT(*) as total
            FROM categoria_spec_templates
            GROUP BY categoria_id
            """
        ).fetchall()
        return {r["categoria_id"]: r["total"] for r in rows}


@router.get("/admin/categorias/{categoria_id}/spec-templates")
def listar_templates(categoria_id: int, request: Request):
    """Lista TODOS los specs disponibles para una categoría.

    Simplificación: lee directo de `spec_definitions` filtrando por
    `categoria_raiz_id`. No depende de `categoria_spec_templates` (que
    causaba bugs cuando las asignaciones quedaban incompletas tras
    migraciones del registry expandido).

    Si el caller pasa una sub-categoría, sube por la jerarquía
    (`WITH RECURSIVE`) para llegar a la raíz y leer todos sus specs.

    Los flags devueltos (destacado, visible_en_card, visible_en_filtros,
    visible_en_nombre) se derivan del spec_def directamente
    (favorito, en_filtros, en_nombre) — son la metadata canónica del
    registry. Si en el futuro se necesita sobrescribir flags por
    sub-categoría se reactiva el JOIN a `categoria_spec_templates`."""
    _require_admin(request)
    with get_db() as conn:
        # Subir a la raíz si recibimos una sub-cat.
        raiz_row = conn.execute(
            """
            WITH RECURSIVE up AS (
                SELECT id, parent_id FROM categorias WHERE id = %s
                UNION
                SELECT c.id, c.parent_id
                FROM categorias c JOIN up ON up.parent_id = c.id
            )
            SELECT id FROM up WHERE parent_id IS NULL LIMIT 1
            """,
            (categoria_id,),
        ).fetchone()
        raiz_id = row_to_dict(raiz_row)["id"] if raiz_row else categoria_id

        rows = conn.execute(
            """
            SELECT
              sd.id AS spec_def_id,
              sd.spec_key, sd.label, sd.tipo, sd.unidad, sd.unidad_id, sd.enum_options,
              sd.tabla_columnas, sd.output_config,
              COALESCE(sd.prioridad, 100) AS prioridad,
              COALESCE(sd.favorito, FALSE) AS visible_en_card,
              COALESCE(sd.en_filtros, FALSE) AS visible_en_filtros,
              COALESCE(sd.en_nombre, FALSE) AS visible_en_nombre,
              COALESCE(sd.favorito, FALSE) AS destacado,
              FALSE AS obligatorio,
              sd.ayuda,
              COALESCE(sd.es_compatibilidad, FALSE) AS es_compatibilidad,
              COALESCE(sd.compatibilidad_modo, 'exacta') AS compatibilidad_modo,
              sd.rol_compatibilidad
            FROM spec_definitions sd
            WHERE sd.categoria_raiz_id = %s
            ORDER BY COALESCE(sd.prioridad, 100), sd.label
            """,
            (raiz_id,),
        ).fetchall()

        items = []
        for r in rows:
            d = row_to_dict(r)
            # Compat con el shape que el frontend espera (id del template +
            # categoria_id). Como no hay template propiamente dicho, usamos
            # null para id y echamos categoria_id como espejo del input.
            d["id"] = None
            d["categoria_id"] = categoria_id
            items.append(d)
        return {"items": items}


@router.get("/admin/categorias/{categoria_id}/spec-templates/orphans")
def listar_orphan_specs(categoria_id: int, request: Request):
    """Devuelve spec_definitions cargadas en equipo_specs de equipos de
    esta categoría que NO están asignadas al template de la categoría.

    Útil para sugerir al admin formalizar specs custom (que ya tienen
    valores en equipos pero no están en el template oficial).

    Devuelve: [{spec_def_id, spec_key, label, count_equipos, sample_values[≤3]}].
    """
    _require_admin(request)
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
              es.spec_def_id,
              sd.spec_key,
              sd.label,
              COUNT(*) AS count_equipos,
              (
                SELECT array_agg(DISTINCT inner_es.value)
                FROM equipo_specs inner_es
                JOIN equipos inner_e ON inner_e.id = inner_es.equipo_id
                JOIN equipo_categorias inner_ec ON inner_ec.equipo_id = inner_e.id
                WHERE inner_es.spec_def_id = es.spec_def_id
                  AND inner_ec.categoria_id = %s
                  AND inner_e.eliminado_at IS NULL
                LIMIT 3
              ) AS sample_values
            FROM equipo_specs es
            JOIN equipos e ON e.id = es.equipo_id
            JOIN equipo_categorias ec ON ec.equipo_id = e.id
            JOIN spec_definitions sd ON sd.id = es.spec_def_id
            WHERE ec.categoria_id = %s
              AND e.eliminado_at IS NULL
              AND NOT EXISTS (
                SELECT 1 FROM categoria_spec_templates t
                WHERE t.categoria_id = ec.categoria_id
                  AND t.spec_def_id = es.spec_def_id
              )
            GROUP BY es.spec_def_id, sd.spec_key, sd.label
            ORDER BY COUNT(*) DESC
        """, (categoria_id, categoria_id)).fetchall()
        return [
            {
                "spec_def_id": r["spec_def_id"],
                "spec_key": r["spec_key"],
                "label": r["label"],
                "count_equipos": r["count_equipos"],
                "sample_values": [str(v) for v in (r["sample_values"] or [])][:3],
            }
            for r in rows
        ]


@router.post("/admin/categorias/{categoria_id}/spec-templates", status_code=201)
def asignar_spec_a_categoria(categoria_id: int, payload: SpecAssignmentInput, request: Request):
    """Asigna una spec_definition existente a una categoría con flags propios.
    Para crear una spec nueva globalmente usar POST /admin/spec-definitions
    y después asignar acá."""
    _require_admin(request)
    with get_db() as conn:
        cat = conn.execute(
            "SELECT id FROM categorias WHERE id = %s", (categoria_id,)
        ).fetchone()
        if not cat:
            raise HTTPException(404, f"Categoría {categoria_id} no existe")
        sd = conn.execute(
            "SELECT id, label FROM spec_definitions WHERE id = %s", (payload.spec_def_id,)
        ).fetchone()
        if not sd:
            raise HTTPException(404, f"Spec definition {payload.spec_def_id} no existe")
        if payload.rol_compatibilidad and payload.rol_compatibilidad not in ("contenedor", "contenido"):
            raise HTTPException(400, "rol_compatibilidad debe ser 'contenedor' o 'contenido' (o null).")
        try:
            # legacy: los flags visible_en_card/visible_en_filtros/destacado de
            # categoria_spec_templates ya no controlan el catálogo público (se leen
            # de spec_definitions desde Fase 6d). Se elimina en 6f junto al CRUD de templates.
            cur = conn.execute(
                """
                INSERT INTO categoria_spec_templates
                  (categoria_id, spec_def_id, prioridad, destacado, obligatorio,
                   visible_en_card, visible_en_filtros, visible_en_nombre, ayuda,
                   rol_compatibilidad)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    categoria_id,
                    payload.spec_def_id,
                    payload.prioridad,
                    payload.destacado,
                    payload.obligatorio,
                    payload.visible_en_card,
                    payload.visible_en_filtros,
                    payload.visible_en_nombre,
                    payload.ayuda,
                    payload.rol_compatibilidad,
                ),
            )
            new_id = cur.fetchone()[0]
            conn.commit()
            return {"id": new_id, **payload.model_dump()}
        except Exception as e:
            conn.rollback()
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                raise HTTPException(
                    409,
                    f"La spec '{sd['label']}' ya está asignada a esta categoría.",
                )
            raise


@router.patch("/admin/spec-templates/{template_id}")
def actualizar_asignacion(template_id: int, payload: SpecAssignmentUpdate, request: Request):
    """Actualiza los flags de una asignación en categoria_spec_templates.
    NOTA legacy (Fase 6d): estos flags ya no controlan el catálogo público;
    la fuente canónica es spec_definitions. Se elimina en 6f.
    Para cambiar tipo/unidad/options usar PATCH /admin/spec-definitions/{id}."""
    _require_admin(request)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Nada para actualizar")
    if "rol_compatibilidad" in updates and updates["rol_compatibilidad"] not in (None, "contenedor", "contenido"):
        raise HTTPException(400, "rol_compatibilidad debe ser 'contenedor' o 'contenido' (o null).")
    with get_db() as conn:
        try:
            existing = conn.execute(
                "SELECT id FROM categoria_spec_templates WHERE id = %s", (template_id,)
            ).fetchone()
            if not existing:
                raise HTTPException(404, "Asignación no existe")
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE categoria_spec_templates SET {set_clause} WHERE id = %s",
                list(updates.values()) + [template_id],
            )
            conn.commit()
            return {"ok": True, "id": template_id, **updates}
        except Exception:
            conn.rollback()
            raise


@router.delete("/admin/spec-templates/{template_id}", status_code=204)
def borrar_asignacion(template_id: int, request: Request):
    """Desasigna la spec de la categoría (no toca la spec_definition global)."""
    _require_admin(request)
    with get_db() as conn:
        conn.execute(
            "DELETE FROM categoria_spec_templates WHERE id = %s", (template_id,)
        )
        conn.commit()
        # NOTA: equipo_specs NO se borra al desasignar — los valores cargados
        # quedan como "huérfanos" hasta que el dueño los borre desde la UI.


@router.post("/admin/spec-templates/reorder")
def reordenar_templates(payload: dict, request: Request):
    """Actualiza la prioridad de categoria_spec_templates en un solo request.
    Body: {"items": [{"id": 1, "prioridad": 10}, {"id": 2, "prioridad": 20}, …]}.
    NOTA legacy (Fase 6d): el catálogo público usa sd.prioridad de spec_definitions.
    Este endpoint escribe en categoria_spec_templates (solo afecta la UI admin de
    asignación por categoría). Se elimina en 6f.
    """
    _require_admin(request)
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "Falta 'items' (lista de {id, prioridad})")
    with get_db() as conn:
        try:
            for item in items:
                tid = item.get("id")
                prio = item.get("prioridad")
                if tid is None or prio is None:
                    raise HTTPException(400, "Cada item necesita 'id' y 'prioridad'")
                conn.execute(
                    "UPDATE categoria_spec_templates SET prioridad = %s WHERE id = %s",
                    (int(prio), int(tid)),
                )
            conn.commit()
            return {"ok": True, "count": len(items)}
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            logger.exception("Error reordenando spec-templates")
            raise HTTPException(500, "No se pudo reordenar")
