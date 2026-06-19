"""Catálogo global de spec_definitions (#501 — extraído del god-module
`routes/specs.py`).

CRUD del catálogo de definiciones de specs (listar / crear / actualizar / borrar)
+ sus validadores (output_config, columnas de tabla, unidades) y constantes de
tipos válidos. Registra sus rutas en el router compartido del paquete
`routes.specs`. `_require_admin` (guard) vive en `core`.
"""
import json
from typing import Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel

from database import get_db, row_to_dict
from routes.specs.core import router, _require_admin


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

