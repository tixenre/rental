"""queries/propuestas.py — lectura de la cola de propuestas (Canal C).

Ver `commands/propuestas.py` para el porqué de la tabla y la regla de
"nunca aplica sola"."""

from __future__ import annotations


def listar_propuestas_pendientes(conn) -> list[dict]:
    """Propuestas sin aplicar ni descartar, más recientes primero."""
    rows = conn.execute(
        "SELECT id, tipo, payload, origen, confianza, equipo_id, created_at"
        " FROM spec_propuestas_pendientes"
        " WHERE aplicado_at IS NULL AND descartado_at IS NULL"
        " ORDER BY created_at DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def listar_no_reconocidos_agrupados(conn) -> list[dict]:
    """Propuestas `spec_nueva` pendientes, agrupadas por (categoria,
    label_normalizado) — #1203, panel admin de specs no reconocidos. Une lo
    que produce el CLI offline (agregado, sin equipo) con lo que produce el
    upload en vivo (una fila por equipo, sin umbral): misma forma de
    payload (`commands/proponer.py`), ambos productores conviven en una
    sola vista. `equipos` es `[]` para propuestas agregadas sin atribución.

    `ejemplos` se desarma acá (no en SQL): cada fila subyacente trae su propio
    array JSON de hasta 5 valores; agregarlos en Postgres exigiría un
    `jsonb_array_elements_text` lateral por poco beneficio — más simple leer
    el array crudo y aplanar/deduplicar en Python."""
    rows = conn.execute(
        """
        SELECT
          p.payload->>'categoria' AS categoria,
          p.payload->>'label' AS label,
          p.payload->>'label_normalizado' AS label_normalizado,
          array_agg(p.payload->'ejemplos' ORDER BY p.id) AS ejemplos_por_fila,
          array_agg(p.id ORDER BY p.id) AS propuesta_ids,
          COALESCE(array_agg(DISTINCT e.id) FILTER (WHERE e.id IS NOT NULL), ARRAY[]::int[]) AS equipo_ids,
          COALESCE(array_agg(DISTINCT e.nombre) FILTER (WHERE e.id IS NOT NULL), ARRAY[]::text[]) AS equipo_nombres,
          MAX(p.created_at) AS ultima_vez
        FROM spec_propuestas_pendientes p
        LEFT JOIN equipos e ON e.id = p.equipo_id
        WHERE p.tipo = 'spec_nueva'
          AND p.aplicado_at IS NULL
          AND p.descartado_at IS NULL
        GROUP BY p.payload->>'categoria', p.payload->>'label', p.payload->>'label_normalizado'
        ORDER BY MAX(p.created_at) DESC
        """
    ).fetchall()

    out = []
    for row in rows:
        d = dict(row)
        ejemplos: list[str] = []
        for fila in d.pop("ejemplos_por_fila") or []:
            for v in (fila or []):
                if v not in ejemplos:
                    ejemplos.append(v)
        d["ejemplos"] = ejemplos[:5]
        out.append(d)
    return out
