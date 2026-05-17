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
from services.clasificador_heuristico import clasificar_lote
from services.migracion_specs import migrar_specs_todos
from services.nombre_service import (
    actualizar_nombres_de,
    calcular_nombres_para,
    regenerar_nombres_todos,
)
from services.ranking_service import recalcular_ranking_todos


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
              COALESCE(sd.es_compatibilidad, FALSE) AS es_compatibilidad,
              COALESCE(sd.compatibilidad_modo, 'exacta') AS compatibilidad_modo,
              COALESCE(sd.validado, FALSE) AS validado,
              (SELECT COUNT(*) FROM categoria_spec_templates t WHERE t.spec_def_id = sd.id) AS uso_categorias,
              (SELECT COUNT(*) FROM equipo_specs es WHERE es.spec_def_id = sd.id) AS uso_equipos,
              COALESCE(
                (SELECT json_agg(
                          json_build_object(
                            'id', c.id,
                            'nombre', c.nombre,
                            'template_id', t.id
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
    """Verifica shape de `output_config`. Solo soporta `row_strategy` por ahora,
    y solo aplica a specs tipo tabla."""
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


# ── CRUD familias jerárquicas (multi_enum) ─────────────────────────────


class SpecFamiliaItemInput(BaseModel):
    familia: str
    valor: str
    posicion: int
    spec_def_id: Optional[int] = None


class SpecFamiliaItemUpdate(BaseModel):
    familia: Optional[str] = None
    valor: Optional[str] = None
    posicion: Optional[int] = None
    spec_def_id: Optional[int] = None


@router.get("/admin/spec-familias")
def listar_familias(request: Request):
    """Lista todas las entries de spec_familia_jerarquia agrupadas por
    familia. Devuelve `[{familia, items: [{id, valor, posicion, spec_def_id}]}]`
    ordenadas por familia y posicion."""
    _require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, familia, valor, posicion, spec_def_id "
            "FROM spec_familia_jerarquia "
            "ORDER BY familia, posicion, valor"
        ).fetchall()
        grupos: dict[str, list[dict]] = {}
        for r in rows:
            d = row_to_dict(r) if not isinstance(r, dict) else r
            grupos.setdefault(d["familia"], []).append({
                "id": d["id"],
                "valor": d["valor"],
                "posicion": d["posicion"],
                "spec_def_id": d.get("spec_def_id"),
            })
        return {
            "items": [
                {"familia": fam, "items": items}
                for fam, items in sorted(grupos.items())
            ],
        }
    finally:
        conn.close()


@router.post("/admin/spec-familias", status_code=201)
def crear_familia_item(payload: SpecFamiliaItemInput, request: Request):
    """Crea una entry nueva en la familia (ej. agregar HDMI 2.1b)."""
    _require_admin(request)
    familia = (payload.familia or "").strip().lower()
    valor = (payload.valor or "").strip()
    if not familia or not valor:
        raise HTTPException(400, "familia y valor son obligatorios.")
    conn = get_db()
    try:
        try:
            cur = conn.execute(
                """
                INSERT INTO spec_familia_jerarquia
                  (familia, valor, posicion, spec_def_id)
                VALUES (?, ?, ?, ?)
                RETURNING id
                """,
                (familia, valor, payload.posicion, payload.spec_def_id),
            )
            new_id = cur.fetchone()[0]
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise HTTPException(
                    409, f"Ya existe valor '{valor}' en familia '{familia}'."
                )
            raise
    finally:
        conn.close()
    _MULTI_ENUM_FAMILIES.invalidate()
    return {"id": new_id, "familia": familia, "valor": valor, "posicion": payload.posicion}


@router.patch("/admin/spec-familias/{item_id}")
def actualizar_familia_item(item_id: int, payload: SpecFamiliaItemUpdate, request: Request):
    """Modifica un item (reordenar via posicion, renombrar valor, mover de familia)."""
    _require_admin(request)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Nada para actualizar.")
    if "familia" in updates:
        updates["familia"] = (updates["familia"] or "").strip().lower()
    if "valor" in updates:
        updates["valor"] = (updates["valor"] or "").strip()
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM spec_familia_jerarquia WHERE id = ?", (item_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Item no existe.")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        try:
            conn.execute(
                f"UPDATE spec_familia_jerarquia SET {set_clause}, "
                f"updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                list(updates.values()) + [item_id],
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise HTTPException(
                    409, "Conflicto: el (familia, valor) resultante ya existe."
                )
            raise
    finally:
        conn.close()
    _MULTI_ENUM_FAMILIES.invalidate()
    return {"ok": True, "id": item_id, **updates}


@router.delete("/admin/spec-familias/{item_id}", status_code=204)
def borrar_familia_item(item_id: int, request: Request):
    """Borra un item. La compat de equipos que usen ese valor en sus
    specs sigue funcionando vía match exacto — solo deja de aplicar la
    jerarquía intra-familia para ese valor."""
    _require_admin(request)
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM spec_familia_jerarquia WHERE id = ?", (item_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Item no existe.")
        conn.execute("DELETE FROM spec_familia_jerarquia WHERE id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()
    _MULTI_ENUM_FAMILIES.invalidate()


# ── Cleanup de specs legacy (equipo_fichas.specs_json) ─────────────────


@router.get("/admin/specs/legacy/inventario")
def listar_legacy_inventario(request: Request):
    """Lista los equipos que tienen `equipo_fichas.specs_json` con specs
    cargadas, junto con cuántas matchean fuzzy una `spec_definitions` y
    cuántas son genuinamente custom (sin equivalente).

    Devuelve `[{equipo_id, equipo_nombre, total, matched, custom}]`
    ordenado por total descendente. El admin después usa
    `POST /admin/specs/legacy/promover/{equipo_id}` para mover las
    matched a `equipo_specs`."""
    _require_admin(request)
    conn = get_db()
    try:
        # Index de spec_definitions por label normalizado.
        from services.spec_render import norm_spec_label
        def_rows = conn.execute(
            "SELECT id, label FROM spec_definitions"
        ).fetchall()
        defs_by_norm: dict[str, int] = {}
        for r in def_rows:
            d = row_to_dict(r) if not isinstance(r, dict) else r
            n = norm_spec_label(d.get("label") or "")
            if n:
                defs_by_norm[n] = d["id"]

        eq_rows = conn.execute(
            """
            SELECT e.id, e.nombre, ef.specs_json
            FROM equipos e
            JOIN equipo_fichas ef ON ef.equipo_id = e.id
            WHERE e.eliminado_at IS NULL
              AND ef.specs_json IS NOT NULL
              AND TRIM(ef.specs_json) <> ''
            """
        ).fetchall()

        items: list[dict] = []
        for r in eq_rows:
            d = row_to_dict(r) if not isinstance(r, dict) else r
            try:
                arr = json.loads(d["specs_json"])
            except Exception:
                continue
            if not isinstance(arr, list):
                continue
            matched = 0
            custom = 0
            total = 0
            for s in arr:
                if not isinstance(s, dict):
                    continue
                label = s.get("label") or ""
                value = s.get("value")
                if not label or value is None or value == "":
                    continue
                total += 1
                if defs_by_norm.get(norm_spec_label(label)):
                    matched += 1
                else:
                    custom += 1
            if total > 0:
                items.append({
                    "equipo_id": d["id"],
                    "equipo_nombre": d["nombre"],
                    "total": total,
                    "matched": matched,
                    "custom": custom,
                })
        items.sort(key=lambda x: -x["total"])
        return {"total": len(items), "items": items}
    finally:
        conn.close()


@router.post("/admin/specs/legacy/promover/{equipo_id}")
def promover_legacy_equipo(equipo_id: int, request: Request):
    """Para cada spec del `specs_json` legacy del equipo cuyo label
    matchee un `spec_definitions`:
      1. Crea o actualiza `equipo_specs` (PK equipo_id, spec_def_id).
      2. Saca esa entry del `specs_json`.

    Las specs custom (sin matching) quedan en el JSON intactas — el
    admin decide manualmente si crear la spec global o borrarlas. Esto
    NO toca specs tabla (las marca como `value_raw` y tienen flujo
    propio)."""
    _require_admin(request)
    conn = get_db()
    try:
        from services.spec_render import norm_spec_label
        def_rows = conn.execute(
            "SELECT id, label, tipo FROM spec_definitions"
        ).fetchall()
        defs_by_norm: dict[str, dict] = {}
        for r in def_rows:
            d = row_to_dict(r) if not isinstance(r, dict) else r
            n = norm_spec_label(d.get("label") or "")
            if n:
                defs_by_norm[n] = {"id": d["id"], "tipo": d["tipo"]}

        ficha = conn.execute(
            "SELECT specs_json FROM equipo_fichas WHERE equipo_id = ?",
            (equipo_id,),
        ).fetchone()
        if not ficha or not ficha["specs_json"]:
            raise HTTPException(404, "Equipo sin specs_json.")

        try:
            arr = json.loads(ficha["specs_json"])
        except Exception:
            raise HTTPException(400, "specs_json corrupto.")
        if not isinstance(arr, list):
            raise HTTPException(400, "specs_json no es array.")

        kept: list[dict] = []
        promoted: list[dict] = []
        for s in arr:
            if not isinstance(s, dict):
                kept.append(s)
                continue
            label = s.get("label") or ""
            value = s.get("value")
            if not label or value is None or value == "":
                kept.append(s)
                continue
            match = defs_by_norm.get(norm_spec_label(label))
            if not match:
                kept.append(s)
                continue
            # Skip specs tabla — su shape no es el del legacy plain.
            if match["tipo"] == "tabla":
                kept.append(s)
                continue
            # Migrar.
            conn.execute(
                """
                INSERT INTO equipo_specs (equipo_id, spec_def_id, value)
                VALUES (?, ?, ?)
                ON CONFLICT (equipo_id, spec_def_id) DO UPDATE
                  SET value = EXCLUDED.value
                """,
                (equipo_id, match["id"], str(value)),
            )
            promoted.append({"label": label, "spec_def_id": match["id"]})

        # Actualizar specs_json sin las que migramos.
        new_json = json.dumps(kept, ensure_ascii=False) if kept else None
        conn.execute(
            "UPDATE equipo_fichas SET specs_json = ? WHERE equipo_id = ?",
            (new_json, equipo_id),
        )
        conn.commit()
        return {
            "ok": True,
            "equipo_id": equipo_id,
            "promoted_count": len(promoted),
            "kept_count": len(kept),
            "promoted": promoted,
        }
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
    """Lista asignaciones de la categoría, JOIN con spec_definitions para
    devolver los campos planos (label, tipo, unidad, enum_options) que el
    frontend usa para renderear inputs."""
    _require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT
              t.id, t.categoria_id, t.spec_def_id,
              sd.spec_key, sd.label, sd.tipo, sd.unidad, sd.unidad_id, sd.enum_options,
              sd.tabla_columnas, sd.output_config,
              t.prioridad,
              COALESCE(t.visible_en_card, FALSE) AS visible_en_card,
              COALESCE(t.visible_en_filtros, FALSE) AS visible_en_filtros,
              COALESCE(t.visible_en_nombre, FALSE) AS visible_en_nombre,
              COALESCE(t.obligatorio, FALSE) AS obligatorio,
              COALESCE(t.ayuda, sd.ayuda) AS ayuda,
              COALESCE(t.destacado, FALSE) AS destacado,
              COALESCE(sd.es_compatibilidad, FALSE) AS es_compatibilidad,
              COALESCE(sd.compatibilidad_modo, 'exacta') AS compatibilidad_modo,
              t.rol_compatibilidad
            FROM categoria_spec_templates t
            JOIN spec_definitions sd ON sd.id = t.spec_def_id
            WHERE t.categoria_id = ?
            ORDER BY t.prioridad, sd.label
            """,
            (categoria_id,),
        ).fetchall()
        return {"items": [row_to_dict(r) for r in rows]}
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
    """Actualiza los flags de una asignación (prioridad, destacado, visible_*,
    obligatorio, ayuda). Para cambiar tipo/unidad/options usar PATCH
    /admin/spec-definitions/{id} (afecta a todas las categorías)."""
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
    """Actualiza la prioridad de múltiples templates en un solo request.
    Body: {"items": [{"id": 1, "prioridad": 10}, {"id": 2, "prioridad": 20}, …]}.
    Menor prioridad = aparece antes (el listado y el form ordenan ASC).
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

        # Template aplicable: las categorías del equipo + sus asignaciones.
        # Mergeados con dedup por spec_def_id (la primera asignación gana en
        # caso de conflicto entre categorías).
        template_rows = conn.execute(
            """
            SELECT DISTINCT ON (t.spec_def_id)
                t.id AS template_id,
                t.spec_def_id,
                sd.spec_key, sd.label, sd.tipo, sd.unidad, sd.unidad_id, sd.enum_options,
                sd.tabla_columnas, sd.output_config,
                t.prioridad,
                t.visible_en_card, t.visible_en_filtros, t.visible_en_nombre,
                t.obligatorio,
                COALESCE(t.ayuda, sd.ayuda) AS ayuda,
                COALESCE(t.destacado, FALSE) AS destacado,
                c.nombre AS categoria_nombre
            FROM equipo_categorias ec
            JOIN categoria_spec_templates t ON t.categoria_id = ec.categoria_id
            JOIN spec_definitions sd ON sd.id = t.spec_def_id
            JOIN categorias c ON c.id = ec.categoria_id
            WHERE ec.equipo_id = ?
            ORDER BY t.spec_def_id, t.prioridad
            """,
            (equipo_id,),
        ).fetchall()
        template = [row_to_dict(r) for r in template_rows]
        template.sort(key=lambda t: (t["prioridad"], t["label"]))

        return {
            "equipo_id": equipo_id,
            "specs": specs,
            "template": template,
        }
    finally:
        conn.close()


def _validate_multi_enum_value(value: str, enum_options: list[str], spec_label: str) -> str:
    """Normaliza `value` a JSON array y valida que cada item esté en
    `enum_options`. Acepta dos shapes de entrada (CSV legacy o JSON array)
    pero siempre devuelve JSON array compactado.

    El endpoint PUT usa esto para enforce el storage canónico definido en
    la migration `f3a5c7d9e1b6_multi_enum_json_canonical.py`."""
    v = (value or "").strip()
    if not v:
        return "[]"
    items: list[str]
    if v.startswith("["):
        try:
            parsed = json.loads(v)
        except Exception:
            raise HTTPException(
                400, f"Spec '{spec_label}' tipo multi_enum: JSON inválido."
            )
        if not isinstance(parsed, list):
            raise HTTPException(
                400, f"Spec '{spec_label}': multi_enum debe ser array."
            )
        items = [str(x).strip() for x in parsed if str(x).strip()]
    else:
        items = [p.strip() for p in v.split(",") if p.strip()]
    # Validar contra enum_options si están declaradas. Si la spec no tiene
    # enum_options (caso raro), aceptamos cualquier valor pero canonizado.
    if enum_options:
        opts_set = set(enum_options)
        invalid = [x for x in items if x not in opts_set]
        if invalid:
            raise HTTPException(
                400,
                f"Spec '{spec_label}' multi_enum: valores no permitidos {invalid}. "
                f"Opciones: {enum_options}.",
            )
    # Dedup preservando orden de aparición.
    seen: set[str] = set()
    deduped: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            deduped.append(x)
    return json.dumps(deduped, ensure_ascii=False)


def _validate_tabla_value(value: str, columnas: list[dict], spec_label: str) -> str:
    """Valida que `value` sea JSON array donde cada row tiene las keys de
    `columnas` con los tipos correctos. Devuelve el JSON re-serializado
    (compactado) para garantizar storage normalizado."""
    try:
        data = json.loads(value)
    except Exception:
        raise HTTPException(400, f"Spec '{spec_label}' tipo tabla: value debe ser JSON válido.")
    if not isinstance(data, list):
        raise HTTPException(400, f"Spec '{spec_label}': tabla debe ser un array de filas.")
    cleaned: list[dict] = []
    col_by_key = {c["key"]: c for c in columnas}
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            raise HTTPException(400, f"Spec '{spec_label}' fila {i}: debe ser objeto.")
        clean_row: dict = {}
        for key, col in col_by_key.items():
            v = row.get(key)
            if v is None or v == "":
                continue  # campo vacío permitido en cualquier columna
            ctipo = col["tipo"]
            if ctipo == "number":
                try:
                    clean_row[key] = float(v) if "." in str(v) else int(v)
                except (TypeError, ValueError):
                    raise HTTPException(
                        400,
                        f"Spec '{spec_label}' fila {i} columna '{key}': debe ser número, vino {v!r}.",
                    )
            elif ctipo == "valor_unidad":
                # Objeto {valor, unidad}. Permite que la unidad varíe por fila.
                if not isinstance(v, dict):
                    raise HTTPException(
                        400,
                        f"Spec '{spec_label}' fila {i} columna '{key}': debe ser objeto {{valor, unidad}}.",
                    )
                valor_raw = v.get("valor")
                unidad_raw = v.get("unidad", "")
                has_valor = valor_raw not in (None, "")
                has_unidad = bool(str(unidad_raw or "").strip())
                if not has_valor and not has_unidad:
                    continue
                cell: dict = {}
                if has_valor:
                    try:
                        cell["valor"] = float(valor_raw) if "." in str(valor_raw) else int(valor_raw)
                    except (TypeError, ValueError):
                        cell["valor"] = str(valor_raw).strip()
                if has_unidad:
                    cell["unidad"] = str(unidad_raw).strip()
                clean_row[key] = cell
            elif ctipo == "bool":
                clean_row[key] = bool(v) if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes", "sí", "si")
            elif ctipo == "enum":
                if str(v) not in (col.get("options") or []):
                    raise HTTPException(
                        400,
                        f"Spec '{spec_label}' fila {i} columna '{key}': '{v}' no está en opciones {col.get('options')}.",
                    )
                clean_row[key] = str(v)
            else:  # string
                clean_row[key] = str(v).strip()
        if clean_row:  # solo persistir filas con al menos un valor
            cleaned.append(clean_row)
    return json.dumps(cleaned, ensure_ascii=False)


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

        # Pre-cargar las defs referenciadas (tipo + tabla_columnas) para
        # validar el value de specs tipo 'tabla' antes de persistir.
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
                f"SELECT id, label, tipo, tabla_columnas, enum_options "
                f"FROM spec_definitions WHERE id IN ({placeholders})",
                tuple(keys_int),
            ).fetchall()
            defs_by_id = {r["id"]: row_to_dict(r) for r in def_rows}

        conn.execute("DELETE FROM equipo_specs WHERE equipo_id = ?", (equipo_id,))
        for key, value in payload.specs.items():
            if value is None or value == "":
                continue
            spec_def_id = int(key)
            sd = defs_by_id.get(spec_def_id)
            persist_value = str(value)
            if sd and sd.get("tipo") == "tabla":
                cols = sd.get("tabla_columnas")
                if isinstance(cols, str):
                    cols = json.loads(cols)
                if not cols:
                    raise HTTPException(
                        500,
                        f"Spec '{sd.get('label')}' tipo tabla sin tabla_columnas definidas.",
                    )
                persist_value = _validate_tabla_value(persist_value, cols, sd.get("label") or "")
                if persist_value == "[]":
                    continue  # tabla totalmente vacía → no persistir nada
            elif sd and sd.get("tipo") == "multi_enum":
                opts = sd.get("enum_options")
                if isinstance(opts, str):
                    try:
                        opts = json.loads(opts)
                    except Exception:
                        opts = []
                persist_value = _validate_multi_enum_value(
                    persist_value, opts or [], sd.get("label") or "",
                )
                if persist_value == "[]":
                    continue  # multi_enum vacío → no persistir
            conn.execute(
                """
                INSERT INTO equipo_specs (equipo_id, spec_def_id, value)
                VALUES (?, ?, ?)
                ON CONFLICT (equipo_id, spec_def_id) DO UPDATE
                    SET value = EXCLUDED.value
                """,
                (equipo_id, spec_def_id, persist_value),
            )

        try:
            actualizar_nombres_de(conn, equipo_id, commit=False)
        except Exception:
            pass

        conn.commit()
        return {"ok": True, "equipo_id": equipo_id, "specs_count": len(payload.specs)}
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
        where = []
        params: list = []
        if equipo_ids:
            placeholders = ",".join(["?"] * len(equipo_ids))
            where.append(f"e.id IN ({placeholders})")
            params.extend(int(i) for i in equipo_ids)
        elif solo_sin:
            where.append(
                "NOT EXISTS (SELECT 1 FROM equipo_categorias ec WHERE ec.equipo_id = e.id)"
            )

        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute(
            f"SELECT e.id, e.nombre, e.marca, e.modelo, e.foto_url "
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
            "WHERE NOT EXISTS (SELECT 1 FROM equipo_categorias ec WHERE ec.equipo_id = e.id)"
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
            SELECT e.id, e.nombre, e.marca, e.foto_url
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


@router.post("/admin/equipos/migrar-specs-json", deprecated=True)
def migrar_specs_json(payload: dict, request: Request):
    """DEPRECATED post unificar_specs_definitions: el migrador legacy
    asumía el schema (categoria_id, spec_key) que ya no existe. Si necesitás
    re-importar specs_json viejos, hay que reescribir el service para que
    cree spec_definitions sobre la marcha. Para el dueño esto es no-op
    porque los specs_json viejos ya fueron migrados antes del refactor."""
    _require_admin(request)
    raise HTTPException(
        410,
        "Endpoint obsoleto. El refactor unificar_specs_definitions cambió "
        "el schema. Si necesitás migrar specs_json legacy, reescribí el "
        "service migracion_specs.py para que use spec_def_id.",
    )


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
    where = ""
    if filtro == "pendientes":
        where = "WHERE COALESCE(nombre_publico_revisado, FALSE) = FALSE"
    elif filtro == "aprobados":
        where = "WHERE nombre_publico_revisado = TRUE AND nombre_publico_override IS NULL"
    elif filtro == "editados":
        where = "WHERE nombre_publico_revisado = TRUE AND nombre_publico_override IS NOT NULL"

    conn = get_db()
    try:
        rows = conn.execute(
            f"""
            SELECT id, nombre, marca, modelo, foto_url,
                   nombre_publico, nombre_publico_largo,
                   nombre_publico_override,
                   COALESCE(nombre_publico_revisado, FALSE) AS revisado
            FROM equipos
            {where}
            ORDER BY LOWER(COALESCE(nombre_publico, nombre))
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
                e.id, e.nombre, e.marca, e.modelo,
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
            """
            SELECT id, nombre, marca, modelo, dueno
            FROM equipos
            WHERE id = ? AND eliminado_at IS NULL
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

        # Ficha (descripcion + raw_json del autocompletar)
        ficha = conn.execute(
            """
            SELECT descripcion, raw_json
            FROM fichas_tecnicas
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
                "raw_json": ficha["raw_json"] if ficha else None,
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


# ── Propuestas de specs (resolver/normalizer) ──────────────────────────

@router.post("/admin/specs/proponer")
def proponer_specs(payload: PropuestasBulkInput, request: Request):
    """El skill envía sus propuestas (enum_option / spec_nueva / merge_specs).
    NO se aplican — quedan en spec_propuestas_pendientes para que el dueño
    apruebe o descarte desde la UI."""
    _require_admin(request)
    if not payload.items:
        return {"ok": True, "creadas": 0}

    valid_tipos = {"enum_option", "spec_nueva", "merge_specs"}
    for p in payload.items:
        if p.tipo not in valid_tipos:
            raise HTTPException(400, f"tipo de propuesta inválido: {p.tipo}")
        if p.confianza is not None and not (0.0 <= p.confianza <= 1.0):
            raise HTTPException(400, "confianza debe estar entre 0 y 1")

    conn = get_db()
    try:
        creadas = 0
        for p in payload.items:
            conn.execute(
                """
                INSERT INTO spec_propuestas_pendientes
                  (tipo, payload, origen, confianza)
                VALUES (?, ?::jsonb, ?, ?)
                """,
                (p.tipo, json.dumps(p.payload), p.origen, p.confianza),
            )
            creadas += 1
        conn.commit()
        return {"ok": True, "creadas": creadas}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.get("/admin/specs/propuestas")
def listar_propuestas(request: Request, estado: str = "pendientes"):
    """Lista propuestas. estado: pendientes (default) | aplicadas | descartadas | todas."""
    _require_admin(request)
    conn = get_db()
    try:
        where_clause = ""
        if estado == "pendientes":
            where_clause = "WHERE aplicado_at IS NULL AND descartado_at IS NULL"
        elif estado == "aplicadas":
            where_clause = "WHERE aplicado_at IS NOT NULL"
        elif estado == "descartadas":
            where_clause = "WHERE descartado_at IS NOT NULL"
        elif estado != "todas":
            raise HTTPException(400, "estado debe ser pendientes|aplicadas|descartadas|todas")

        rows = conn.execute(
            f"""
            SELECT id, tipo, payload, origen, confianza, created_at,
                   aplicado_at, descartado_at
            FROM spec_propuestas_pendientes
            {where_clause}
            ORDER BY created_at DESC
            LIMIT 200
            """
        ).fetchall()
        return {
            "items": [
                {
                    "id": r["id"],
                    "tipo": r["tipo"],
                    "payload": r["payload"],
                    "origen": r["origen"],
                    "confianza": r["confianza"],
                    "created_at": str(r["created_at"]),
                    "aplicado_at": str(r["aplicado_at"]) if r["aplicado_at"] else None,
                    "descartado_at": str(r["descartado_at"]) if r["descartado_at"] else None,
                }
                for r in rows
            ],
        }
    finally:
        conn.close()


@router.post("/admin/specs/propuestas/{propuesta_id}/aplicar")
def aplicar_propuesta(propuesta_id: int, request: Request):
    """Aplica una propuesta: ejecuta la acción correspondiente según el tipo
    y marca aplicado_at."""
    _require_admin(request)
    conn = get_db()
    try:
        p = conn.execute(
            """
            SELECT id, tipo, payload, aplicado_at, descartado_at
            FROM spec_propuestas_pendientes
            WHERE id = ?
            """,
            (propuesta_id,),
        ).fetchone()
        if not p:
            raise HTTPException(404, "Propuesta no existe")
        if p["aplicado_at"]:
            raise HTTPException(409, "Propuesta ya fue aplicada")
        if p["descartado_at"]:
            raise HTTPException(409, "Propuesta ya fue descartada")

        tipo = p["tipo"]
        # payload viene de JSONB → ya es dict
        data = p["payload"] if isinstance(p["payload"], dict) else json.loads(p["payload"])

        if tipo == "enum_option":
            spec_def_id = data.get("spec_def_id")
            new_options = data.get("options") or []
            if not spec_def_id or not new_options:
                raise HTTPException(400, "Payload enum_option inválido")
            sd = conn.execute(
                "SELECT enum_options FROM spec_definitions WHERE id = ?",
                (spec_def_id,),
            ).fetchone()
            if not sd:
                raise HTTPException(404, "Spec definition no existe")
            existing = sd["enum_options"] or []
            if isinstance(existing, str):
                existing = json.loads(existing)
            merged = list(existing)
            for opt in new_options:
                if opt not in merged:
                    merged.append(opt)
            conn.execute(
                "UPDATE spec_definitions SET enum_options = ?::jsonb WHERE id = ?",
                (json.dumps(merged), spec_def_id),
            )

        elif tipo == "spec_nueva":
            # Crea una spec_definition nueva con los campos del payload.
            spec_key = data.get("spec_key")
            label = data.get("label")
            tipo_spec = data.get("tipo")
            if not all([spec_key, label, tipo_spec]):
                raise HTTPException(400, "Payload spec_nueva inválido (faltan spec_key/label/tipo)")
            # Defensa: si modo=jerarquia, tipo debe ser enum
            compat_modo = data.get("compatibilidad_modo", "exacta")
            if data.get("es_compatibilidad") and compat_modo == "jerarquia" and tipo_spec != "enum":
                raise HTTPException(400, "Modo jerárquico requiere tipo enum")
            conn.execute(
                """
                INSERT INTO spec_definitions
                  (spec_key, label, tipo, unidad, enum_options, ayuda,
                   es_compatibilidad, compatibilidad_modo)
                VALUES (?, ?, ?, ?, ?::jsonb, ?, ?, ?)
                """,
                (
                    spec_key, label, tipo_spec,
                    data.get("unidad"),
                    json.dumps(data.get("enum_options")) if data.get("enum_options") else None,
                    data.get("ayuda"),
                    bool(data.get("es_compatibilidad", False)),
                    compat_modo,
                ),
            )

        elif tipo == "merge_specs":
            # Consolida specs: para cada spec en merge_spec_def_ids, mueve sus
            # equipo_specs al keep_spec_def_id y borra la spec mergeada.
            keep_id = data.get("keep_spec_def_id")
            merge_ids = data.get("merge_spec_def_ids") or []
            if not keep_id or not merge_ids:
                raise HTTPException(400, "Payload merge_specs inválido")
            keep_exists = conn.execute(
                "SELECT id FROM spec_definitions WHERE id = ?", (keep_id,),
            ).fetchone()
            if not keep_exists:
                raise HTTPException(404, "keep_spec_def_id no existe")
            for mid in merge_ids:
                if mid == keep_id:
                    continue
                # Mover equipo_specs (ON CONFLICT: el keep gana si ya tiene valor)
                conn.execute(
                    """
                    INSERT INTO equipo_specs (equipo_id, spec_def_id, value)
                    SELECT equipo_id, ?, value
                    FROM equipo_specs
                    WHERE spec_def_id = ?
                    ON CONFLICT (equipo_id, spec_def_id) DO NOTHING
                    """,
                    (keep_id, mid),
                )
                # Borrar las viejas
                conn.execute(
                    "DELETE FROM equipo_specs WHERE spec_def_id = ?", (mid,),
                )
                # Mover asignaciones de categoría (ON CONFLICT: keep gana)
                conn.execute(
                    """
                    INSERT INTO categoria_spec_templates
                      (categoria_id, spec_def_id, prioridad, destacado,
                       obligatorio, visible_en_card, visible_en_filtros,
                       visible_en_nombre, ayuda)
                    SELECT categoria_id, ?, prioridad, destacado,
                           obligatorio, visible_en_card, visible_en_filtros,
                           visible_en_nombre, ayuda
                    FROM categoria_spec_templates
                    WHERE spec_def_id = ?
                    ON CONFLICT (categoria_id, spec_def_id) DO NOTHING
                    """,
                    (keep_id, mid),
                )
                conn.execute(
                    "DELETE FROM categoria_spec_templates WHERE spec_def_id = ?",
                    (mid,),
                )
                conn.execute(
                    "DELETE FROM spec_definitions WHERE id = ?", (mid,),
                )

        elif tipo == "assign_spec":
            # Asigna una spec existente a una categoría. Opcionalmente carga
            # el valor sugerido en el equipo origen.
            spec_def_id = data.get("spec_def_id")
            categoria_id = data.get("categoria_id")
            if not spec_def_id or not categoria_id:
                raise HTTPException(400, "Payload assign_spec inválido (faltan spec_def_id o categoria_id)")
            sd = conn.execute("SELECT id FROM spec_definitions WHERE id = ?", (spec_def_id,)).fetchone()
            if not sd:
                raise HTTPException(404, "Spec definition no existe")
            cat = conn.execute("SELECT id FROM categorias WHERE id = ?", (categoria_id,)).fetchone()
            if not cat:
                raise HTTPException(404, "Categoría no existe")
            # Asignación idempotente
            conn.execute(
                """
                INSERT INTO categoria_spec_templates
                    (categoria_id, spec_def_id, prioridad, destacado, obligatorio,
                     visible_en_card, visible_en_filtros, visible_en_nombre, ayuda,
                     rol_compatibilidad)
                VALUES (?, ?, 100, FALSE, FALSE, FALSE, FALSE, FALSE, NULL, NULL)
                ON CONFLICT (categoria_id, spec_def_id) DO NOTHING
                """,
                (categoria_id, spec_def_id),
            )
            # Si la propuesta tiene valor sugerido y un equipo origen, cargar
            # también el valor (es la pieza que detectó el autocompletar).
            valor = data.get("valor_sugerido")
            source_equipo_id = data.get("source_equipo_id")
            if valor and source_equipo_id:
                conn.execute(
                    """
                    INSERT INTO equipo_specs (equipo_id, spec_def_id, value)
                    VALUES (?, ?, ?)
                    ON CONFLICT (equipo_id, spec_def_id) DO UPDATE
                        SET value = EXCLUDED.value
                    """,
                    (source_equipo_id, spec_def_id, str(valor)),
                )

        else:
            raise HTTPException(400, f"tipo desconocido: {tipo}")

        # Marcar como aplicada
        conn.execute(
            "UPDATE spec_propuestas_pendientes SET aplicado_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (propuesta_id,),
        )
        conn.commit()
        return {"ok": True, "id": propuesta_id, "tipo": tipo}
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/admin/specs/propuestas/{propuesta_id}/descartar")
def descartar_propuesta(propuesta_id: int, request: Request):
    """Marca una propuesta como descartada (no se aplica, queda en historial)."""
    _require_admin(request)
    conn = get_db()
    try:
        p = conn.execute(
            "SELECT aplicado_at, descartado_at FROM spec_propuestas_pendientes WHERE id = ?",
            (propuesta_id,),
        ).fetchone()
        if not p:
            raise HTTPException(404, "Propuesta no existe")
        if p["aplicado_at"]:
            raise HTTPException(409, "Propuesta ya fue aplicada")
        if p["descartado_at"]:
            return {"ok": True, "id": propuesta_id}   # idempotente
        conn.execute(
            "UPDATE spec_propuestas_pendientes SET descartado_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (propuesta_id,),
        )
        conn.commit()
        return {"ok": True, "id": propuesta_id}
    finally:
        conn.close()


class PropuestasBulkActionInput(BaseModel):
    """Body del endpoint bulk. `ids` puede tener 1..N propuestas.
    `accion` es 'apply' o 'discard'. `min_confianza` es opcional: si está
    set, solo procesa propuestas con `confianza >= min_confianza` (útil
    para "aplicar todas las que confianza ≥ 80%")."""
    ids: list[int]
    accion: str  # "apply" | "discard"
    min_confianza: Optional[float] = None


@router.post("/admin/specs/propuestas/bulk")
def bulk_propuestas(payload: PropuestasBulkActionInput, request: Request):
    """Aplica o descarta varias propuestas de una vez.

    No es all-or-nothing — cada propuesta se procesa de forma independiente.
    Las que fallan se reportan en `failed` con su error, las que pasan en
    `ok_ids`. Permite resolver "aplicar las 12 que matchean" y dejar las
    que requieren revisión manual.

    Si una propuesta ya fue aplicada/descartada, se cuenta como ok
    (idempotente)."""
    _require_admin(request)
    if not payload.ids:
        return {"ok_count": 0, "ok_ids": [], "failed": []}
    if payload.accion not in ("apply", "discard"):
        raise HTTPException(400, "accion debe ser 'apply' o 'discard'.")

    # Filtrar por confianza si se pidió.
    ids_a_procesar = list(payload.ids)
    if payload.min_confianza is not None:
        conn = get_db()
        try:
            placeholders = ",".join(["?"] * len(payload.ids))
            rows = conn.execute(
                f"""
                SELECT id, confianza FROM spec_propuestas_pendientes
                WHERE id IN ({placeholders})
                """,
                tuple(payload.ids),
            ).fetchall()
            ids_a_procesar = [
                r["id"] for r in rows
                if (r["confianza"] or 0) >= payload.min_confianza
            ]
        finally:
            conn.close()

    ok_ids: list[int] = []
    failed: list[dict] = []
    for pid in ids_a_procesar:
        try:
            if payload.accion == "apply":
                aplicar_propuesta(pid, request)
            else:
                descartar_propuesta(pid, request)
            ok_ids.append(pid)
        except HTTPException as he:
            # Propuesta ya aplicada/descartada = ok (idempotente).
            detail = str(he.detail).lower()
            if "ya fue" in detail or he.status_code == 404:
                ok_ids.append(pid)
            else:
                failed.append({"id": pid, "error": str(he.detail)[:200]})
        except Exception as e:
            failed.append({
                "id": pid,
                "error": f"Error inesperado ({type(e).__name__})",
            })

    return {
        "ok_count": len(ok_ids),
        "ok_ids": ok_ids,
        "failed": failed,
        "skipped_by_confianza": len(payload.ids) - len(ids_a_procesar),
    }
