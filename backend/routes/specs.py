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

class SpecTemplateInput(BaseModel):
    spec_key: str
    label: str
    tipo: str   # "string" | "number" | "enum" | "bool"
    unidad: Optional[str] = None
    enum_options: Optional[list[str]] = None
    prioridad: int = 100
    visible_en_card: bool = False
    visible_en_filtros: bool = False
    visible_en_nombre: bool = False
    obligatorio: bool = False
    ayuda: Optional[str] = None


class SpecTemplateUpdate(BaseModel):
    label: Optional[str] = None
    tipo: Optional[str] = None
    unidad: Optional[str] = None
    enum_options: Optional[list[str]] = None
    prioridad: Optional[int] = None
    visible_en_card: Optional[bool] = None
    visible_en_filtros: Optional[bool] = None
    visible_en_nombre: Optional[bool] = None
    obligatorio: Optional[bool] = None
    ayuda: Optional[str] = None


class EquipoSpecsInput(BaseModel):
    """Diccionario `{spec_key: value}`. Reemplaza TODAS las specs del equipo."""
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


# ── CRUD: Spec templates por categoría ─────────────────────────────────

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
    _require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT id, categoria_id, spec_key, label, tipo, unidad,
                   enum_options, prioridad, visible_en_card,
                   visible_en_filtros, visible_en_nombre, obligatorio, ayuda
            FROM categoria_spec_templates
            WHERE categoria_id = ?
            ORDER BY prioridad, label
            """,
            (categoria_id,),
        ).fetchall()
        return {"items": [row_to_dict(r) for r in rows]}
    finally:
        conn.close()


@router.post("/admin/categorias/{categoria_id}/spec-templates", status_code=201)
def crear_template(categoria_id: int, payload: SpecTemplateInput, request: Request):
    _require_admin(request)
    conn = get_db()
    try:
        # Verificar que la categoría existe
        cat = conn.execute(
            "SELECT id FROM categorias WHERE id = ?", (categoria_id,)
        ).fetchone()
        if not cat:
            raise HTTPException(404, f"Categoría {categoria_id} no existe")
        try:
            cur = conn.execute(
                """
                INSERT INTO categoria_spec_templates
                  (categoria_id, spec_key, label, tipo, unidad, enum_options,
                   prioridad, visible_en_card, visible_en_filtros,
                   visible_en_nombre, obligatorio, ayuda)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    categoria_id,
                    payload.spec_key,
                    payload.label,
                    payload.tipo,
                    payload.unidad,
                    json.dumps(payload.enum_options) if payload.enum_options else None,
                    payload.prioridad,
                    payload.visible_en_card,
                    payload.visible_en_filtros,
                    payload.visible_en_nombre,
                    payload.obligatorio,
                    payload.ayuda,
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
                    f"La spec '{payload.spec_key}' ya existe para esta categoría",
                )
            raise
    finally:
        conn.close()


@router.patch("/admin/spec-templates/{template_id}")
def actualizar_template(template_id: int, payload: SpecTemplateUpdate, request: Request):
    _require_admin(request)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Nada para actualizar")
    # enum_options viene como list, hay que serializarlo a JSON
    if "enum_options" in updates:
        updates["enum_options"] = (
            json.dumps(updates["enum_options"]) if updates["enum_options"] else None
        )
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM categoria_spec_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Template no existe")
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
def borrar_template(template_id: int, request: Request):
    _require_admin(request)
    conn = get_db()
    try:
        cur = conn.execute(
            "DELETE FROM categoria_spec_templates WHERE id = ?", (template_id,)
        )
        conn.commit()
        # NOTA: equipo_specs NO se borra automáticamente al borrar el template,
        # quedan como "extras" sin schema. Es intencional para no perder data.
    finally:
        conn.close()


# ── Specs por equipo ────────────────────────────────────────────────────

@router.get("/admin/equipos/{equipo_id}/specs")
def obtener_specs_equipo(equipo_id: int, request: Request):
    """Devuelve las specs estructuradas del equipo + el template aplicable
    (si tiene categoría asignada). Útil para que el form sepa qué inputs
    renderear y con qué valores actuales."""
    _require_admin(request)
    conn = get_db()
    try:
        # Verificar equipo
        eq = conn.execute(
            "SELECT id FROM equipos WHERE id = ?", (equipo_id,)
        ).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no existe")

        # Specs ya cargadas
        spec_rows = conn.execute(
            "SELECT spec_key, value FROM equipo_specs WHERE equipo_id = ?",
            (equipo_id,),
        ).fetchall()
        specs = {r["spec_key"]: r["value"] for r in spec_rows}

        # Template aplicable: las categorías del equipo (cualquier nivel) +
        # sus templates. Mergeados con dedup por spec_key (la primera gana).
        template_rows = conn.execute(
            """
            SELECT DISTINCT ON (t.spec_key)
                t.spec_key, t.label, t.tipo, t.unidad,
                t.enum_options, t.prioridad,
                t.visible_en_card, t.visible_en_filtros, t.visible_en_nombre,
                t.obligatorio, t.ayuda,
                c.nombre AS categoria_nombre
            FROM equipo_categorias ec
            JOIN categoria_spec_templates t ON t.categoria_id = ec.categoria_id
            JOIN categorias c ON c.id = ec.categoria_id
            WHERE ec.equipo_id = ?
            ORDER BY t.spec_key, t.prioridad
            """,
            (equipo_id,),
        ).fetchall()
        template = [row_to_dict(r) for r in template_rows]
        # Ordenar por prioridad (DISTINCT ON rompió el ORDER lógico)
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
    """Reemplaza TODAS las specs del equipo por las del payload. Las que
    no estén en el payload se borran."""
    _require_admin(request)
    conn = get_db()
    try:
        eq = conn.execute(
            "SELECT id FROM equipos WHERE id = ?", (equipo_id,)
        ).fetchone()
        if not eq:
            raise HTTPException(404, "Equipo no existe")

        # Borrar las viejas y meter las nuevas en una transacción.
        conn.execute("DELETE FROM equipo_specs WHERE equipo_id = ?", (equipo_id,))
        for key, value in payload.specs.items():
            if value is None or value == "":
                continue
            conn.execute(
                """
                INSERT INTO equipo_specs (equipo_id, spec_key, value)
                VALUES (?, ?, ?)
                ON CONFLICT (equipo_id, spec_key) DO UPDATE
                    SET value = EXCLUDED.value
                """,
                (equipo_id, key, str(value)),
            )

        # Recalcular nombre público (ahora que las specs cambiaron, puede
        # cambiar el nombre auto-generado).
        try:
            actualizar_nombres_de(conn, equipo_id, commit=False)
        except Exception:
            # Si el recálculo falla, no abortamos el guardado de specs.
            pass

        conn.commit()
        return {"ok": True, "equipo_id": equipo_id, "specs_count": len(payload.specs)}
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
                CASE WHEN ec.equipo_a_id = ? THEN ec.equipo_b_id ELSE ec.equipo_a_id END AS otro_id,
                eb.nombre AS otro_nombre, eb.foto_url AS otro_foto,
                ea.nombre AS adaptador_nombre
            FROM equipo_compatibilidad ec
            LEFT JOIN equipos eb ON eb.id = CASE
                WHEN ec.equipo_a_id = ? THEN ec.equipo_b_id ELSE ec.equipo_a_id END
            LEFT JOIN equipos ea ON ea.id = ec.adaptador_id
            WHERE ec.equipo_a_id = ? OR ec.equipo_b_id = ?
            ORDER BY ec.tipo, eb.nombre
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


@router.post("/admin/equipos/migrar-specs-json")
def migrar_specs_json(payload: dict, request: Request):
    """Migra specs_json (formato legacy) a equipo_specs (formato estructurado).

    Body:
      - dry_run: bool — si True, devuelve preview sin escribir.

    Después de migrar, hay que correr regenerar-nombres para que los
    nombres públicos reflejen los specs nuevos."""
    _require_admin(request)
    dry_run = bool(payload.get("dry_run"))
    conn = get_db()
    try:
        result = migrar_specs_todos(conn, dry_run=dry_run)
        # Si no es dry_run, regenerar nombres masivamente para que reflejen
        # los specs recién migrados.
        if not dry_run:
            try:
                nombres = regenerar_nombres_todos(conn, dry_run=False)
                result["nombres_actualizados"] = len(nombres["cambios"])
            except Exception as e:
                result["nombres_error"] = str(e)
        return result
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
