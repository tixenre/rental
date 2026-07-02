"""commands/propuestas.py — Canal C: cola de propuestas de aprendizaje.

`spec_propuestas_pendientes` ya existía en el schema (creada para el skill
`gear-compatibility`, que nunca llegó a escribirle — tabla huérfana,
verificado: ningún código fuera de schema.py/migrations la referenciaba).
`specs_ingesta` es el primer productor real (F7 del rediseño de ingesta,
`commands/proponer.py`): unmatched frecuentes → acá.

Regla dura: **esto NUNCA muta el registry.** `aplicar_propuesta` solo cierra
el ítem de la cola DESPUÉS de que el humano ya editó `registry/catalogo/*.py`
a mano (el código sigue siendo la fuente única de specs/aliases) y corrió el
seeder — no hay "aplicar" automático que escriba `spec_definitions` desde acá.
"""

from __future__ import annotations

import json


def encolar_propuesta(
    conn,
    *,
    tipo: str,
    payload: dict,
    origen: str | None = None,
    confianza: float | None = None,
    equipo_id: int | None = None,
) -> int:
    """Encola una propuesta. `tipo` ∈ {enum_option, spec_nueva, merge_specs,
    assign_spec} (CHECK constraint de la tabla). Nunca se aplica sola — queda
    pendiente hasta que el dueño la revise. `equipo_id` (#1203, opcional): qué
    equipo la encontró — lo usa el productor "live" (upload en vivo, sin
    umbral); el productor agregado del CLI offline (F7a) lo deja NULL."""
    return conn.insert_returning(
        "INSERT INTO spec_propuestas_pendientes (tipo, payload, origen, confianza, equipo_id)"
        " VALUES (%s, %s, %s, %s, %s)",
        (tipo, json.dumps(payload, ensure_ascii=False), origen, confianza, equipo_id),
    )


def aplicar_propuesta(conn, propuesta_id: int) -> None:
    """Marca la propuesta como aplicada (bookkeeping). El cambio real al
    registry ya lo hizo el humano a mano — ver docstring del módulo."""
    conn.execute(
        "UPDATE spec_propuestas_pendientes SET aplicado_at = CURRENT_TIMESTAMP WHERE id = %s",
        (propuesta_id,),
    )


def descartar_propuesta(conn, propuesta_id: int) -> None:
    """Marca la propuesta como descartada (el dueño decidió que no aplica)."""
    conn.execute(
        "UPDATE spec_propuestas_pendientes SET descartado_at = CURRENT_TIMESTAMP WHERE id = %s",
        (propuesta_id,),
    )
