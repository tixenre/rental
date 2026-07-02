"""queries/propuestas.py — lectura de la cola de propuestas (Canal C).

Ver `commands/propuestas.py` para el porqué de la tabla y la regla de
"nunca aplica sola"."""

from __future__ import annotations


def listar_propuestas_pendientes(conn) -> list[dict]:
    """Propuestas sin aplicar ni descartar, más recientes primero."""
    rows = conn.execute(
        "SELECT id, tipo, payload, origen, confianza, created_at"
        " FROM spec_propuestas_pendientes"
        " WHERE aplicado_at IS NULL AND descartado_at IS NULL"
        " ORDER BY created_at DESC"
    ).fetchall()
    return [dict(row) for row in rows]
