"""
routes/inventario.py — Calidad y completitud del inventario.

Parte del epic #93. Incluye:
- #349 Dashboard de calidad (read-only, métricas de completitud).
- #352 Sugerencias automáticas (detectores + apply para inconsistencias).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import get_db
from admin_guard import require_admin

router = APIRouter()


@router.get("/inventario/calidad")
def get_calidad_inventario(_admin: dict = Depends(require_admin)):
    """
    Devuelve métricas de completitud del inventario.

    Solo cuenta equipos activos (eliminado_at IS NULL). Un equipo se considera
    "faltante" en un campo si está NULL o vacío.
    """
    conn = get_db()
    try:
        # Total de equipos activos.
        total = conn.execute(
            "SELECT COUNT(*) FROM equipos WHERE eliminado_at IS NULL"
        ).fetchone()[0]

        # Campos faltantes — una query con COUNT FILTER por cada campo.
        # NULLIF + COALESCE para tratar string vacío y NULL igual.
        row = conn.execute("""
            SELECT
              COUNT(*) FILTER (WHERE NULLIF(TRIM(COALESCE(e.serie, '')), '') IS NULL)        AS sin_serie,
              COUNT(*) FILTER (WHERE e.valor_reposicion IS NULL OR e.valor_reposicion = 0)   AS sin_valor_reposicion,
              COUNT(*) FILTER (WHERE NULLIF(TRIM(COALESCE(e.foto_url, '')), '') IS NULL)     AS sin_foto,
              COUNT(*) FILTER (WHERE NULLIF(TRIM(COALESCE(f.descripcion, '')), '') IS NULL)  AS sin_descripcion,
              COUNT(*) FILTER (WHERE NULLIF(TRIM(COALESCE(e.nombre_publico, '')), '') IS NULL) AS sin_nombre_publico
            FROM equipos e
            LEFT JOIN equipo_fichas f ON f.equipo_id = e.id
            WHERE e.eliminado_at IS NULL
        """).fetchone()

        # Equipos sin categoría: no aparecen en equipo_categorias.
        sin_categoria = conn.execute("""
            SELECT COUNT(*)
            FROM equipos e
            WHERE e.eliminado_at IS NULL
              AND NOT EXISTS (
                SELECT 1 FROM equipo_categorias ec WHERE ec.equipo_id = e.id
              )
        """).fetchone()[0]

        faltantes = {
            "serie":              row["sin_serie"],
            "valor_reposicion":   row["sin_valor_reposicion"],
            "foto":               row["sin_foto"],
            "descripcion":        row["sin_descripcion"],
            "nombre_publico":     row["sin_nombre_publico"],
            "categoria":          sin_categoria,
        }

        # Score de completitud: cada equipo tiene 6 "slots" (serie, valor,
        # foto, descripción, nombre público, categoría). Slot lleno = +1.
        # Total posible = total * 6. Porcentaje = slots llenos / total posible.
        if total == 0:
            completos_pct = 100
        else:
            slots_totales = total * len(faltantes)
            slots_faltantes = sum(faltantes.values())
            completos_pct = round(100 * (slots_totales - slots_faltantes) / slots_totales)

        return {
            "total": total,
            "completos_pct": completos_pct,
            "faltantes": faltantes,
        }
    finally:
        conn.close()


# ── Sugerencias automáticas (#352) ───────────────────────────────────────────
#
# Detectores que comparan datos y proponen fix sin auto-aplicar. El admin
# revisa y decide. MVP con 2 detectores: marcas duplicadas case-insensitive
# y precio AR sin USD. Más detectores landean en iteraciones siguientes.


def _detect_marcas_duplicadas(conn) -> list[dict]:
    """Detecta marcas con mismo nombre normalizado (lowercase + trim) pero
    distinto registro en la tabla. Ej. 'Sony', 'sony', 'SONY' — fragmentan
    reportes y carruseles. Apply = fusionar al canonical (el más usado)."""
    rows = conn.execute("""
        SELECT
          LOWER(TRIM(nombre)) AS clave,
          json_agg(json_build_object(
            'id', id,
            'nombre', nombre,
            'cant_pedidos', cant_pedidos,
            'equipos', (SELECT COUNT(*) FROM equipos WHERE brand_id = m.id AND eliminado_at IS NULL)
          ) ORDER BY cant_pedidos DESC, id ASC) AS marcas
        FROM marcas m
        GROUP BY LOWER(TRIM(nombre))
        HAVING COUNT(*) > 1
    """).fetchall()
    out = []
    for r in rows:
        marcas = r["marcas"]
        # Canonical = primer item (orden por cant_pedidos DESC).
        out.append({
            "tipo": "marcas_duplicadas",
            "ref": r["clave"],
            "titulo": f"Marca duplicada: {marcas[0]['nombre']}",
            "detalle": (
                f"Hay {len(marcas)} variantes con el mismo nombre normalizado. "
                f"Canonical sugerida: '{marcas[0]['nombre']}' "
                f"({marcas[0]['cant_pedidos']} pedidos · {marcas[0]['equipos']} equipos)"
            ),
            "marcas": marcas,
            "accion": "fusionar",
            "accion_label": "Fusionar todas",
        })
    return out


def _detect_precio_sin_usd(conn) -> list[dict]:
    """Detecta equipos con precio_jornada cargado pero precio_usd vacío.
    Apply = computar precio_usd usando usd_rate de app_settings."""
    rows = conn.execute("""
        SELECT id, nombre, marca, precio_jornada
        FROM equipos
        WHERE eliminado_at IS NULL
          AND precio_jornada IS NOT NULL
          AND precio_jornada > 0
          AND (precio_usd IS NULL OR precio_usd = 0)
        ORDER BY precio_jornada DESC
        LIMIT 50
    """).fetchall()
    if not rows:
        return []
    return [{
        "tipo": "precio_sin_usd",
        "ref": "all",
        "titulo": f"{len(rows)} equipos con precio AR pero sin USD",
        "detalle": (
            "Estos equipos tienen precio_jornada cargado pero precio_usd vacío. "
            "El catálogo en USD muestra '—' para ellos. "
            "Apply = computar precio_usd usando la cotización actual."
        ),
        "equipos": [
            {"id": r["id"], "nombre": r["nombre"], "marca": r["marca"], "precio_jornada": r["precio_jornada"]}
            for r in rows
        ],
        "accion": "calcular_usd",
        "accion_label": "Calcular USD con cotización del día",
    }]


@router.get("/inventario/sugerencias")
def get_sugerencias(_admin: dict = Depends(require_admin)):
    """Devuelve la lista de sugerencias detectadas. No muta nada."""
    conn = get_db()
    try:
        items = []
        items += _detect_marcas_duplicadas(conn)
        items += _detect_precio_sin_usd(conn)
        return {"items": items, "total": len(items)}
    finally:
        conn.close()


class AplicarSugerenciaBody(BaseModel):
    tipo: str
    ref: str


@router.post("/inventario/sugerencias/aplicar")
def aplicar_sugerencia(body: AplicarSugerenciaBody, _admin: dict = Depends(require_admin)):
    """Aplica una sugerencia. Devuelve { ok: True, message: ... } o falla 400."""
    conn = get_db()
    try:
        if body.tipo == "marcas_duplicadas":
            return _apply_fusionar_marcas(conn, clave=body.ref)
        if body.tipo == "precio_sin_usd":
            return _apply_calcular_usd(conn)
        raise HTTPException(400, f"Tipo de sugerencia desconocido: {body.tipo}")
    finally:
        conn.close()


def _apply_fusionar_marcas(conn, clave: str) -> dict:
    """Fusiona todas las marcas con LOWER(nombre) = clave en una sola.
    Canonical = la que tiene más pedidos. Las demás se eliminan después de
    reapuntar sus equipos al canonical."""
    rows = conn.execute("""
        SELECT id, nombre, cant_pedidos
        FROM marcas
        WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(?))
        ORDER BY cant_pedidos DESC, id ASC
    """, (clave,)).fetchall()
    if len(rows) <= 1:
        raise HTTPException(400, "Nada para fusionar en esa clave.")
    canonical_id = rows[0]["id"]
    canonical_nombre = rows[0]["nombre"]
    duplicados_ids = [r["id"] for r in rows[1:]]
    placeholders = ",".join(["%s"] * len(duplicados_ids))
    # Repuntar equipos: brand_id + marca TEXT (que está cacheado).
    conn.execute(
        f"UPDATE equipos SET brand_id = ?, marca = ? WHERE brand_id IN ({placeholders})",
        (canonical_id, canonical_nombre, *duplicados_ids),
    )
    conn.execute(
        f"DELETE FROM marcas WHERE id IN ({placeholders})",
        tuple(duplicados_ids),
    )
    conn.commit()
    return {
        "ok": True,
        "message": (
            f"Fusionadas {len(duplicados_ids)} marcas duplicadas en '{canonical_nombre}'."
        ),
    }


def _apply_calcular_usd(conn) -> dict:
    """Computa precio_usd = precio_jornada / usd_rate para los equipos
    sin USD. Lee usd_rate de app_settings."""
    rate_row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", ("usd_rate",)
    ).fetchone()
    if not rate_row:
        raise HTTPException(400, "usd_rate no configurado en settings.")
    try:
        rate = float(rate_row["value"])
    except (TypeError, ValueError):
        raise HTTPException(400, "usd_rate inválido en settings.")
    if rate <= 0:
        raise HTTPException(400, "usd_rate debe ser > 0.")
    # Tener en cuenta el roi_pct_default si está, igual que el cálculo de
    # precio_jornada hace inverso. Por ahora cálculo simple: USD = ARS / rate.
    result = conn.execute("""
        UPDATE equipos
        SET precio_usd = ROUND((precio_jornada / ?)::numeric, 2)
        WHERE eliminado_at IS NULL
          AND precio_jornada IS NOT NULL
          AND precio_jornada > 0
          AND (precio_usd IS NULL OR precio_usd = 0)
    """, (rate,))
    n = result.rowcount if hasattr(result, "rowcount") else 0
    conn.commit()
    return {"ok": True, "message": f"{n} equipos actualizados con precio_usd calculado."}
