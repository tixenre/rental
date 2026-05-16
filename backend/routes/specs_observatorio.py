"""
routes/specs_observatorio.py — Relevamiento de specs reales del inventario.

El "observatorio" lee el cache de scrapes (`equipo_fichas.raw_json`) que dejó
el flujo de autocompletar (B&H/Adorama → Firecrawl → LLM), extrae las specs
detectadas y las guarda en la tabla `spec_observacion`. Después, expone
agregados por categoría para decidir:

  - Qué labels aparecen seguido y NO tienen template canónico (gaps).
  - Qué valores se repiten para cada label (¿conviene enum vs string?).
  - Qué versiones de HDMI/SDI/etc. aparecen realmente para calibrar las
    familias jerárquicas hardcoded.

Endpoints:
  - POST /admin/specs/observatorio/recompute — rebuild de la tabla.
  - GET  /admin/specs/observatorio/agregado?categoria=X — distribución.
  - GET  /admin/specs/observatorio/stats — counts globales.

Diseño:
  - La tabla `spec_observacion` es denormalizada (`categoria_raiz` cached).
  - `recompute` borra y reinserta — idempotente, simple.
  - El matching contra `spec_definitions` usa label normalizado (sin tildes,
    lowercase) — mismo approach que `services/spec_render.norm_spec_label`.
"""

import json as _json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from admin_guard import require_admin
from database import get_db, row_to_dict
from services.spec_render import norm_spec_label


router = APIRouter()
logger = logging.getLogger(__name__)


class RecomputeOutput(BaseModel):
    equipos_procesados: int
    observaciones_insertadas: int
    labels_unicos: int
    sin_raw_json: int


def _extract_specs_from_raw(raw_json_str: str) -> list[dict]:
    """Saca la lista de specs del cache de scrape. El raw_json tiene shape
    {marca, modelo, foto_url, specs: [{label, value}], ...} — devolvemos
    `specs` o [] si no está."""
    try:
        data = _json.loads(raw_json_str)
    except Exception:
        return []
    specs = data.get("specs")
    if not isinstance(specs, list):
        return []
    out: list[dict] = []
    for s in specs:
        if not isinstance(s, dict):
            continue
        label = s.get("label")
        value = s.get("value")
        if not label or value is None or value == "":
            continue
        out.append({"label": str(label), "value": str(value)})
    return out


def _categoria_raiz_del_equipo(conn, equipo_id: int) -> Optional[str]:
    """Devuelve el nombre de la categoría raíz del equipo (parent_id IS NULL).
    Si el equipo está en varias raíces, gana la de menor prioridad."""
    row = conn.execute(
        """
        SELECT c.nombre AS nombre
        FROM equipo_categorias ec
        JOIN categorias c ON c.id = ec.categoria_id
        WHERE ec.equipo_id = ?
          AND c.parent_id IS NULL
        ORDER BY c.prioridad NULLS LAST, c.nombre
        LIMIT 1
        """,
        (equipo_id,),
    ).fetchone()
    if not row:
        # Si no tiene raíz directa, busca el ancestro raíz de su categoría más prioritaria.
        row = conn.execute(
            """
            WITH RECURSIVE chain AS (
                SELECT c.id, c.parent_id, c.nombre, c.prioridad
                FROM equipo_categorias ec
                JOIN categorias c ON c.id = ec.categoria_id
                WHERE ec.equipo_id = ?
                UNION
                SELECT p.id, p.parent_id, p.nombre, p.prioridad
                FROM categorias p
                JOIN chain ON p.id = chain.parent_id
            )
            SELECT nombre FROM chain WHERE parent_id IS NULL
            ORDER BY prioridad NULLS LAST, nombre
            LIMIT 1
            """,
            (equipo_id,),
        ).fetchone()
    return row["nombre"] if row else None


def _spec_def_index(conn) -> dict[str, dict]:
    """Devuelve un dict {label_normalizado: {id, spec_key}} con TODAS las
    spec_definitions vigentes — usado para matching contra observaciones.

    Incluye tanto el `label` canónico como cada item de `aliases` (también
    normalizado). Permite que el observatorio matchee labels alternativos
    sin tocar el spec canónico (ej. "Montura" → spec lens_mount via
    aliases, sin renombrar el spec)."""
    rows = conn.execute(
        "SELECT id, spec_key, label, aliases FROM spec_definitions"
    ).fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        d = row_to_dict(r) if not isinstance(r, dict) else r
        spec_id = d["id"]
        spec_key = d["spec_key"]

        # 1) Label canónico.
        norm = norm_spec_label(d.get("label") or "")
        if norm and norm not in out:
            out[norm] = {"id": spec_id, "spec_key": spec_key}

        # 2) Aliases (si los tiene). El primer match gana (no pisa el canónico).
        aliases = d.get("aliases")
        if isinstance(aliases, str):
            try:
                import json as _json
                aliases = _json.loads(aliases)
            except Exception:
                aliases = None
        if isinstance(aliases, list):
            for alias in aliases:
                if not alias:
                    continue
                alias_norm = norm_spec_label(str(alias))
                if alias_norm and alias_norm not in out:
                    out[alias_norm] = {"id": spec_id, "spec_key": spec_key}
    return out


@router.post(
    "/admin/specs/observatorio/recompute",
    response_model=RecomputeOutput,
)
def recompute_observatorio(request: Request) -> RecomputeOutput:
    """Reset + reinsert: borra `spec_observacion` y la repuebla desde
    `equipo_fichas.raw_json` de todos los equipos que lo tengan cacheado.

    Idempotente — corré las veces que quieras. La uniqueness por
    (equipo_id, label_normalizado) previene duplicados dentro de un equipo
    si raw_json trae el mismo label dos veces con casing distinto."""
    require_admin(request)
    conn = get_db()
    try:
        conn.execute("DELETE FROM spec_observacion")

        # Equipos con raw_json no nulo.
        eq_rows = conn.execute(
            """
            SELECT e.id, ef.raw_json, ef.fuente_url
            FROM equipos e
            JOIN equipo_fichas ef ON ef.equipo_id = e.id
            WHERE e.eliminado_at IS NULL
              AND ef.raw_json IS NOT NULL
              AND ef.raw_json <> ''
            """
        ).fetchall()

        spec_idx = _spec_def_index(conn)

        total_equipos = 0
        total_obs = 0
        labels_norm_set: set[str] = set()
        sin_raw_json = 0

        for eq_row in eq_rows:
            eq = row_to_dict(eq_row) if not isinstance(eq_row, dict) else eq_row
            equipo_id = eq["id"]
            raw_json_str = eq.get("raw_json") or ""
            fuente_url = eq.get("fuente_url") or ""

            specs = _extract_specs_from_raw(raw_json_str)
            if not specs:
                sin_raw_json += 1
                continue

            cat_raiz = _categoria_raiz_del_equipo(conn, equipo_id)
            source = _source_from_url(fuente_url)

            seen_labels: set[str] = set()
            equipo_tuvo_obs = False
            for s in specs:
                label_obs = s["label"].strip()
                norm = norm_spec_label(label_obs)
                if not norm or norm in seen_labels:
                    continue
                seen_labels.add(norm)
                labels_norm_set.add(norm)

                match = spec_idx.get(norm)
                spec_def_id = match["id"] if match else None
                matched = match is not None

                conn.execute(
                    """
                    INSERT INTO spec_observacion
                      (equipo_id, categoria_raiz, label_observado,
                       label_normalizado, value_observado, spec_def_id,
                       matched_template, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (equipo_id, label_normalizado) DO NOTHING
                    """,
                    (
                        equipo_id, cat_raiz, label_obs, norm,
                        s["value"], spec_def_id, matched, source,
                    ),
                )
                total_obs += 1
                equipo_tuvo_obs = True
            if equipo_tuvo_obs:
                total_equipos += 1

        conn.commit()
        return RecomputeOutput(
            equipos_procesados=total_equipos,
            observaciones_insertadas=total_obs,
            labels_unicos=len(labels_norm_set),
            sin_raw_json=sin_raw_json,
        )
    except Exception:
        conn.rollback()
        logger.exception("recompute_observatorio falló")
        raise HTTPException(500, "Recompute falló — ver logs")
    finally:
        conn.close()


def _source_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    u = url.lower()
    if "bhphotovideo" in u or "bh.com" in u:
        return "bh"
    if "adorama" in u:
        return "adorama"
    return "otro"


@router.get("/admin/specs/observatorio/agregado")
def agregado_observatorio(
    request: Request,
    categoria: Optional[str] = Query(None, description="Filtrar por categoría raíz"),
    solo_unmapped: bool = Query(
        False, description="Solo labels que NO matchean ningún template"
    ),
    top_values: int = Query(5, ge=1, le=20),
) -> dict:
    """Para cada (categoría, label) observado: cuántos equipos lo tienen,
    cuáles son los top-N valores más frecuentes, qué proporción matchea
    un template. Sirve para decidir qué labels canonizar y qué
    enum_options agregar a un spec existente."""
    require_admin(request)
    conn = get_db()
    try:
        params: list = []
        where_extra = ""
        if categoria:
            where_extra += " AND so.categoria_raiz = ?"
            params.append(categoria)
        if solo_unmapped:
            where_extra += " AND so.matched_template = FALSE"

        # Step 1: por (categoria_raiz, label_normalizado), conteo + matched flag.
        rows = conn.execute(
            f"""
            SELECT
                so.categoria_raiz,
                so.label_normalizado,
                MIN(so.label_observado) AS label_observado_sample,
                COUNT(*) AS equipos_count,
                bool_or(so.matched_template) AS algun_match,
                MIN(so.spec_def_id) AS spec_def_id
            FROM spec_observacion so
            WHERE 1=1 {where_extra}
            GROUP BY so.categoria_raiz, so.label_normalizado
            ORDER BY equipos_count DESC, so.label_normalizado
            """,
            params,
        ).fetchall()

        items: list[dict] = []
        for r in rows:
            d = row_to_dict(r) if not isinstance(r, dict) else r
            cat = d["categoria_raiz"]
            label_norm = d["label_normalizado"]

            # Top values para ese (cat, label).
            top = conn.execute(
                """
                SELECT value_observado AS value, COUNT(*) AS count
                FROM spec_observacion
                WHERE label_normalizado = ?
                  AND (categoria_raiz = ? OR (categoria_raiz IS NULL AND ? IS NULL))
                GROUP BY value_observado
                ORDER BY count DESC, value_observado
                LIMIT ?
                """,
                (label_norm, cat, cat, top_values),
            ).fetchall()

            items.append({
                "categoria_raiz": cat,
                "label_observado": d["label_observado_sample"],
                "label_normalizado": label_norm,
                "equipos_count": d["equipos_count"],
                "matched_template": d["algun_match"],
                "spec_def_id": d["spec_def_id"],
                "top_values": [
                    {"value": (row_to_dict(t) if not isinstance(t, dict) else t)["value"],
                     "count": (row_to_dict(t) if not isinstance(t, dict) else t)["count"]}
                    for t in top
                ],
            })

        return {"total": len(items), "items": items}
    finally:
        conn.close()


@router.get("/admin/specs/observatorio/scrapeables-pendientes")
def listar_scrapeables_pendientes(request: Request) -> dict:
    """Devuelve los IDs de equipos que tienen `bh_url` cargada pero
    no tienen `equipo_fichas.raw_json` cacheado. Son los candidatos
    para correr `batch-enriquecer` masivamente desde la UI del
    observatorio."""
    require_admin(request)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT e.id, e.nombre, e.bh_url
            FROM equipos e
            LEFT JOIN equipo_fichas ef ON ef.equipo_id = e.id
            WHERE e.eliminado_at IS NULL
              AND e.bh_url IS NOT NULL
              AND TRIM(e.bh_url) <> ''
              AND (ef.raw_json IS NULL OR TRIM(ef.raw_json) = '')
            ORDER BY e.id
            """
        ).fetchall()
        items = [
            {"id": r["id"], "nombre": r["nombre"], "bh_url": r["bh_url"]}
            for r in rows
        ]
        return {"total": len(items), "items": items, "ids": [it["id"] for it in items]}
    finally:
        conn.close()


@router.get("/admin/specs/observatorio/stats")
def stats_observatorio(request: Request) -> dict:
    """Resumen global: total observaciones, equipos cubiertos, % matched."""
    require_admin(request)
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_obs,
                COUNT(DISTINCT equipo_id) AS equipos_cubiertos,
                COUNT(DISTINCT label_normalizado) AS labels_unicos,
                SUM(CASE WHEN matched_template THEN 1 ELSE 0 END) AS matched_count,
                SUM(CASE WHEN NOT matched_template THEN 1 ELSE 0 END) AS unmatched_count
            FROM spec_observacion
            """
        ).fetchone()
        d = row_to_dict(row) if not isinstance(row, dict) else (row or {})

        last_obs = conn.execute(
            "SELECT MAX(observed_at) AS last_obs FROM spec_observacion"
        ).fetchone()
        last_d = row_to_dict(last_obs) if not isinstance(last_obs, dict) else (last_obs or {})

        equipos_con_raw = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM equipos e
            JOIN equipo_fichas ef ON ef.equipo_id = e.id
            WHERE e.eliminado_at IS NULL
              AND ef.raw_json IS NOT NULL
              AND ef.raw_json <> ''
            """
        ).fetchone()
        raw_d = row_to_dict(equipos_con_raw) if not isinstance(equipos_con_raw, dict) else (equipos_con_raw or {})

        # Equipos scrapeables pero todavía no scrapeados: tienen bh_url
        # cargada pero `equipo_fichas.raw_json` está vacío o no existe.
        # Si querés más data en el observatorio, hay que correr
        # batch-enriquecer sobre estos.
        equipos_pendientes = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM equipos e
            LEFT JOIN equipo_fichas ef ON ef.equipo_id = e.id
            WHERE e.eliminado_at IS NULL
              AND e.bh_url IS NOT NULL
              AND TRIM(e.bh_url) <> ''
              AND (ef.raw_json IS NULL OR TRIM(ef.raw_json) = '')
            """
        ).fetchone()
        pend_d = row_to_dict(equipos_pendientes) if not isinstance(equipos_pendientes, dict) else (equipos_pendientes or {})

        # Total de equipos activos (para contextualizar los demás counts).
        total_eq = conn.execute(
            "SELECT COUNT(*) AS n FROM equipos WHERE eliminado_at IS NULL"
        ).fetchone()
        total_d = row_to_dict(total_eq) if not isinstance(total_eq, dict) else (total_eq or {})

        return {
            "total_obs": d.get("total_obs", 0) or 0,
            "equipos_cubiertos": d.get("equipos_cubiertos", 0) or 0,
            "labels_unicos": d.get("labels_unicos", 0) or 0,
            "matched_count": d.get("matched_count", 0) or 0,
            "unmatched_count": d.get("unmatched_count", 0) or 0,
            "equipos_con_raw_json": raw_d.get("n", 0) or 0,
            "equipos_scrapeables_pendientes": pend_d.get("n", 0) or 0,
            "equipos_total": total_d.get("n", 0) or 0,
            "last_observed_at": last_d.get("last_obs"),
        }
    finally:
        conn.close()
