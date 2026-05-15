"""
routes/inventario.py — Calidad y completitud del inventario.

Parte 1/4 del epic #93 (issue #349): dashboard read-only que cuenta
qué equipos tienen campos faltantes para que el admin sepa dónde poner foco.
"""

from fastapi import APIRouter, Depends

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
