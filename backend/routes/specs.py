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

from database import get_db, row_to_dict, MARCA_SUBQUERY
from routes.auth import get_session
from services.clasificador_heuristico import clasificar_lote
from services.nombre_service import (
    actualizar_nombres_de,
    calcular_nombres_para,
    regenerar_nombres_todos,
)
from services.ranking_service import recalcular_ranking_todos
from services.spec_persist import persistir_specs, _validate_tabla_value


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


class EquipoSpecsInput(BaseModel):
    """Diccionario `{spec_def_id (str): value}`. Reemplaza TODAS las specs
    del equipo. Las keys del dict son strings (JSON) pero se interpretan
    como int en el backend."""
    specs: dict[str, str]


class RegenerarNombresInput(BaseModel):
    dry_run: bool = True


class RecalcularRankingInput(BaseModel):
    dry_run: bool = True
    ventana_dias: int = 180


class AplicarClasificacionInput(BaseModel):
    """Aplica categorías a equipos. Acepta `categoria_ids` (lista de ids
    de categorías a asignar a ese equipo, reemplaza lo que tenga)."""
    asignaciones: list[dict]   # [{equipo_id, categoria_ids: [int]}]


class CompatibilidadInput(BaseModel):
    equipo_b_id: int
    tipo: str   # "compatible" | "incompatible" | "requiere_adaptador"
    nota: Optional[str] = None
    adaptador_id: Optional[int] = None


class AprobarNombreInput(BaseModel):
    override: Optional[str] = None   # Si se manda, queda como override manual.
    revisado: bool = True             # Si False, vuelve a "pendiente".


# ── Compatibilidad asistida por IA ─────────────────────────────────────
# Modelos para el skill `/compat` que escribe compat auto-generadas en
# bulk. Las manuales (auto_generado=false) nunca se tocan; las auto se
# reemplazan en cada pasada.

class CompatBulkItem(BaseModel):
    equipo_a_id: int
    equipo_b_id: int
    tipo: str   # "compatible" | "incompatible" | "requiere_adaptador"
    nota: Optional[str] = None
    adaptador_id: Optional[int] = None
    razon_ia: Optional[str] = None
    confianza: Optional[float] = None   # 0..1


class CompatBulkInput(BaseModel):
    # Equipos cuyo lado A se está procesando. Las auto previas de estos
    # equipos se borran antes de insertar las nuevas.
    equipos_procesados: list[int]
    items: list[CompatBulkItem]


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
    conn = get_db()
    try:
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
    finally:
        conn.close()


@router.get("/admin/specs/por-categoria")
def listar_specs_por_categoria(request: Request):
    """Devuelve specs agrupadas por categoría raíz (Cámaras, Lentes, …) con
    los flags persistentes y el conteo de equipos que la tienen cargada.
    Usado por la UI consolidada de /admin/specs (drag-and-drop + favoritos)."""
    _require_admin(request)
    conn = get_db()
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
    finally:
        conn.close()


@router.get("/admin/specs/diagnostico")
def diagnostico_specs(request: Request):
    """Devuelve info de estado del subsistema specs — útil para diagnosticar
    500s desde la UI admin sin tener acceso a logs."""
    _require_admin(request)
    conn = get_db()
    try:
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
    finally:
        conn.close()


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
    conn = get_db()
    try:
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
    finally:
        conn.close()


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
    conn = get_db()
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
    finally:
        conn.close()


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
    conn = get_db()
    try:
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
    finally:
        conn.close()


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
    conn = get_db()
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
    finally:
        conn.close()

@router.delete("/admin/spec-definitions/{def_id}", status_code=204)
def borrar_spec_definition(def_id: int, request: Request):
    _require_admin(request)
    conn = get_db()
    try:
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
    finally:
        conn.close()


# ── CRUD: Asignaciones de spec_definitions a categorías ────────────────

@router.get("/admin/spec-templates/resumen")
def resumen_templates(request: Request):
    """Devuelve conteo de specs por categoría para el overview del editor."""
    _require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT categoria_id, COUNT(*) as total
            FROM categoria_spec_templates
            GROUP BY categoria_id
            """
        ).fetchall()
        return {r["categoria_id"]: r["total"] for r in rows}
    finally:
        conn.close()


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
    conn = get_db()
    try:
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
    finally:
        conn.close()


@router.get("/admin/categorias/{categoria_id}/spec-templates/orphans")
def listar_orphan_specs(categoria_id: int, request: Request):
    """Devuelve spec_definitions cargadas en equipo_specs de equipos de
    esta categoría que NO están asignadas al template de la categoría.

    Útil para sugerir al admin formalizar specs custom (que ya tienen
    valores en equipos pero no están en el template oficial).

    Devuelve: [{spec_def_id, spec_key, label, count_equipos, sample_values[≤3]}].
    """
    _require_admin(request)
    conn = get_db()
    try:
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
    finally:
        conn.close()


@router.post("/admin/categorias/{categoria_id}/spec-templates", status_code=201)
def asignar_spec_a_categoria(categoria_id: int, payload: SpecAssignmentInput, request: Request):
    """Asigna una spec_definition existente a una categoría con flags propios.
    Para crear una spec nueva globalmente usar POST /admin/spec-definitions
    y después asignar acá."""
    _require_admin(request)
    conn = get_db()
    try:
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
    finally:
        conn.close()


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
    conn = get_db()
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
    finally:
        conn.close()


@router.delete("/admin/spec-templates/{template_id}", status_code=204)
def borrar_asignacion(template_id: int, request: Request):
    """Desasigna la spec de la categoría (no toca la spec_definition global)."""
    _require_admin(request)
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM categoria_spec_templates WHERE id = ?", (template_id,)
        )
        conn.commit()
        # NOTA: equipo_specs NO se borra al desasignar — los valores cargados
        # quedan como "huérfanos" hasta que el dueño los borre desde la UI.
    finally:
        conn.close()


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
    conn = get_db()
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
    finally:
        conn.close()


# ── Specs por equipo ────────────────────────────────────────────────────

@router.get("/admin/equipos/{equipo_id}/specs")
def obtener_specs_equipo(equipo_id: int, request: Request):
    """Devuelve las specs estructuradas del equipo + el template aplicable
    (todas las categorías del equipo unidas, con dedup por spec_def). Las
    keys del dict `specs` son strings stringificadas del spec_def_id (JSON
    no soporta int keys)."""
    _require_admin(request)
    conn = get_db()
    try:
        eq = conn.execute(
            "SELECT id FROM equipos WHERE id = ?", (equipo_id,)
        ).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no existe")

        # Specs ya cargadas
        spec_rows = conn.execute(
            "SELECT spec_def_id, value FROM equipo_specs WHERE equipo_id = ?",
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
            "SELECT categoria_specs FROM equipos WHERE id = ?", (equipo_id,)
        ).fetchone()
        categoria_specs = (
            row_to_dict(cs_row).get("categoria_specs") if cs_row else None
        )

        template: list[dict] = []
        if categoria_specs:
            cat_row = conn.execute(
                "SELECT id FROM categorias WHERE nombre = ? AND parent_id IS NULL",
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
                    WHERE sd.categoria_raiz_id = ?
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
    finally:
        conn.close()


@router.put("/admin/equipos/{equipo_id}/specs")
def reemplazar_specs_equipo(equipo_id: int, payload: EquipoSpecsInput, request: Request):
    """Reemplaza TODAS las specs del equipo. Body shape:
    {specs: { "<spec_def_id>": "value" }}. Las keys son ints stringificados."""
    _require_admin(request)
    conn = get_db()
    try:
        eq = conn.execute(
            "SELECT id FROM equipos WHERE id = ?", (equipo_id,)
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
            placeholders = ",".join(["?"] * len(keys_int))
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
    finally:
        conn.close()


# ── Regenerar nombres masivo ────────────────────────────────────────────

@router.post("/admin/equipos/regenerar-nombres")
def regenerar_nombres(payload: RegenerarNombresInput, request: Request):
    """Recalcula `nombre_publico` y `nombre_publico_largo` de todos los
    equipos. Modo dry-run por default — devuelve preview sin escribir."""
    _require_admin(request)
    conn = get_db()
    try:
        result = regenerar_nombres_todos(conn, dry_run=payload.dry_run)
        # Cap de respuesta para que no se pase de tamaño con 1000 equipos
        if len(result["cambios"]) > 200:
            result["cambios_truncados"] = True
            result["cambios_total"] = len(result["cambios"])
            result["cambios"] = result["cambios"][:200]
        return result
    finally:
        conn.close()


@router.get("/admin/equipos/{equipo_id}/nombre-publico-preview")
def preview_nombre_publico(equipo_id: int, request: Request):
    """Calcula y devuelve el nombre público de un equipo (sin escribir).
    Útil para que el form admin muestre cómo va a quedar el nombre antes
    de guardar."""
    _require_admin(request)
    conn = get_db()
    try:
        try:
            corto, largo = calcular_nombres_para(conn, equipo_id)
            return {
                "equipo_id": equipo_id,
                "nombre_publico": corto,
                "nombre_publico_largo": largo,
            }
        except ValueError as e:
            raise HTTPException(404, str(e))
    finally:
        conn.close()


# ── Recalcular ranking ───────────────────────────────────────────────────

@router.post("/admin/equipos/recalcular-ranking")
def recalcular_ranking(payload: RecalcularRankingInput, request: Request):
    """Recalcula `popularidad_score`, `cant_pedidos` e `ingreso_total_ars`
    para todos los equipos, basado en el historial de alquileres en la
    ventana especificada (180 días por default)."""
    _require_admin(request)
    if payload.ventana_dias < 1 or payload.ventana_dias > 3650:
        raise HTTPException(400, "ventana_dias debe estar entre 1 y 3650")
    conn = get_db()
    try:
        result = recalcular_ranking_todos(
            conn,
            dry_run=payload.dry_run,
            ventana_dias=payload.ventana_dias,
        )
        if len(result["cambios"]) > 200:
            result["cambios_truncados"] = True
            result["cambios_total"] = len(result["cambios"])
            result["cambios"] = result["cambios"][:200]
        return result
    finally:
        conn.close()


# ── Clasificación masiva de categorías (PR C) ───────────────────────────

@router.post("/admin/equipos/clasificar-bulk")
def clasificar_bulk(request: Request, payload: dict = None):
    """Genera sugerencias de categoría para los equipos solicitados.
    NO escribe nada. Devuelve `{items: [{equipo_id, nombre, raiz, sub,
    confianza, razon, raiz_id, sub_id, foto_url}]}`.

    Body opcional:
      - solo_sin_categoria: bool (default True) — sólo equipos que no
        tienen ninguna categoría asignada.
      - equipo_ids: list[int] — limitar a estos ids específicos.
    """
    _require_admin(request)
    payload = payload or {}
    solo_sin = payload.get("solo_sin_categoria", True)
    equipo_ids = payload.get("equipo_ids") or []

    conn = get_db()
    try:
        # El centinela del Estudio no es un producto: nunca entra al flujo de specs.
        where = ["e.es_recurso_interno = FALSE"]
        params: list = []
        if equipo_ids:
            placeholders = ",".join(["?"] * len(equipo_ids))
            where.append(f"e.id IN ({placeholders})")
            params.extend(int(i) for i in equipo_ids)
        elif solo_sin:
            where.append(
                "NOT EXISTS (SELECT 1 FROM equipo_categorias ec WHERE ec.equipo_id = e.id)"
            )

        clause = "WHERE " + " AND ".join(where)
        rows = conn.execute(
            f"SELECT e.id, e.nombre, (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca, e.modelo, e.foto_url "
            f"FROM equipos e {clause} ORDER BY e.nombre",
            tuple(params),
        ).fetchall()

        equipos = [
            {"id": r["id"], "nombre": r["nombre"], "marca": r["marca"], "modelo": r["modelo"]}
            for r in rows
        ]
        sugerencias = clasificar_lote(equipos)

        # Resolver los ids de las categorías sugeridas (raíz y sub) para
        # que el frontend pueda renderear directamente.
        cat_rows = conn.execute(
            "SELECT id, nombre, parent_id, "
            "       (SELECT nombre FROM categorias WHERE id = c.parent_id) AS parent_nombre "
            "FROM categorias c"
        ).fetchall()
        by_name_raiz: dict[str, int] = {}
        by_name_sub: dict[tuple[str, str], int] = {}
        for c in cat_rows:
            if c["parent_id"] is None:
                by_name_raiz[c["nombre"]] = c["id"]
            else:
                by_name_sub[(c["parent_nombre"], c["nombre"])] = c["id"]

        foto_by_id = {r["id"]: r["foto_url"] for r in rows}
        for s in sugerencias:
            s["foto_url"] = foto_by_id.get(s["equipo_id"])
            raiz = s.get("raiz")
            sub = s.get("sub")
            s["raiz_id"] = by_name_raiz.get(raiz) if raiz else None
            s["sub_id"] = by_name_sub.get((raiz, sub)) if (raiz and sub) else None

        alta = sum(1 for s in sugerencias if (s.get("confianza") or 0) >= 0.85)
        media = sum(1 for s in sugerencias if 0.7 <= (s.get("confianza") or 0) < 0.85)
        baja = sum(1 for s in sugerencias if 0 < (s.get("confianza") or 0) < 0.7)
        sin_clasif = sum(1 for s in sugerencias if not s.get("raiz"))
        return {
            "total": len(sugerencias),
            "alta_confianza": alta,
            "media_confianza": media,
            "baja_confianza": baja,
            "sin_clasificar": sin_clasif,
            "items": sugerencias,
        }
    finally:
        conn.close()


@router.post("/admin/equipos/aplicar-clasificacion")
def aplicar_clasificacion(payload: AplicarClasificacionInput, request: Request):
    """Aplica categorías a una lista de equipos. Para cada equipo en
    `asignaciones`, REEMPLAZA las categorías existentes por las nuevas.

    Después de aplicar, recalcula nombre_publico para cada equipo
    afectado (la categoría cambia el template aplicable)."""
    _require_admin(request)

    if not payload.asignaciones:
        raise HTTPException(400, "asignaciones vacío")

    conn = get_db()
    aplicados = []
    errores = []
    try:
        for asig in payload.asignaciones:
            try:
                eq_id = int(asig.get("equipo_id"))
                cat_ids = [int(c) for c in (asig.get("categoria_ids") or [])]
            except (TypeError, ValueError):
                errores.append({"equipo_id": asig.get("equipo_id"), "error": "ids inválidos"})
                continue

            conn.execute("DELETE FROM equipo_categorias WHERE equipo_id = ?", (eq_id,))
            for orden, cat_id in enumerate(cat_ids):
                conn.execute(
                    "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) "
                    "VALUES (?, ?, ?) ON CONFLICT (equipo_id, categoria_id) DO NOTHING",
                    (eq_id, cat_id, orden),
                )
            try:
                actualizar_nombres_de(conn, eq_id, commit=False)
            except Exception:
                pass
            aplicados.append(eq_id)

        conn.commit()
        return {
            "aplicados": len(aplicados),
            "errores": errores,
            "equipo_ids": aplicados,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.get("/admin/equipos/sin-categoria")
def listar_sin_categoria(request: Request):
    """Cuenta los equipos sin ninguna categoría asignada (para badge nav)."""
    _require_admin(request)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM equipos e "
            "WHERE e.es_recurso_interno = FALSE "
            "AND NOT EXISTS (SELECT 1 FROM equipo_categorias ec WHERE ec.equipo_id = e.id)"
        ).fetchone()
        return {"total": row["cnt"]}
    finally:
        conn.close()


# ── Compatibilidades entre equipos ──────────────────────────────────────

@router.get("/admin/equipos/{equipo_id}/compatibilidades")
def listar_compatibilidades(equipo_id: int, request: Request):
    """Devuelve las compatibilidades del equipo (tanto donde es A como B)
    para presentación bidireccional. Cada item viene con el OTRO equipo
    expandido (nombre + foto + ids)."""
    _require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT
                ec.id, ec.equipo_a_id, ec.equipo_b_id, ec.tipo, ec.nota,
                ec.adaptador_id, ec.created_at,
                ec.auto_generado, ec.razon_ia, ec.confianza,
                CASE WHEN ec.equipo_a_id = ? THEN ec.equipo_b_id ELSE ec.equipo_a_id END AS otro_id,
                eb.nombre AS otro_nombre, eb.foto_url AS otro_foto,
                ea.nombre AS adaptador_nombre
            FROM equipo_compatibilidad ec
            LEFT JOIN equipos eb ON eb.id = CASE
                WHEN ec.equipo_a_id = ? THEN ec.equipo_b_id ELSE ec.equipo_a_id END
            LEFT JOIN equipos ea ON ea.id = ec.adaptador_id
            WHERE ec.equipo_a_id = ? OR ec.equipo_b_id = ?
            ORDER BY ec.auto_generado ASC, ec.tipo, eb.nombre
            """,
            (equipo_id, equipo_id, equipo_id, equipo_id),
        ).fetchall()
        items = []
        for r in rows:
            items.append({
                "id": r["id"],
                "otro_id": r["otro_id"],
                "otro_nombre": r["otro_nombre"],
                "otro_foto": r["otro_foto"],
                "tipo": r["tipo"],
                "nota": r["nota"],
                "adaptador_id": r["adaptador_id"],
                "adaptador_nombre": r["adaptador_nombre"],
                "auto_generado": bool(r["auto_generado"]),
                "razon_ia": r["razon_ia"],
                "confianza": r["confianza"],
            })
        return {"items": items}
    finally:
        conn.close()


@router.post("/admin/equipos/{equipo_id}/compatibilidades", status_code=201)
def crear_compatibilidad(equipo_id: int, payload: CompatibilidadInput, request: Request):
    """Crea una relación de compatibilidad. `equipo_id` es A, `equipo_b_id`
    el otro. La tabla tiene CHECK que evita duplicados (a,b,tipo)."""
    _require_admin(request)
    if payload.tipo not in ("compatible", "incompatible", "requiere_adaptador"):
        raise HTTPException(400, f"tipo inválido: {payload.tipo}")
    if payload.equipo_b_id == equipo_id:
        raise HTTPException(400, "No se puede relacionar un equipo consigo mismo")
    conn = get_db()
    try:
        # Verificar que ambos existen
        a_exists = conn.execute("SELECT id FROM equipos WHERE id = ?", (equipo_id,)).fetchone()
        b_exists = conn.execute("SELECT id FROM equipos WHERE id = ?", (payload.equipo_b_id,)).fetchone()
        if not a_exists or not b_exists:
            raise HTTPException(404, "Equipo no encontrado")
        if payload.adaptador_id:
            ad = conn.execute("SELECT id FROM equipos WHERE id = ?", (payload.adaptador_id,)).fetchone()
            if not ad:
                raise HTTPException(404, "Adaptador no encontrado")
        try:
            cur = conn.execute(
                """
                INSERT INTO equipo_compatibilidad
                  (equipo_a_id, equipo_b_id, tipo, nota, adaptador_id)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id
                """,
                (equipo_id, payload.equipo_b_id, payload.tipo, payload.nota, payload.adaptador_id),
            )
            new_id = cur.fetchone()[0]
            conn.commit()
            return {"id": new_id, "equipo_a_id": equipo_id, **payload.model_dump()}
        except Exception as e:
            conn.rollback()
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                raise HTTPException(409, "Esa compatibilidad ya existe")
            raise
    finally:
        conn.close()


@router.delete("/admin/compatibilidades/{compat_id}", status_code=204)
def borrar_compatibilidad(compat_id: int, request: Request):
    _require_admin(request)
    conn = get_db()
    try:
        conn.execute("DELETE FROM equipo_compatibilidad WHERE id = ?", (compat_id,))
        conn.commit()
    finally:
        conn.close()


# ── Compatibilidad automática (#F4) ─────────────────────────────────────
# Algoritmo: encuentra equipos que comparten al menos una spec marcada
# es_compatibilidad=true con el equipo base, calcula el match para cada spec
# (exacta o jerarquia), agrega overrides manuales de equipo_compatibilidad y
# devuelve un overall + razones.

# Familias jerárquicas dentro de specs multi_enum. La lógica de compat aplica
# "mínimo común" por familia cuando dos equipos comparten familia pero no
# versión exacta (ej. cámara HDMI 2.1 + monitor HDMI 2.0 → ambos hablan 2.0).
#
# Las familias viven en la tabla `spec_familia_jerarquia` (editable desde
# `/admin/specs/familias`). Este dict queda como FALLBACK para cuando la
# tabla está vacía (pre-migration o BD nueva sin seed).
_FAMILIES_FALLBACK: dict[str, list[str]] = {
    "HDMI": ["HDMI 1.4", "HDMI 2.0", "HDMI 2.1"],
    "SDI":  ["SDI 3G", "SDI 6G", "SDI 12G"],
}


def _load_families_from_db() -> dict[str, list[str]]:
    """Lee la tabla `spec_familia_jerarquia` y devuelve `{familia: [valores ordenados por posicion]}`.
    El nombre de familia en el dict mantiene el casing del display
    (HDMI/SDI). Si la tabla está vacía o falla, devuelve `_FAMILIES_FALLBACK`."""
    try:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT familia, valor, posicion FROM spec_familia_jerarquia "
                "ORDER BY familia, posicion"
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return dict(_FAMILIES_FALLBACK)

    if not rows:
        return dict(_FAMILIES_FALLBACK)

    out: dict[str, list[str]] = {}
    for r in rows:
        d = row_to_dict(r) if not isinstance(r, dict) else r
        fam_norm = (d.get("familia") or "").strip()
        # Display name = uppercase si todo el valor empieza con el familia
        # (HDMI/SDI casos). Sino, capitalize.
        fam_display = fam_norm.upper() if len(fam_norm) <= 4 else fam_norm.capitalize()
        out.setdefault(fam_display, []).append(d.get("valor"))
    return out


# Alias retro-compat: el código existente usa `_MULTI_ENUM_FAMILIES` como
# un dict. Lo hacemos `property-like` consultando DB on demand.
class _FamiliesProxy:
    """Compatibilidad: actúa como dict pero hidrata de DB cada vez que
    se itera/lee. Caché de 60s para no martillar la BD en el motor de
    compat que itera por cada par de equipos."""
    _cache: dict[str, list[str]] = {}
    _cache_at: float = 0.0
    _ttl = 60.0

    def _refresh_if_needed(self) -> dict[str, list[str]]:
        import time
        now = time.time()
        if now - self._cache_at > self._ttl:
            self._cache = _load_families_from_db()
            self._cache_at = now
        return self._cache

    def items(self):
        return self._refresh_if_needed().items()

    def __iter__(self):
        return iter(self._refresh_if_needed())

    def __getitem__(self, key):
        return self._refresh_if_needed()[key]

    def __contains__(self, key):
        return key in self._refresh_if_needed()

    def get(self, key, default=None):
        return self._refresh_if_needed().get(key, default)

    def invalidate(self):
        """Borrar cache. Llamar después de CRUD a `spec_familia_jerarquia`."""
        self._cache_at = 0.0


_MULTI_ENUM_FAMILIES = _FamiliesProxy()


def _parse_multi_enum_value(value: str) -> list[str]:
    """Parsea un value de multi_enum desde su storage TEXT. El frontend lo
    guarda como string CSV-ish: 'HDMI 2.0, SDI 12G'. Aceptamos también JSON
    array por si vino del autocompletar IA."""
    if not value:
        return []
    v = value.strip()
    if v.startswith("["):
        try:
            arr = json.loads(v)
            return [str(x).strip() for x in arr if x]
        except Exception:
            pass
    return [p.strip() for p in v.split(",") if p.strip()]


def _compute_multi_enum_compat(label: str, a_val: str, b_val: str) -> dict:
    """Lógica de compat para multi_enum (ej. video_out).

    Orden de prioridad:
      1. Match exacto: comparten al menos un valor idéntico → status='match'.
      2. Match jerárquico intra-familia: comparten familia pero distintas
         versiones → status='match' con mensaje "limitado a versión mínima común".
      3. Sin overlap: distintas familias o sin valores comunes → status='mismatch'.
    """
    a_set = set(_parse_multi_enum_value(a_val))
    b_set = set(_parse_multi_enum_value(b_val))
    if not a_set or not b_set:
        return {"spec": label, "status": "mismatch",
                "mensaje": f"{label}: uno de los dos no tiene valores cargados"}

    # 1. Intersection directa
    common = a_set & b_set
    if common:
        return {"spec": label, "status": "match",
                "mensaje": f"{label}: comparten {', '.join(sorted(common))}"}

    # 2. Match jerárquico intra-familia
    common_versions = []
    for family_name, order in _MULTI_ENUM_FAMILIES.items():
        a_in_fam = [v for v in a_set if v in order]
        b_in_fam = [v for v in b_set if v in order]
        if not (a_in_fam and b_in_fam):
            continue
        # "El mejor que cada uno tiene" en esa familia
        a_best = max(a_in_fam, key=lambda v: order.index(v))
        b_best = max(b_in_fam, key=lambda v: order.index(v))
        # Versión común = el menor de los dos máximos
        min_idx = min(order.index(a_best), order.index(b_best))
        common_versions.append({
            "family": family_name,
            "version": order[min_idx],
            "a_best": a_best, "b_best": b_best,
        })

    if common_versions:
        partes = [
            f"{cv['family']} a {cv['version']}"
            + (f" (A: {cv['a_best']}, B: {cv['b_best']})"
               if cv["a_best"] != cv["b_best"] else "")
            for cv in common_versions
        ]
        return {"spec": label, "status": "match",
                "mensaje": f"{label}: compatible vía {', '.join(partes)} (versión mínima común)"}

    # 3. Sin overlap
    return {"spec": label, "status": "mismatch",
            "mensaje": f"{label}: sin conectores en común (A: {', '.join(sorted(a_set))} · B: {', '.join(sorted(b_set))})"}


def _compute_compat(conn, equipo_a_id: int, equipo_b_id: int) -> dict:
    """Devuelve {overall, razones, adaptador?} para el par (A, B).

    overall ∈ {compatible, compatible_con_crop, parcial, incompatible,
               requiere_adaptador, sin_relacion}
    razones: lista de {spec, status, mensaje}
    """
    # 1. Manual override (gana).
    manual = conn.execute(
        """
        SELECT ec.tipo, ec.nota, ec.adaptador_id,
               a.nombre AS adaptador_nombre
        FROM equipo_compatibilidad ec
        LEFT JOIN equipos a ON a.id = ec.adaptador_id
        WHERE (ec.equipo_a_id = ? AND ec.equipo_b_id = ?)
           OR (ec.equipo_a_id = ? AND ec.equipo_b_id = ?)
        LIMIT 1
        """,
        (equipo_a_id, equipo_b_id, equipo_b_id, equipo_a_id),
    ).fetchone()

    if manual and manual["tipo"] == "incompatible":
        return {
            "overall": "incompatible",
            "razones": [],
            "razon": manual["nota"] or "Marcado como incompatible manualmente",
        }
    if manual and manual["tipo"] == "requiere_adaptador":
        return {
            "overall": "requiere_adaptador",
            "razones": [],
            "razon": manual["nota"] or "",
            "adaptador": (
                {"id": manual["adaptador_id"], "nombre": manual["adaptador_nombre"]}
                if manual["adaptador_id"]
                else None
            ),
        }

    # 2. Auto-match por specs compartidas con es_compatibilidad=TRUE.
    spec_rows = conn.execute(
        """
        SELECT
          esa.spec_def_id, esa.value AS a_value, esb.value AS b_value,
          sd.spec_key, sd.label, sd.tipo,
          COALESCE(sd.compatibilidad_modo, 'exacta') AS modo,
          sd.enum_options,
          (SELECT rol_compatibilidad FROM categoria_spec_templates t
            JOIN equipo_categorias ec ON ec.categoria_id = t.categoria_id
            WHERE ec.equipo_id = ? AND t.spec_def_id = sd.id
            LIMIT 1) AS a_rol,
          (SELECT rol_compatibilidad FROM categoria_spec_templates t
            JOIN equipo_categorias ec ON ec.categoria_id = t.categoria_id
            WHERE ec.equipo_id = ? AND t.spec_def_id = sd.id
            LIMIT 1) AS b_rol
        FROM equipo_specs esa
        JOIN equipo_specs esb ON esb.spec_def_id = esa.spec_def_id
        JOIN spec_definitions sd ON sd.id = esa.spec_def_id
        WHERE esa.equipo_id = ? AND esb.equipo_id = ?
          AND sd.es_compatibilidad = TRUE
        """,
        (equipo_a_id, equipo_b_id, equipo_a_id, equipo_b_id),
    ).fetchall()

    razones: list[dict] = []
    for r in spec_rows:
        modo = r["modo"]
        tipo = r["tipo"]
        a_val, b_val = r["a_value"], r["b_value"]
        label = r["label"]
        if modo == "exacta":
            # multi_enum tiene su propia lógica: intersection + jerarquía
            # intra-familia (HDMI 2.1/2.0, SDI 12G/6G/3G).
            if tipo == "multi_enum":
                razones.append(_compute_multi_enum_compat(label, a_val, b_val))
            elif a_val == b_val:
                razones.append({"spec": label, "status": "match", "mensaje": f"{label}: {a_val}"})
            else:
                razones.append({"spec": label, "status": "mismatch",
                                "mensaje": f"{label}: {a_val} ≠ {b_val}"})
        elif modo == "jerarquia":
            enum_opts = r["enum_options"]
            if isinstance(enum_opts, str):
                try:
                    enum_opts = json.loads(enum_opts)
                except Exception:
                    enum_opts = []
            if not enum_opts:
                razones.append({"spec": label, "status": "match",
                                "mensaje": f"{label}: {a_val} (sin escala definida)"})
                continue
            try:
                a_pos = enum_opts.index(a_val)
                b_pos = enum_opts.index(b_val)
            except ValueError:
                razones.append({"spec": label, "status": "mismatch",
                                "mensaje": f"{label}: valor fuera de la escala definida"})
                continue
            a_rol = r["a_rol"]
            b_rol = r["b_rol"]
            if a_pos == b_pos:
                razones.append({"spec": label, "status": "match",
                                "mensaje": f"{label}: {a_val}"})
            elif {a_rol, b_rol} == {"contenedor", "contenido"}:
                if a_rol == "contenedor":
                    cont_val, conf_val, cont_pos, conf_pos = a_val, b_val, a_pos, b_pos
                else:
                    cont_val, conf_val, cont_pos, conf_pos = b_val, a_val, b_pos, a_pos
                if cont_pos >= conf_pos:
                    razones.append({
                        "spec": label, "status": "match_con_crop",
                        "mensaje": f"{label}: {cont_val} más grande que {conf_val} — usa solo el crop central",
                    })
                else:
                    razones.append({
                        "spec": label, "status": "partial_vignette",
                        "mensaje": f"{label}: {cont_val} más chico que {conf_val} → viñetea",
                    })
            else:
                razones.append({"spec": label, "status": "partial",
                                "mensaje": f"{label}: {a_val} vs {b_val} — tamaños difieren"})

    # 2.b. Cross-spec match: video_out (A) ↔ video_in (B), y video_in (A) ↔ video_out (B).
    # Permite detectar conexiones direccionales sin necesidad de que ambos equipos
    # tengan la misma spec. La cámara tiene solo video_out, el monitor solo video_in
    # — el sistema debe match cross y entender "A puede salir hacia B".
    cross_rows = conn.execute(
        """
        SELECT
          sd_a.spec_key AS a_key, sd_a.label AS a_label, esa.value AS a_value,
          sd_b.spec_key AS b_key, sd_b.label AS b_label, esb.value AS b_value
        FROM equipo_specs esa
        JOIN spec_definitions sd_a ON sd_a.id = esa.spec_def_id
        JOIN equipo_specs esb ON esb.equipo_id = ?
        JOIN spec_definitions sd_b ON sd_b.id = esb.spec_def_id
        WHERE esa.equipo_id = ?
          AND (
            (sd_a.spec_key = 'video_out' AND sd_b.spec_key = 'video_in')
            OR (sd_a.spec_key = 'video_in' AND sd_b.spec_key = 'video_out')
          )
        """,
        (equipo_b_id, equipo_a_id),
    ).fetchall()
    cross_pairs_seen: set[tuple[str, str]] = set()
    for cr in cross_rows:
        # Procesamos ambas direcciones (out→in y in→out) porque ambos son
        # conexiones reales. Dedup por par ordenado.
        key = tuple(sorted([cr["a_key"], cr["b_key"]]))
        if key in cross_pairs_seen:
            continue
        cross_pairs_seen.add(key)
        # Determinar quién es out y quién es in para el mensaje direccional
        if cr["a_key"] == "video_out":
            out_val, in_val = cr["a_value"], cr["b_value"]
            dir_label = "A→B"
        else:
            out_val, in_val = cr["b_value"], cr["a_value"]
            dir_label = "B→A"
        result = _compute_multi_enum_compat("Conexión video", out_val, in_val)
        # Reescribimos el mensaje para reflejar la direccionalidad
        if result["status"] == "match":
            result["mensaje"] = result["mensaje"].replace(
                "Conexión video: ", f"Conexión video: {dir_label} "
            )
        elif result["status"] == "mismatch":
            result["mensaje"] = (
                f"Conexión video: el out de {dir_label[0]} no matchea con "
                f"el in de {dir_label[-1]} (posiblemente requiere adaptador/converter)"
            )
        razones.append(result)

    # 3. Aggregate.
    statuses = {r["status"] for r in razones}
    if "mismatch" in statuses:
        overall = "incompatible"
    elif "partial_vignette" in statuses or "partial" in statuses:
        overall = "parcial"
    elif "match_con_crop" in statuses:
        overall = "compatible_con_crop"
    elif razones:
        overall = "compatible"
    else:
        overall = "sin_relacion"

    # Manual 'compatible' positivo: overrides parcial/incompatible.
    if manual and manual["tipo"] == "compatible" and overall in ("parcial", "incompatible"):
        overall = "compatible"

    return {"overall": overall, "razones": razones}


@router.get("/admin/equipos/{equipo_id}/compatibles")
def listar_compatibles(
    equipo_id: int,
    request: Request,
    categoria_id: Optional[int] = None,
    overall_min: Optional[str] = None,
):
    """Devuelve equipos que tienen alguna relación de compatibilidad con
    el equipo base (manual o derivada de specs).

    Filtros:
    - categoria_id: restringe los candidatos a esa categoría (recursiva).
    - overall_min: solo devuelve equipos con overall ≥ este (compatible,
      compatible_con_crop, parcial, requiere_adaptador). Default: todos
      menos sin_relacion e incompatible.
    """
    _require_admin(request)
    conn = get_db()
    try:
        eq = conn.execute(
            "SELECT id FROM equipos WHERE id = ? AND eliminado_at IS NULL",
            (equipo_id,),
        ).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no existe")

        # Candidatos = equipos que (a) comparten al menos una spec con es_compat
        # OR (b) tienen una entrada manual en equipo_compatibilidad.
        spec_candidatos_sql = """
            SELECT DISTINCT esb.equipo_id AS id
            FROM equipo_specs esa
            JOIN equipo_specs esb ON esb.spec_def_id = esa.spec_def_id
            JOIN spec_definitions sd ON sd.id = esa.spec_def_id
            WHERE esa.equipo_id = ?
              AND esb.equipo_id != ?
              AND sd.es_compatibilidad = TRUE
        """
        manual_candidatos_sql = """
            SELECT DISTINCT
              CASE WHEN ec.equipo_a_id = ? THEN ec.equipo_b_id ELSE ec.equipo_a_id END AS id
            FROM equipo_compatibilidad ec
            WHERE ec.equipo_a_id = ? OR ec.equipo_b_id = ?
        """
        candidates_sql = f"""
            SELECT e.id, e.nombre, (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca, e.foto_url
            FROM equipos e
            WHERE e.eliminado_at IS NULL AND e.id IN (
              {spec_candidatos_sql}
              UNION
              {manual_candidatos_sql}
            )
        """
        params = [equipo_id, equipo_id, equipo_id, equipo_id, equipo_id]
        if categoria_id:
            candidates_sql += """
              AND e.id IN (
                SELECT ec.equipo_id FROM equipo_categorias ec
                WHERE ec.categoria_id IN (
                  WITH RECURSIVE sub AS (
                    SELECT id FROM categorias WHERE id = ?
                    UNION ALL
                    SELECT c.id FROM categorias c JOIN sub ON c.parent_id = sub.id
                  )
                  SELECT id FROM sub
                )
              )
            """
            params.append(categoria_id)
        candidates_sql += " ORDER BY e.nombre"

        candidates = conn.execute(candidates_sql, params).fetchall()

        items = []
        for c in candidates:
            result = _compute_compat(conn, equipo_id, c["id"])
            items.append({
                "equipo_id": c["id"],
                "nombre": c["nombre"],
                "marca": c["marca"],
                "foto_url": c["foto_url"],
                **result,
            })

        # Filtro overall_min: default = excluir sin_relacion e incompatible.
        if overall_min is None:
            items = [i for i in items if i["overall"] not in ("sin_relacion", "incompatible")]
        else:
            order = ["sin_relacion", "incompatible", "parcial", "compatible_con_crop",
                     "requiere_adaptador", "compatible"]
            if overall_min in order:
                threshold = order.index(overall_min)
                items = [i for i in items if i["overall"] in order
                         and order.index(i["overall"]) >= threshold]

        return {"items": items, "total": len(items)}
    finally:
        conn.close()


# ── Aprobar / overridear nombre público ─────────────────────────────────

@router.put("/admin/equipos/{equipo_id}/nombre-publico")
def aprobar_o_editar_nombre(equipo_id: int, payload: AprobarNombreInput, request: Request):
    """Marca un nombre como revisado y opcionalmente lo overridea.
      - override=null + revisado=true → mantener el auto-generado, marcar como aprobado.
      - override="texto" + revisado=true → guardar override manual.
      - revisado=false → volver a "pendiente" (descarta override).
    """
    _require_admin(request)
    conn = get_db()
    try:
        eq = conn.execute("SELECT id FROM equipos WHERE id = ?", (equipo_id,)).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no existe")

        override = payload.override.strip() if (payload.override and payload.override.strip()) else None

        if not payload.revisado:
            # Volver a pendiente: descartar override y recalcular auto.
            conn.execute(
                "UPDATE equipos SET nombre_publico_override = NULL, "
                "nombre_publico_revisado = FALSE WHERE id = ?",
                (equipo_id,),
            )
            try:
                actualizar_nombres_de(conn, equipo_id, commit=False)
            except Exception:
                pass
        else:
            conn.execute(
                "UPDATE equipos SET nombre_publico_override = ?, "
                "nombre_publico_revisado = TRUE WHERE id = ?",
                (override, equipo_id),
            )
            # Si override está seteado, recalculamos para que nombre_publico
            # también lo refleje (el builder respeta el override).
            try:
                actualizar_nombres_de(conn, equipo_id, commit=False)
            except Exception:
                pass
        conn.commit()
        row = conn.execute(
            "SELECT id, nombre_publico, nombre_publico_largo, "
            "nombre_publico_override, nombre_publico_revisado "
            "FROM equipos WHERE id = ?",
            (equipo_id,),
        ).fetchone()
        return row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.get("/admin/equipos/nombres-validacion")
def listar_para_validacion(request: Request, filtro: str = "all"):
    """Lista equipos con su nombre auto y override para la UI de validación.

    `filtro`:
      - "pendientes" → revisado=FALSE
      - "aprobados"  → revisado=TRUE AND override IS NULL
      - "editados"   → revisado=TRUE AND override IS NOT NULL
      - "all"        → todos
    """
    _require_admin(request)
    # El centinela del Estudio no es un producto: queda fuera del nombre público.
    conds = ["es_recurso_interno = FALSE"]
    if filtro == "pendientes":
        conds.append("COALESCE(nombre_publico_revisado, FALSE) = FALSE")
    elif filtro == "aprobados":
        conds.append("nombre_publico_revisado = TRUE AND nombre_publico_override IS NULL")
    elif filtro == "editados":
        conds.append("nombre_publico_revisado = TRUE AND nombre_publico_override IS NOT NULL")
    where = "WHERE " + " AND ".join(conds)

    conn = get_db()
    try:
        rows = conn.execute(
            f"""
            SELECT e.id, e.nombre, {MARCA_SUBQUERY}, e.modelo, e.foto_url,
                   e.nombre_publico, e.nombre_publico_largo,
                   e.nombre_publico_override,
                   COALESCE(e.nombre_publico_revisado, FALSE) AS revisado
            FROM equipos e
            {where}
            ORDER BY LOWER(COALESCE(e.nombre_publico, e.nombre))
            """
        ).fetchall()
        # Counts globales
        counts = conn.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE COALESCE(nombre_publico_revisado, FALSE) = FALSE) AS pendientes,
                COUNT(*) FILTER (WHERE nombre_publico_revisado = TRUE AND nombre_publico_override IS NULL) AS aprobados,
                COUNT(*) FILTER (WHERE nombre_publico_revisado = TRUE AND nombre_publico_override IS NOT NULL) AS editados,
                COUNT(*) AS total
            FROM equipos
            WHERE es_recurso_interno = FALSE
            """
        ).fetchone()
        return {
            "items": [row_to_dict(r) for r in rows],
            "stats": {
                "pendientes": counts["pendientes"],
                "aprobados": counts["aprobados"],
                "editados": counts["editados"],
                "total": counts["total"],
            },
        }
    finally:
        conn.close()


# ── Compat asistida por IA (F6: skill gear-compatibility) ───────────────
# Endpoints consumidos por el skill .claude/skills/gear-compatibility.md
# para escribir compat auto-generadas y propuestas de specs.

@router.post("/admin/compat/bulk")
def compat_bulk(payload: CompatBulkInput, request: Request):
    """Escribe múltiples compat auto-generadas. Para cada equipo en
    equipos_procesados:
      1. Borra TODAS sus compat con auto_generado=true (regen limpia).
      2. Inserta los items con auto_generado=true.
      3. Marca compat_analizado_at = now().
    Las compat manuales (auto_generado=false) NUNCA se tocan.
    """
    _require_admin(request)
    if not payload.equipos_procesados:
        raise HTTPException(400, "equipos_procesados no puede estar vacío")

    valid_tipos = {"compatible", "incompatible", "requiere_adaptador"}
    for it in payload.items:
        if it.tipo not in valid_tipos:
            raise HTTPException(400, f"tipo inválido: {it.tipo}")
        if it.equipo_a_id == it.equipo_b_id:
            raise HTTPException(400, "equipo_a_id y equipo_b_id no pueden ser iguales")
        if it.confianza is not None and not (0.0 <= it.confianza <= 1.0):
            raise HTTPException(400, "confianza debe estar entre 0 y 1")

    conn = get_db()
    try:
        # 1. Verificar que todos los equipos existen.
        ids_referenciados = set(payload.equipos_procesados)
        for it in payload.items:
            ids_referenciados.add(it.equipo_a_id)
            ids_referenciados.add(it.equipo_b_id)
            if it.adaptador_id:
                ids_referenciados.add(it.adaptador_id)
        rows = conn.execute(
            "SELECT id FROM equipos WHERE id = ANY(%s) AND eliminado_at IS NULL",
            (list(ids_referenciados),),
        ).fetchall()
        existentes = {r["id"] for r in rows}
        faltantes = ids_referenciados - existentes
        if faltantes:
            raise HTTPException(404, f"Equipos no encontrados: {sorted(faltantes)}")

        # 2. Borrar auto previas de los equipos procesados.
        for eq_id in payload.equipos_procesados:
            conn.execute(
                """
                DELETE FROM equipo_compatibilidad
                WHERE auto_generado = TRUE
                  AND (equipo_a_id = ? OR equipo_b_id = ?)
                """,
                (eq_id, eq_id),
            )

        # 3. Insertar los nuevos.
        inserted = 0
        skipped_manual = 0
        for it in payload.items:
            # Si ya existe una manual entre este par + tipo, no la pisamos.
            manual_exists = conn.execute(
                """
                SELECT id FROM equipo_compatibilidad
                WHERE auto_generado = FALSE
                  AND tipo = ?
                  AND ((equipo_a_id = ? AND equipo_b_id = ?)
                    OR (equipo_a_id = ? AND equipo_b_id = ?))
                LIMIT 1
                """,
                (it.tipo, it.equipo_a_id, it.equipo_b_id,
                 it.equipo_b_id, it.equipo_a_id),
            ).fetchone()
            if manual_exists:
                skipped_manual += 1
                continue
            try:
                conn.execute(
                    """
                    INSERT INTO equipo_compatibilidad
                      (equipo_a_id, equipo_b_id, tipo, nota, adaptador_id,
                       auto_generado, razon_ia, confianza)
                    VALUES (?, ?, ?, ?, ?, TRUE, ?, ?)
                    """,
                    (it.equipo_a_id, it.equipo_b_id, it.tipo, it.nota,
                     it.adaptador_id, it.razon_ia, it.confianza),
                )
                inserted += 1
            except Exception as e:
                # Duplicate (a,b,tipo): ignorar — ya está
                if "duplicate" not in str(e).lower() and "unique" not in str(e).lower():
                    conn.rollback()
                    raise

        # 4. Marcar timestamp de análisis.
        conn.execute(
            "UPDATE equipos SET compat_analizado_at = CURRENT_TIMESTAMP "
            "WHERE id = ANY(%s)",
            (payload.equipos_procesados,),
        )
        conn.commit()
        return {
            "ok": True,
            "equipos_procesados": len(payload.equipos_procesados),
            "compat_inserted": inserted,
            "skipped_manual_override": skipped_manual,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.get("/admin/equipos/pendientes-compat")
def listar_pendientes_compat(request: Request, limit: int = 50):
    """Equipos que necesitan análisis de compat: nunca analizados o
    modificados después del último análisis. Lo consume el skill cuando
    se invoca `/gear-compat new`.
    """
    _require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT
                e.id, e.nombre, (SELECT nombre FROM marcas WHERE id = e.brand_id) AS marca, e.modelo,
                e.compat_analizado_at,
                e.updated_at,
                CASE
                  WHEN e.compat_analizado_at IS NULL THEN 'nunca_analizado'
                  WHEN e.updated_at > e.compat_analizado_at THEN 'modificado'
                  ELSE 'al_dia'
                END AS motivo,
                COALESCE(
                  (SELECT json_agg(c.nombre)
                   FROM equipo_categorias ec
                   JOIN categorias c ON c.id = ec.categoria_id
                   WHERE ec.equipo_id = e.id),
                  '[]'::json
                ) AS categorias
            FROM equipos e
            WHERE e.eliminado_at IS NULL
              AND (e.compat_analizado_at IS NULL
                   OR e.updated_at > e.compat_analizado_at)
            ORDER BY e.compat_analizado_at NULLS FIRST, e.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return {
            "total": len(rows),
            "items": [
                {
                    "id": r["id"],
                    "nombre": r["nombre"],
                    "marca": r["marca"],
                    "modelo": r["modelo"],
                    "categorias": r["categorias"] or [],
                    "compat_analizado_at": str(r["compat_analizado_at"]) if r["compat_analizado_at"] else None,
                    "motivo": r["motivo"],
                }
                for r in rows
            ],
        }
    finally:
        conn.close()


@router.get("/admin/equipos/{equipo_id}/contexto-compat")
def contexto_compat(equipo_id: int, request: Request):
    """Payload completo que el skill necesita para razonar sobre un equipo:
    datos base + specs cargadas con metadata de spec_definitions + raw_json
    del autocompletar + compat manuales existentes.
    """
    _require_admin(request)
    conn = get_db()
    try:
        eq = conn.execute(
            f"""
            SELECT e.id, e.nombre, {MARCA_SUBQUERY}, e.modelo, e.dueno
            FROM equipos e
            WHERE e.id = ? AND e.eliminado_at IS NULL
            """,
            (equipo_id,),
        ).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no existe")

        # Categorías
        cat_rows = conn.execute(
            """
            SELECT c.id, c.nombre, c.parent_id
            FROM equipo_categorias ec
            JOIN categorias c ON c.id = ec.categoria_id
            WHERE ec.equipo_id = ?
            ORDER BY c.nombre
            """,
            (equipo_id,),
        ).fetchall()

        # Specs cargadas con metadata completa
        spec_rows = conn.execute(
            """
            SELECT
                es.spec_def_id, es.value,
                sd.spec_key, sd.label, sd.tipo, sd.unidad,
                sd.enum_options, sd.es_compatibilidad,
                COALESCE(sd.compatibilidad_modo, 'exacta') AS compatibilidad_modo,
                (SELECT rol_compatibilidad FROM categoria_spec_templates t
                  JOIN equipo_categorias ec2 ON ec2.categoria_id = t.categoria_id
                  WHERE ec2.equipo_id = ? AND t.spec_def_id = sd.id
                  LIMIT 1) AS rol_compatibilidad
            FROM equipo_specs es
            JOIN spec_definitions sd ON sd.id = es.spec_def_id
            WHERE es.equipo_id = ?
            ORDER BY sd.label
            """,
            (equipo_id, equipo_id),
        ).fetchall()

        # Ficha del equipo. Tabla canónica: `equipo_fichas` (definida en
        # database.py:397). Antes acá apuntaba a `fichas_tecnicas` (que
        # nunca existió) y leía `raw_json` (dropeado en Fase E por la
        # migración d7e9b3c5a8f2) → 500. Ver #504.
        ficha = conn.execute(
            """
            SELECT descripcion, notas
            FROM equipo_fichas
            WHERE equipo_id = ?
            """,
            (equipo_id,),
        ).fetchone()

        # Compat manuales existentes (para que el skill no las contradiga)
        manuales = conn.execute(
            """
            SELECT
                ec.id, ec.equipo_a_id, ec.equipo_b_id, ec.tipo, ec.nota,
                ec.adaptador_id,
                CASE WHEN ec.equipo_a_id = ? THEN ec.equipo_b_id ELSE ec.equipo_a_id END AS otro_id,
                eb.nombre AS otro_nombre
            FROM equipo_compatibilidad ec
            LEFT JOIN equipos eb ON eb.id = CASE
                WHEN ec.equipo_a_id = ? THEN ec.equipo_b_id ELSE ec.equipo_a_id END
            WHERE (ec.equipo_a_id = ? OR ec.equipo_b_id = ?)
              AND ec.auto_generado = FALSE
            """,
            (equipo_id, equipo_id, equipo_id, equipo_id),
        ).fetchall()

        return {
            "equipo": {
                "id": eq["id"],
                "nombre": eq["nombre"],
                "marca": eq["marca"],
                "modelo": eq["modelo"],
                "dueno": eq["dueno"],
            },
            "categorias": [
                {"id": c["id"], "nombre": c["nombre"], "parent_id": c["parent_id"]}
                for c in cat_rows
            ],
            "specs": [
                {
                    "spec_def_id": s["spec_def_id"],
                    "spec_key": s["spec_key"],
                    "label": s["label"],
                    "tipo": s["tipo"],
                    "unidad": s["unidad"],
                    "enum_options": s["enum_options"],
                    "value": s["value"],
                    "es_compatibilidad": s["es_compatibilidad"],
                    "compatibilidad_modo": s["compatibilidad_modo"],
                    "rol_compatibilidad": s["rol_compatibilidad"],
                }
                for s in spec_rows
            ],
            "ficha": {
                "descripcion": ficha["descripcion"] if ficha else None,
                "notas": ficha["notas"] if ficha else None,
            },
            "compat_manuales": [
                {
                    "id": m["id"],
                    "otro_id": m["otro_id"],
                    "otro_nombre": m["otro_nombre"],
                    "tipo": m["tipo"],
                    "nota": m["nota"],
                    "adaptador_id": m["adaptador_id"],
                }
                for m in manuales
            ],
        }
    finally:
        conn.close()

