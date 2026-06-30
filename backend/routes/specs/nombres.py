"""Nombres públicos, ranking y clasificación de equipos (#501 — extraído del
god-module `routes/specs.py`).

Regenerar nombres públicos (masivo + preview), recalcular ranking, clasificar
equipos en categorías (bulk heurístico + aplicar) y el flujo de aprobación /
validación del nombre público. Registra sus rutas en el router compartido del
paquete `routes.specs`. `_require_admin` (guard) vive en `core`.
"""
from typing import Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel

from database import get_db, row_to_dict, MARCA_SUBQUERY
from services.clasificador_heuristico import clasificar_lote
from services.nombre_service import (
    actualizar_nombres_de,
    calcular_nombres_para,
    regenerar_nombres_todos,
)
from services.ranking_service import recalcular_ranking_todos
from routes.specs.core import router, _require_admin


class RegenerarNombresInput(BaseModel):
    dry_run: bool = True


class RecalcularRankingInput(BaseModel):
    dry_run: bool = True
    ventana_dias: int = 180


class AplicarClasificacionInput(BaseModel):
    """Aplica categorías a equipos. Acepta `categoria_ids` (lista de ids
    de categorías a asignar a ese equipo, reemplaza lo que tenga)."""
    asignaciones: list[dict]   # [{equipo_id, categoria_ids: [int]}]


class AprobarNombreInput(BaseModel):
    override: Optional[str] = None   # Si se manda, queda como override manual.
    revisado: bool = True             # Si False, vuelve a "pendiente".


# ── Regenerar nombres masivo ────────────────────────────────────────────

@router.post("/admin/equipos/regenerar-nombres")
def regenerar_nombres(payload: RegenerarNombresInput, request: Request):
    """Recalcula `nombre_publico` y `nombre_publico_largo` de todos los
    equipos. Modo dry-run por default — devuelve preview sin escribir."""
    _require_admin(request)
    with get_db() as conn:
        result = regenerar_nombres_todos(conn, dry_run=payload.dry_run)
        # Cap de respuesta para que no se pase de tamaño con 1000 equipos
        if len(result["cambios"]) > 200:
            result["cambios_truncados"] = True
            result["cambios_total"] = len(result["cambios"])
            result["cambios"] = result["cambios"][:200]
        return result


@router.get("/admin/equipos/{equipo_id}/nombre-publico-preview")
def preview_nombre_publico(equipo_id: int, request: Request):
    """Calcula y devuelve el nombre público de un equipo (sin escribir).
    Útil para que el form admin muestre cómo va a quedar el nombre antes
    de guardar."""
    _require_admin(request)
    with get_db() as conn:
        try:
            corto, largo = calcular_nombres_para(conn, equipo_id)
            return {
                "equipo_id": equipo_id,
                "nombre_publico": corto,
                "nombre_publico_largo": largo,
            }
        except ValueError as e:
            raise HTTPException(404, str(e))


# ── Recalcular ranking ───────────────────────────────────────────────────

@router.post("/admin/equipos/recalcular-ranking")
def recalcular_ranking(payload: RecalcularRankingInput, request: Request):
    """Recalcula `popularidad_score`, `cant_pedidos` e `ingreso_total_ars`
    para todos los equipos, basado en el historial de alquileres en la
    ventana especificada (180 días por default)."""
    _require_admin(request)
    if payload.ventana_dias < 1 or payload.ventana_dias > 3650:
        raise HTTPException(400, "ventana_dias debe estar entre 1 y 3650")
    with get_db() as conn:
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

    with get_db() as conn:
        # El centinela del Estudio no es un producto: nunca entra al flujo de specs.
        where = ["e.es_recurso_interno = FALSE"]
        params: list = []
        if equipo_ids:
            placeholders = ",".join(["%s"] * len(equipo_ids))
            where.append(f"e.id IN ({placeholders})")
            params.extend(int(i) for i in equipo_ids)
        elif solo_sin:
            where.append(
                "NOT EXISTS (SELECT 1 FROM equipo_categorias ec WHERE ec.equipo_id = e.id)"
            )

        clause = "WHERE " + " AND ".join(where)
        rows = conn.execute(
            f"SELECT e.id, e.nombre, {MARCA_SUBQUERY}, e.modelo, e.foto_url "
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


@router.post("/admin/equipos/aplicar-clasificacion")
def aplicar_clasificacion(payload: AplicarClasificacionInput, request: Request):
    """Aplica categorías a una lista de equipos. Para cada equipo en
    `asignaciones`, REEMPLAZA las categorías existentes por las nuevas.

    Después de aplicar, recalcula nombre_publico para cada equipo
    afectado (la categoría cambia el template aplicable)."""
    _require_admin(request)

    if not payload.asignaciones:
        raise HTTPException(400, "asignaciones vacío")

    aplicados = []
    errores = []
    with get_db() as conn:
        try:
            for asig in payload.asignaciones:
                try:
                    eq_id = int(asig.get("equipo_id"))
                    cat_ids = [int(c) for c in (asig.get("categoria_ids") or [])]
                except (TypeError, ValueError):
                    errores.append({"equipo_id": asig.get("equipo_id"), "error": "ids inválidos"})
                    continue

                conn.execute("DELETE FROM equipo_categorias WHERE equipo_id = %s", (eq_id,))
                for orden, cat_id in enumerate(cat_ids):
                    conn.execute(
                        "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) "
                        "VALUES (%s, %s, %s) ON CONFLICT (equipo_id, categoria_id) DO NOTHING",
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


@router.get("/admin/equipos/sin-categoria")
def listar_sin_categoria(request: Request):
    """Cuenta los equipos sin ninguna categoría asignada (para badge nav)."""
    _require_admin(request)
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM equipos e "
            "WHERE e.es_recurso_interno = FALSE "
            "AND NOT EXISTS (SELECT 1 FROM equipo_categorias ec WHERE ec.equipo_id = e.id)"
        ).fetchone()
        return {"total": row["cnt"]}


# ── Aprobar / overridear nombre público ─────────────────────────────────

@router.put("/admin/equipos/{equipo_id}/nombre-publico")
def aprobar_o_editar_nombre(equipo_id: int, payload: AprobarNombreInput, request: Request):
    """Marca un nombre como revisado y opcionalmente lo overridea.
      - override=null + revisado=true → mantener el auto-generado, marcar como aprobado.
      - override="texto" + revisado=true → guardar override manual.
      - revisado=false → volver a "pendiente" (descarta override).
    """
    _require_admin(request)
    with get_db() as conn:
        try:
            eq = conn.execute("SELECT id FROM equipos WHERE id = %s", (equipo_id,)).fetchone()
            if not eq:
                raise HTTPException(404, "Equipo no existe")

            override = payload.override.strip() if (payload.override and payload.override.strip()) else None

            if not payload.revisado:
                # Volver a pendiente: descartar override y recalcular auto.
                conn.execute(
                    "UPDATE equipos SET nombre_publico_override = NULL, "
                    "nombre_publico_revisado = FALSE WHERE id = %s",
                    (equipo_id,),
                )
                try:
                    actualizar_nombres_de(conn, equipo_id, commit=False)
                except Exception:
                    pass
            else:
                conn.execute(
                    "UPDATE equipos SET nombre_publico_override = %s, "
                    "nombre_publico_revisado = TRUE WHERE id = %s",
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
                "FROM equipos WHERE id = %s",
                (equipo_id,),
            ).fetchone()
            return row_to_dict(row)
        except Exception:
            conn.rollback()
            raise


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

    with get_db() as conn:
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

