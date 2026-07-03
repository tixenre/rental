"""queries/audit.py — Reportes agregados sobre el estado de la taxonomía.

Alimentan el dashboard de calidad del catálogo (`/api/admin/inventario/calidad`,
`routes/inventario.py`) y, a futuro, la feature de completitud de catálogo
(equipos/categorías con datos faltantes — skill `catalogo`)."""


def equipos_sin_categoria(conn) -> int:
    """Cantidad de equipos activos (no eliminados, no centinela del Estudio)
    sin ninguna categoría asignada. Usado hoy por el dashboard de calidad."""
    row = conn.execute("""
        SELECT COUNT(*)
        FROM equipos e
        WHERE e.eliminado_at IS NULL
          AND e.es_recurso_interno = FALSE
          AND NOT EXISTS (
            SELECT 1 FROM equipo_categorias ec WHERE ec.equipo_id = e.id
          )
    """).fetchone()
    return row[0]


def categorias_sin_equipos(conn) -> list[dict]:
    """Categorías (de cualquier nivel) sin ningún equipo asignado directamente.

    Reservada para la feature de completitud de catálogo (aún sin consumidor
    en este commit) — no borrar por "código muerto"; es la contraparte de
    `equipos_sin_categoria` para ese dashboard."""
    rows = conn.execute("""
        SELECT c.id, c.nombre, c.prioridad
        FROM categorias c
        LEFT JOIN equipo_categorias ec ON ec.categoria_id = c.id
        GROUP BY c.id, c.nombre, c.prioridad
        HAVING COUNT(ec.equipo_id) = 0
        ORDER BY c.prioridad ASC, LOWER(c.nombre) ASC
    """).fetchall()
    return [{"id": r["id"], "nombre": r["nombre"], "prioridad": r["prioridad"]} for r in rows]
