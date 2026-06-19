"""
routes/specs.py — Endpoints del rediseño bulletproof de specs.

Cubre:
  - CRUD de templates por categoría (categoria_spec_templates).
  - GET/PUT de specs por equipo (equipo_specs).
  - Endpoint para regenerar nombres públicos masivamente (con dry-run).
  - Endpoint para recalcular el ranking de popularidad (con dry-run).

Diseño completo: docs/DISEÑO_SPECS.md sección 3, 4, 5.
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from database import get_db, row_to_dict
from routes.auth import get_session


router = APIRouter()


# ── Auth helper ─────────────────────────────────────────────────────────

def _require_admin(request: Request) -> dict:
    session = get_session(request)
    if not session:
        raise HTTPException(401, "No autenticado")
    return session


# ── Models Pydantic ────────────────────────────────────────────────────
#
# Refactor unificar_specs_definitions:
# - spec_definitions: catálogo global. Cada spec_key existe UNA vez.
# - categoria_spec_templates: ASIGNACIÓN de una def a una categoría + flags
#   propios de visibilidad/prioridad/destacado.
# - equipo_specs: valor por equipo, referenciado por spec_def_id.


# Definición global (creación / update del catálogo).
class SpecDefinitionInput(BaseModel):
    spec_key: str
    label: str
    tipo: str   # "string" | "number" | "enum" | "bool" | "rango" | "wxh" | "wxhxd" | "multi_enum" | "tabla"
    unidad: Optional[str] = None
    enum_options: Optional[list[str]] = None
    ayuda: Optional[str] = None
    es_compatibilidad: bool = False
    compatibilidad_modo: str = "exacta"  # "exacta" | "jerarquia"
    validado: bool = False
    # tabla_columnas: shape de columnas cuando tipo='tabla'. Cada item:
    #   {key, label, tipo, options?, unidad?}
    # `tipo` interno de la columna: "string" | "number" | "enum" | "bool".
    tabla_columnas: Optional[list[dict]] = None
    # Config declarativa de render del placeholder {spec:Label}.
    # Por ahora solo soporta `row_strategy: "all" | "first" | "last"` para
    # specs tipo tabla. NULL = defaults (all).
    output_config: Optional[dict] = None


class SpecDefinitionUpdate(BaseModel):
    spec_key: Optional[str] = None  # Editable durante construcción del sistema.
    label: Optional[str] = None
    tipo: Optional[str] = None
    unidad: Optional[str] = None
    enum_options: Optional[list[str]] = None
    ayuda: Optional[str] = None
    es_compatibilidad: Optional[bool] = None
    compatibilidad_modo: Optional[str] = None
    validado: Optional[bool] = None
    tabla_columnas: Optional[list[dict]] = None
    output_config: Optional[dict] = None
    # Flags persistentes a nivel categoría raíz (ver migración e5a7b9d2c4f1).
    favorito: Optional[bool] = None
    en_nombre: Optional[bool] = None
    en_filtros: Optional[bool] = None
    prioridad: Optional[int] = None


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


class PropuestaInput(BaseModel):
    # Una propuesta del skill resolver. tipo determina el shape del payload:
    # - enum_option: {spec_def_id, options: [str]}
    # - spec_nueva: {spec_key, label, tipo, unidad?, enum_options?, es_compatibilidad?, compatibilidad_modo?, razon}
    # - merge_specs: {keep_spec_def_id, merge_spec_def_ids: [int], razon}
    tipo: str   # "enum_option" | "spec_nueva" | "merge_specs"
    payload: dict
    origen: Optional[str] = None    # ej. "gear-compatibility skill v1"
    confianza: Optional[float] = None


class PropuestasBulkInput(BaseModel):
    items: list[PropuestaInput]


# ── Catálogo global de spec_definitions ────────────────────────────────

@router.get("/admin/spec-definitions")
def listar_spec_definitions(request: Request):
    """Catálogo global de specs disponibles, con uso_count (cuántas
    categorías la usan + cuántos equipos tienen value cargado) y un array
    de nombres de categorías que la asignan (para filtrar en la UI)."""
    _require_admin(request)
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
              sd.id, sd.spec_key, sd.label, sd.tipo, sd.unidad, sd.unidad_id,
              sd.enum_options, sd.ayuda, sd.tabla_columnas, sd.output_config,
              sd.categoria_raiz_id,
              COALESCE(sd.es_compatibilidad, FALSE) AS es_compatibilidad,
              COALESCE(sd.compatibilidad_modo, 'exacta') AS compatibilidad_modo,
              COALESCE(sd.validado, FALSE) AS validado,
              COALESCE(sd.favorito, FALSE) AS favorito,
              COALESCE(sd.en_nombre, FALSE) AS en_nombre,
              COALESCE(sd.en_filtros, FALSE) AS en_filtros,
              COALESCE(sd.prioridad, 100) AS prioridad,
              (SELECT COUNT(*) FROM categoria_spec_templates t WHERE t.spec_def_id = sd.id) AS uso_categorias,
              (SELECT COUNT(*) FROM equipo_specs es WHERE es.spec_def_id = sd.id) AS uso_equipos,
              COALESCE(
                (SELECT json_agg(
                          json_build_object(
                            'id', c.id,
                            'nombre', c.nombre,
                            'template_id', t.id,
                            'destacado', COALESCE(t.destacado, FALSE),
                            'prioridad', t.prioridad,
                            'ayuda', t.ayuda
                          ) ORDER BY c.nombre
                        )
                 FROM categoria_spec_templates t
                 JOIN categorias c ON c.id = t.categoria_id
                 WHERE t.spec_def_id = sd.id),
                '[]'::json
              ) AS categorias
            FROM spec_definitions sd
            ORDER BY sd.validado DESC, sd.label
        """).fetchall()
        return {"items": [row_to_dict(r) for r in rows]}


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


_VALID_SPEC_TIPOS = {"string", "number", "enum", "bool", "rango", "wxh", "wxhxd", "multi_enum", "tabla"}
_VALID_COL_TIPOS = {"string", "number", "enum", "bool", "valor_unidad"}
_VALID_ROW_STRATEGIES = {"all", "first", "last"}


def _resolve_unidad_id(conn, simbolo: Optional[str]) -> Optional[int]:
    """Lookup `unidades.id` por `simbolo`. Si no existe la entry y el
    símbolo no está vacío, la crea (idempotent, dimension=NULL).
    Devuelve `None` si simbolo es vacío/None."""
    if simbolo is None:
        return None
    s = (simbolo or "").strip()
    if not s:
        return None
    row = conn.execute(
        "SELECT id FROM unidades WHERE simbolo = ?", (s,)
    ).fetchone()
    if row:
        return row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0]
    conn.execute(
        "INSERT INTO unidades (simbolo, nombre, dimension) "
        "VALUES (?, ?, NULL) ON CONFLICT (simbolo) DO NOTHING",
        (s, s),
    )
    row = conn.execute(
        "SELECT id FROM unidades WHERE simbolo = ?", (s,)
    ).fetchone()
    if row is None:
        return None
    return row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0]


def _validate_output_config(oc: Optional[dict], tipo: str) -> None:
    """Verifica shape de `output_config`. Soporta:
    - `row_strategy` (solo specs tipo tabla)
    - `name_format` (template para nombre auto, ej. "Potencia {value} lm")
    """
    if oc is None or oc == {}:
        return
    if not isinstance(oc, dict):
        raise HTTPException(400, "output_config debe ser un objeto JSON.")
    rs = oc.get("row_strategy")
    if rs is not None:
        if tipo != "tabla":
            raise HTTPException(
                400, "output_config.row_strategy solo aplica a specs tipo 'tabla'."
            )
        if rs not in _VALID_ROW_STRATEGIES:
            raise HTTPException(
                400,
                f"output_config.row_strategy inválido: '{rs}'. "
                f"Permitidos: {sorted(_VALID_ROW_STRATEGIES)}.",
            )
    nf = oc.get("name_format")
    if nf is not None:
        if not isinstance(nf, str):
            raise HTTPException(400, "output_config.name_format debe ser string.")
        if len(nf) > 200:
            raise HTTPException(400, "output_config.name_format máximo 200 caracteres.")


def _validate_tabla_columnas(cols: Optional[list[dict]]) -> None:
    """Verifica el shape de `tabla_columnas`: cada item debe tener
    {key, label, tipo} con tipo en _VALID_COL_TIPOS, opciones obligatorias
    si tipo='enum', keys únicas."""
    if not cols:
        raise HTTPException(400, "Para tipo 'tabla' hay que definir al menos una columna.")
    seen: set[str] = set()
    for i, c in enumerate(cols):
        if not isinstance(c, dict):
            raise HTTPException(400, f"Columna {i}: debe ser objeto JSON.")
        key = (c.get("key") or "").strip()
        label = (c.get("label") or "").strip()
        tipo = (c.get("tipo") or "").strip()
        if not key or not label or not tipo:
            raise HTTPException(400, f"Columna {i}: faltan key/label/tipo.")
        if key in seen:
            raise HTTPException(400, f"Columna {i}: key '{key}' duplicada.")
        seen.add(key)
        if tipo not in _VALID_COL_TIPOS:
            raise HTTPException(
                400, f"Columna '{key}': tipo '{tipo}' inválido. Permitidos: {sorted(_VALID_COL_TIPOS)}"
            )
        if tipo == "enum" and not c.get("options"):
            raise HTTPException(400, f"Columna '{key}' tipo enum: hay que listar 'options'.")


@router.post("/admin/spec-definitions", status_code=201)
def crear_spec_definition(payload: SpecDefinitionInput, request: Request):
    _require_admin(request)
    if payload.tipo not in _VALID_SPEC_TIPOS:
        raise HTTPException(400, f"tipo inválido: {payload.tipo}. Permitidos: {sorted(_VALID_SPEC_TIPOS)}")
    if payload.tipo in ("rango", "wxh", "wxhxd") and not (payload.unidad and payload.unidad.strip()):
        raise HTTPException(400, "Para este tipo la unidad es obligatoria (mm, px, °, kg…).")
    if payload.tipo in ("enum", "multi_enum") and not payload.enum_options:
        raise HTTPException(400, "Para tipo enum / multi_enum hay que listar al menos una opción.")
    if payload.tipo == "tabla":
        _validate_tabla_columnas(payload.tabla_columnas)
    _validate_output_config(payload.output_config, payload.tipo)
    if payload.compatibilidad_modo not in ("exacta", "jerarquia"):
        raise HTTPException(400, "compatibilidad_modo debe ser 'exacta' o 'jerarquia'.")
    if payload.compatibilidad_modo == "jerarquia" and payload.tipo != "enum":
        raise HTTPException(
            400,
            "Modo jerárquico solo aplica a tipo 'enum' — el orden de enum_options "
            "define la posición de cada valor en la escala.",
        )
    with get_db() as conn:
        try:
            unidad_id = _resolve_unidad_id(conn, payload.unidad)
            cur = conn.execute(
                """
                INSERT INTO spec_definitions
                  (spec_key, label, tipo, unidad, unidad_id, enum_options, ayuda,
                   es_compatibilidad, compatibilidad_modo, validado,
                   tabla_columnas, output_config)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    payload.spec_key,
                    payload.label,
                    payload.tipo,
                    payload.unidad,
                    unidad_id,
                    json.dumps(payload.enum_options) if payload.enum_options else None,
                    payload.ayuda,
                    payload.es_compatibilidad,
                    payload.compatibilidad_modo,
                    payload.validado,
                    json.dumps(payload.tabla_columnas) if payload.tabla_columnas else None,
                    json.dumps(payload.output_config) if payload.output_config else None,
                ),
            )
            new_id = cur.fetchone()[0]
            conn.commit()
            return {"id": new_id, **payload.model_dump()}
        except Exception as e:
            conn.rollback()
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                raise HTTPException(409, f"La spec '{payload.spec_key}' ya existe globalmente.")
            raise


@router.patch("/admin/spec-definitions/{def_id}")
def actualizar_spec_definition(def_id: int, payload: SpecDefinitionUpdate, request: Request):
    _require_admin(request)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Nada para actualizar")
    if "prioridad" in updates and updates["prioridad"] is not None:
        if updates["prioridad"] < 0:
            raise HTTPException(400, "prioridad debe ser >= 0")
    if "spec_key" in updates:
        # Editable durante construcción del sistema. Validamos formato igual
        # que en CREATE; la colisión por UNIQUE constraint la captura el
        # except más abajo.
        new_key = (updates["spec_key"] or "").strip()
        import re as _re
        if not _re.match(r"^[a-z][a-z0-9_]*$", new_key):
            raise HTTPException(
                400,
                "spec_key inválida: solo minúsculas, números y _ (debe empezar con letra).",
            )
        updates["spec_key"] = new_key
    if "enum_options" in updates:
        updates["enum_options"] = (
            json.dumps(updates["enum_options"]) if updates["enum_options"] else None
        )
    if "tabla_columnas" in updates:
        if updates["tabla_columnas"]:
            _validate_tabla_columnas(updates["tabla_columnas"])
            updates["tabla_columnas"] = json.dumps(updates["tabla_columnas"])
        else:
            updates["tabla_columnas"] = None
    if "compatibilidad_modo" in updates and updates["compatibilidad_modo"] not in ("exacta", "jerarquia"):
        raise HTTPException(400, "compatibilidad_modo debe ser 'exacta' o 'jerarquia'.")
    if "output_config" in updates:
        # Necesita conocer el tipo final para validar — lo chequea más abajo
        # contra existing_dict + final_tipo. Acá solo serializamos.
        oc_val = updates["output_config"]
        updates["output_config"] = json.dumps(oc_val) if oc_val else None
    # Sync unidad ↔ unidad_id: si el caller cambia `unidad`, recomputamos
    # `unidad_id` desde el catálogo (creándolo si no existe).
    sync_unidad_id: Optional[bool] = "unidad" in updates
    with get_db() as conn:
        try:
            existing = conn.execute(
                "SELECT id, tipo, unidad, compatibilidad_modo FROM spec_definitions WHERE id = ?", (def_id,)
            ).fetchone()
            if not existing:
                raise HTTPException(404, "Definición no existe")
            existing_dict = row_to_dict(existing) if not isinstance(existing, dict) else existing
            final_tipo = updates.get("tipo", existing_dict.get("tipo"))
            final_unidad = updates.get("unidad", existing_dict.get("unidad"))
            final_modo = updates.get("compatibilidad_modo", existing_dict.get("compatibilidad_modo"))
            if final_tipo in ("rango", "wxh", "wxhxd") and not (final_unidad and str(final_unidad).strip()):
                raise HTTPException(400, "Para este tipo la unidad es obligatoria (mm, px, °, kg…).")
            if final_modo == "jerarquia" and final_tipo != "enum":
                raise HTTPException(
                    400,
                    "Modo jerárquico solo aplica a tipo 'enum' — cambiá el tipo o el modo.",
                )
            # Validar output_config contra el tipo final (después de aplicar
            # cambios pendientes). Usamos el payload sin serializar de Pydantic.
            if payload.output_config is not None:
                _validate_output_config(payload.output_config, final_tipo)
            # Sync unidad_id desde el catálogo cuando se cambia `unidad`.
            if sync_unidad_id:
                updates["unidad_id"] = _resolve_unidad_id(conn, updates.get("unidad"))
            # Si está cambiando el tipo y hay valores ya cargados, bloqueamos —
            # el cambio podría invalidar todos los formatos guardados.
            if "tipo" in updates and updates["tipo"] != existing_dict.get("tipo"):
                count = conn.execute(
                    "SELECT COUNT(*) AS n FROM equipo_specs WHERE spec_def_id = ?", (def_id,)
                ).fetchone()
                if count and count["n"] > 0:
                    raise HTTPException(
                        409,
                        f"No se puede cambiar el tipo: hay {count['n']} equipos con valores cargados. "
                        "Borralos primero o creá una spec nueva.",
                    )
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            try:
                conn.execute(
                    f"UPDATE spec_definitions SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    list(updates.values()) + [def_id],
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                msg = str(e).lower()
                if "duplicate key" in msg or "unique" in msg:
                    raise HTTPException(
                        409,
                        f"Ya existe otra spec con key '{updates.get('spec_key')}'. Elegí otra.",
                    )
                raise
            return {"ok": True, "id": def_id, **updates}
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise

@router.delete("/admin/spec-definitions/{def_id}", status_code=204)
def borrar_spec_definition(def_id: int, request: Request):
    _require_admin(request)
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM spec_definitions WHERE id = ?", (def_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Definición no existe")
        usos = conn.execute(
            "SELECT COUNT(*) AS n FROM categoria_spec_templates WHERE spec_def_id = ?", (def_id,)
        ).fetchone()
        if usos and usos["n"] > 0:
            raise HTTPException(
                409,
                f"La spec está asignada a {usos['n']} categoría(s). "
                "Desasignala primero antes de borrar la definición.",
            )
        equip = conn.execute(
            "SELECT COUNT(*) AS n FROM equipo_specs WHERE spec_def_id = ?", (def_id,)
        ).fetchone()
        if equip and equip["n"] > 0:
            raise HTTPException(
                409,
                f"Hay {equip['n']} equipos con valores cargados en esta spec. "
                "Borralos primero.",
            )
        conn.execute("DELETE FROM spec_definitions WHERE id = ?", (def_id,))
        conn.commit()


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
                SELECT id, parent_id FROM categorias WHERE id = ?
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
            WHERE sd.categoria_raiz_id = ?
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
                  AND inner_ec.categoria_id = ?
                  AND inner_e.eliminado_at IS NULL
                LIMIT 3
              ) AS sample_values
            FROM equipo_specs es
            JOIN equipos e ON e.id = es.equipo_id
            JOIN equipo_categorias ec ON ec.equipo_id = e.id
            JOIN spec_definitions sd ON sd.id = es.spec_def_id
            WHERE ec.categoria_id = ?
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
            "SELECT id FROM categorias WHERE id = ?", (categoria_id,)
        ).fetchone()
        if not cat:
            raise HTTPException(404, f"Categoría {categoria_id} no existe")
        sd = conn.execute(
            "SELECT id, label FROM spec_definitions WHERE id = ?", (payload.spec_def_id,)
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                "SELECT id FROM categoria_spec_templates WHERE id = ?", (template_id,)
            ).fetchone()
            if not existing:
                raise HTTPException(404, "Asignación no existe")
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE categoria_spec_templates SET {set_clause} WHERE id = ?",
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
            "DELETE FROM categoria_spec_templates WHERE id = ?", (template_id,)
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
                    "UPDATE categoria_spec_templates SET prioridad = ? WHERE id = ?",
                    (int(prio), int(tid)),
                )
            conn.commit()
            return {"ok": True, "count": len(items)}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(500, f"Error reordenando: {e}")

