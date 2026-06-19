"""Diagnóstico / inspección del sistema de specs (#501 — extraído del god-module
`routes/specs.py`).

Vistas de lectura del estado de specs por categoría (cobertura, huérfanas,
debug del template), más el reorder de specs dentro de una categoría. Registra
sus rutas en el router compartido del paquete `routes.specs`. `_require_admin`
(guard) vive en `core`.
"""
from fastapi import HTTPException, Request

from database import get_db, row_to_dict
from routes.specs.core import router, _require_admin


@router.get("/admin/specs/por-categoria")
def listar_specs_por_categoria(request: Request):
    """Devuelve specs agrupadas por categoría raíz (Cámaras, Lentes, …) con
    los flags persistentes y el conteo de equipos que la tienen cargada.
    Usado por la UI consolidada de /admin/specs (drag-and-drop + favoritos)."""
    _require_admin(request)
    with get_db() as conn:
        try:
            # Pre-check: las columnas favorito/en_nombre/en_filtros/prioridad
            # vienen de la migración `e5a7b9d2c4f1_spec_def_flags`. Si no corrió
            # en producción (alembic upgrade head falla silenciosamente al boot),
            # el SELECT principal tira UndefinedColumn 500 sin contexto.
            # Mejor detectarlo acá y devolver mensaje accionable.
            cols_rows = conn.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'spec_definitions'
            """).fetchall()
            col_names = {row_to_dict(c)["column_name"] for c in cols_rows}
            required = {"favorito", "en_nombre", "en_filtros", "prioridad"}
            missing = required - col_names
            if missing:
                raise HTTPException(
                    503,
                    f"Migración pendiente: faltan columnas {sorted(missing)} en spec_definitions. "
                    f"Correr `alembic upgrade head` en producción o forzar re-deploy.",
                )
            # Raíces que tienen specs sembradas. Ordenadas por prioridad de la
            # categoría (= el orden visual del bloque).
            rows = conn.execute("""
                SELECT
                  c.id AS categoria_id,
                  c.nombre AS categoria_nombre,
                  c.prioridad AS categoria_prioridad,
                  c.grupo_visual,
                  c.nombre_publico_template,
                  sd.id, sd.spec_key, sd.label, sd.tipo, sd.unidad,
                  sd.enum_options, sd.ayuda, sd.output_config,
                  COALESCE(sd.es_compatibilidad, FALSE) AS es_compatibilidad,
                  COALESCE(sd.compatibilidad_modo, 'exacta') AS compatibilidad_modo,
                  COALESCE(sd.favorito, FALSE) AS favorito,
                  COALESCE(sd.en_nombre, FALSE) AS en_nombre,
                  COALESCE(sd.en_filtros, FALSE) AS en_filtros,
                  COALESCE(sd.prioridad, 100) AS prioridad,
                  COALESCE(uso.n, 0) AS uso_equipos
                FROM spec_definitions sd
                JOIN categorias c ON c.id = sd.categoria_raiz_id
                LEFT JOIN (
                  SELECT spec_def_id, COUNT(*) AS n
                  FROM equipo_specs
                  GROUP BY spec_def_id
                ) uso ON uso.spec_def_id = sd.id
                WHERE sd.categoria_raiz_id IS NOT NULL
                ORDER BY c.prioridad NULLS LAST, c.nombre, sd.prioridad, sd.label
            """).fetchall()
            # Agrupar por categoría raíz
            grupos: dict[int, dict] = {}
            for r in rows:
                d = row_to_dict(r)
                cid = d["categoria_id"]
                if cid not in grupos:
                    grupos[cid] = {
                        "id": cid,
                        "nombre": d["categoria_nombre"],
                        "prioridad": d["categoria_prioridad"],
                        "grupo_visual": d.get("grupo_visual"),
                        "nombre_publico_template": d.get("nombre_publico_template"),
                        "specs": [],
                    }
                grupos[cid]["specs"].append({
                    "id": d["id"],
                    "spec_key": d["spec_key"],
                    "label": d["label"],
                    "tipo": d["tipo"],
                    "unidad": d.get("unidad"),
                    "enum_options": d.get("enum_options"),
                    "ayuda": d.get("ayuda"),
                    "output_config": d.get("output_config"),
                    "es_compatibilidad": d.get("es_compatibilidad", False),
                    "compatibilidad_modo": d.get("compatibilidad_modo"),
                    "favorito": d.get("favorito", False),
                    "en_nombre": d.get("en_nombre", False),
                    "en_filtros": d.get("en_filtros", False),
                    "prioridad": d.get("prioridad", 100),
                    "uso_equipos": d.get("uso_equipos", 0),
                })
            # Devolver como lista ordenada
            return {"categorias": list(grupos.values())}
        except HTTPException:
            raise
        except Exception as e:
            # Devolver el error con contexto SQL para diagnosticar 500s desde
            # la UI admin. Es endpoint admin → OK exponer detalles.
            import traceback
            raise HTTPException(
                500,
                f"Error en listar_specs_por_categoria: {type(e).__name__}: {e}\n"
                f"{traceback.format_exc()[-500:]}",
            )


@router.get("/admin/specs/diagnostico")
def diagnostico_specs(request: Request):
    """Devuelve info de estado del subsistema specs — útil para diagnosticar
    500s desde la UI admin sin tener acceso a logs."""
    _require_admin(request)
    with get_db() as conn:
        # Schema de spec_definitions
        cols = conn.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'spec_definitions'
            ORDER BY ordinal_position
        """).fetchall()
        # Versión actual de alembic
        try:
            ver_row = conn.execute(
                "SELECT version_num FROM alembic_version LIMIT 1"
            ).fetchone()
            alembic_version = (
                row_to_dict(ver_row)["version_num"] if ver_row else None
            )
        except Exception as e:
            alembic_version = f"<error: {e}>"
        # Conteo de specs sembradas
        try:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM spec_definitions"
            ).fetchone()
            total_specs = row_to_dict(total)["n"] if total else 0
        except Exception as e:
            total_specs = f"<error: {e}>"
        # Categorías raíz con specs
        try:
            cats = conn.execute("""
                SELECT c.nombre, COUNT(sd.id) AS n
                FROM categorias c
                LEFT JOIN spec_definitions sd ON sd.categoria_raiz_id = c.id
                WHERE c.parent_id IS NULL
                GROUP BY c.id, c.nombre
                ORDER BY c.nombre
            """).fetchall()
            por_categoria = [row_to_dict(r) for r in cats]
        except Exception as e:
            por_categoria = f"<error: {e}>"
        return {
            "alembic_version": alembic_version,
            "spec_definitions_schema": [row_to_dict(c) for c in cols],
            "total_specs": total_specs,
            "por_categoria_raiz": por_categoria,
            "expected_columns": [
                "favorito", "en_nombre", "en_filtros", "prioridad",
            ],
            "missing_required_columns": sorted(
                {"favorito", "en_nombre", "en_filtros", "prioridad"}
                - {row_to_dict(c)["column_name"] for c in cols}
            ),
        }


@router.get("/admin/specs/template-debug")
def template_debug(categoria_id: int, request: Request):
    """Diagnóstico para el endpoint `listar_templates`.

    Reportado: el form de edición de equipo muestra solo 1 spec en la
    ficha técnica para un equipo en raíz "Iluminación" (que tiene 56
    specs en el registry). PR #407 agregó fallback al registry pero el
    bug persiste tras el deploy. Este endpoint devuelve los conteos
    intermedios del mismo SQL para identificar dónde falla la cadena.
    """
    _require_admin(request)
    with get_db() as conn:
        # 1) Calcular raíz desde la categoría dada
        raiz_row = conn.execute(
            """
            WITH RECURSIVE up AS (
                SELECT id, parent_id, 0 AS depth FROM categorias WHERE id = ?
                UNION
                SELECT c.id, c.parent_id, up.depth + 1
                FROM categorias c JOIN up ON up.parent_id = c.id
            )
            SELECT id FROM up WHERE parent_id IS NULL LIMIT 1
            """,
            (categoria_id,),
        ).fetchone()
        raiz_id = row_to_dict(raiz_row)["id"] if raiz_row else categoria_id

        # 2) Conteo de specs en spec_definitions con esa raíz
        sd_row = conn.execute(
            "SELECT COUNT(*) AS n FROM spec_definitions WHERE categoria_raiz_id = ?",
            (raiz_id,),
        ).fetchone()
        categoria_raiz_specs_count = row_to_dict(sd_row)["n"] if sd_row else 0

        # 3) Asignaciones explícitas en categoria_spec_templates
        assigned_rows = conn.execute(
            """
            SELECT sd.spec_key
            FROM categoria_spec_templates t
            JOIN spec_definitions sd ON sd.id = t.spec_def_id
            WHERE t.categoria_id = ?
            ORDER BY sd.label
            """,
            (categoria_id,),
        ).fetchall()
        assigned_keys = [row_to_dict(r)["spec_key"] for r in assigned_rows]

        # 4) Fallback: specs de la raíz que NO tienen asignación a categoria_id
        fallback_rows = conn.execute(
            """
            SELECT sd.spec_key
            FROM spec_definitions sd
            WHERE sd.categoria_raiz_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM categoria_spec_templates t
                  WHERE t.categoria_id = ?
                    AND t.spec_def_id = sd.id
              )
            ORDER BY sd.label
            """,
            (raiz_id, categoria_id),
        ).fetchall()
        fallback_keys = [row_to_dict(r)["spec_key"] for r in fallback_rows]

        # 5) Categoria info para el response
        cat_row = conn.execute(
            "SELECT id, nombre, parent_id FROM categorias WHERE id = ?",
            (categoria_id,),
        ).fetchone()
        cat_info = row_to_dict(cat_row) if cat_row else None

        return {
            "input": {"categoria_id": categoria_id},
            "categoria": cat_info,
            "raiz_id": raiz_id,
            "categoria_raiz_specs_count": categoria_raiz_specs_count,
            "assigned_count": len(assigned_keys),
            "fallback_count": len(fallback_keys),
            "total_items": len(assigned_keys) + len(fallback_keys),
            "sample_keys_assigned": assigned_keys[:5],
            "sample_keys_fallback": fallback_keys[:5],
            "explicacion": {
                "ok_endpoint_funciona": "categoria_raiz_specs_count == total_items",
                "bug_si_fallback_zero_pero_raiz_no_zero":
                    "El SQL del fallback en listar_templates está mal — "
                    "los specs existen pero no se devuelven.",
                "bug_si_raiz_specs_count_zero":
                    "Los specs no tienen categoria_raiz_id poblado — "
                    "regresión en el seeder.",
            },
        }


@router.put("/admin/specs/categoria/{categoria_id}/reorder")
def reorder_specs_categoria(categoria_id: int, payload: dict, request: Request):
    """Reordena las specs de una categoría raíz vía drag-and-drop.

    Payload: `{"spec_ids": [id1, id2, id3, ...]}` en el orden deseado.
    Se asigna prioridad = 10, 20, 30, ... según el índice (con gap por si
    hay que insertar después)."""
    _require_admin(request)
    ids = payload.get("spec_ids")
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        raise HTTPException(400, "spec_ids debe ser una lista de enteros.")
    with get_db() as conn:
        try:
            # Verificar que todos los ids pertenecen a la categoría
            rows = conn.execute(
                "SELECT id FROM spec_definitions WHERE categoria_raiz_id = ?",
                (categoria_id,),
            ).fetchall()
            valid_ids = {row_to_dict(r)["id"] for r in rows}
            for spec_id in ids:
                if spec_id not in valid_ids:
                    raise HTTPException(
                        400,
                        f"Spec id={spec_id} no pertenece a la categoría {categoria_id}.",
                    )
            if not ids:
                return {"ok": True, "actualizadas": 0}
            # Una sola UPDATE con CASE WHEN — evita el N+1.
            # Los ids ya fueron validados (todos ints + pertenecen a la categoría),
            # así que es seguro inlinearlos en la query.
            case_parts = []
            params: list[int] = []
            for idx, spec_id in enumerate(ids):
                case_parts.append("WHEN id = ? THEN ?")
                params.extend([spec_id, (idx + 1) * 10])
            placeholders = ",".join("?" for _ in ids)
            params.extend(ids)
            conn.execute(
                f"""UPDATE spec_definitions
                       SET prioridad = CASE {' '.join(case_parts)} ELSE prioridad END,
                           updated_at = CURRENT_TIMESTAMP
                     WHERE id IN ({placeholders})""",
                params,
            )
            conn.commit()
            return {"ok": True, "actualizadas": len(ids)}
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
