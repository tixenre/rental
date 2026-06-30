"""Specs por equipo (#501 — extraído del god-module `routes/specs.py`).

Get/replace de las specs estructuradas de un equipo. Registra sus rutas en el
router compartido del paquete `routes.specs`. `_require_admin` es el guard
compartido (vive en `core`).
"""
from fastapi import HTTPException, Request
from pydantic import BaseModel

from database import get_db, row_to_dict
from services.nombre_service import actualizar_nombres_de
from services.spec_persist import persistir_specs
from routes.specs.core import router, _require_admin


class EquipoSpecsInput(BaseModel):
    """Diccionario `{spec_def_id (str): value}`. Reemplaza TODAS las specs
    del equipo. Las keys del dict son strings (JSON) pero se interpretan
    como int en el backend."""
    specs: dict[str, str]


# ── Specs por equipo ────────────────────────────────────────────────────

@router.get("/admin/equipos/{equipo_id}/specs")
def obtener_specs_equipo(equipo_id: int, request: Request):
    """Devuelve las specs estructuradas del equipo + el template aplicable
    (todas las categorías del equipo unidas, con dedup por spec_def). Las
    keys del dict `specs` son strings stringificadas del spec_def_id (JSON
    no soporta int keys)."""
    _require_admin(request)
    with get_db() as conn:
        eq = conn.execute(
            "SELECT id FROM equipos WHERE id = %s", (equipo_id,)
        ).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no existe")

        # Specs ya cargadas
        spec_rows = conn.execute(
            "SELECT spec_def_id, value FROM equipo_specs WHERE equipo_id = %s",
            (equipo_id,),
        ).fetchall()
        specs = {str(r["spec_def_id"]): r["value"] for r in spec_rows}

        # Template aplicable: se resuelve desde la categoría de SPECS del
        # equipo (`equipos.categoria_specs`), NO desde el árbol de catálogo.
        # El catálogo (`equipo_categorias`) es solo agrupación para el
        # front-office; las specs de un equipo las define su categoría de specs
        # (1 de las 5 del registry: Cámaras/Lentes/…). Leemos directo de
        # `spec_definitions` por `categoria_raiz_id` (mismo criterio que
        # /admin/categorias/{id}/spec-templates) para no depender de
        # `categoria_spec_templates`, que puede quedar incompleto tras
        # migraciones del registry. El SELECT proyecta el shape completo del
        # tipo `SpecTemplate` del frontend.
        cs_row = conn.execute(
            "SELECT categoria_specs FROM equipos WHERE id = %s", (equipo_id,)
        ).fetchone()
        categoria_specs = (
            row_to_dict(cs_row).get("categoria_specs") if cs_row else None
        )

        template: list[dict] = []
        if categoria_specs:
            cat_row = conn.execute(
                "SELECT id FROM categorias WHERE nombre = %s AND parent_id IS NULL",
                (categoria_specs,),
            ).fetchone()
            if cat_row:
                raiz_id = row_to_dict(cat_row)["id"]
                template_rows = conn.execute(
                    """
                    SELECT
                        sd.id AS spec_def_id,
                        sd.spec_key, sd.label, sd.tipo, sd.unidad, sd.unidad_id,
                        sd.enum_options, sd.tabla_columnas, sd.output_config,
                        COALESCE(sd.es_compatibilidad, FALSE) AS es_compatibilidad,
                        COALESCE(sd.compatibilidad_modo, 'exacta') AS compatibilidad_modo,
                        sd.rol_compatibilidad,
                        COALESCE(sd.prioridad, 100) AS prioridad,
                        COALESCE(sd.favorito, FALSE) AS visible_en_card,
                        COALESCE(sd.en_filtros, FALSE) AS visible_en_filtros,
                        COALESCE(sd.en_nombre, FALSE) AS visible_en_nombre,
                        COALESCE(sd.favorito, FALSE) AS destacado,
                        FALSE AS obligatorio,
                        sd.ayuda
                    FROM spec_definitions sd
                    WHERE sd.categoria_raiz_id = %s
                    ORDER BY COALESCE(sd.prioridad, 100), sd.label
                    """,
                    (raiz_id,),
                ).fetchall()
                for r in template_rows:
                    d = row_to_dict(r)
                    d["id"] = None
                    d["template_id"] = None
                    d["categoria_id"] = raiz_id
                    template.append(d)
        template.sort(key=lambda t: (t["prioridad"], t["label"]))

        return {
            "equipo_id": equipo_id,
            "specs": specs,
            "template": template,
        }


@router.put("/admin/equipos/{equipo_id}/specs")
def reemplazar_specs_equipo(equipo_id: int, payload: EquipoSpecsInput, request: Request):
    """Reemplaza TODAS las specs del equipo. Body shape:
    {specs: { "<spec_def_id>": "value" }}. Las keys son ints stringificados."""
    _require_admin(request)
    with get_db() as conn:
        try:
            eq = conn.execute(
                "SELECT id FROM equipos WHERE id = %s", (equipo_id,)
            ).fetchone()
            if not eq:
                raise HTTPException(404, "Equipo no existe")

            keys_int: list[int] = []
            for key in payload.specs.keys():
                try:
                    keys_int.append(int(key))
                except (TypeError, ValueError):
                    raise HTTPException(
                        400,
                        f"spec_def_id inválido en payload.specs: '{key}'. Las keys deben ser IDs numéricos.",
                    )

            defs_by_id: dict[int, dict] = {}
            if keys_int:
                placeholders = ",".join(["%s"] * len(keys_int))
                def_rows = conn.execute(
                    f"SELECT id, label, tipo, tabla_columnas, enum_options, unidad "
                    f"FROM spec_definitions WHERE id IN ({placeholders})",
                    tuple(keys_int),
                ).fetchall()
                defs_by_id = {r["id"]: row_to_dict(r) for r in def_rows}

            result = persistir_specs(conn, equipo_id, payload.specs, defs_by_id, coerce=True)

            try:
                actualizar_nombres_de(conn, equipo_id, commit=False)
            except Exception:
                pass

            conn.commit()
            return {
                "ok": True,
                "equipo_id": equipo_id,
                "specs_count": result["persisted"],
                "discarded": result["discarded"],
            }
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
