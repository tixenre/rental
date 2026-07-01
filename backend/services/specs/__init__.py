"""services/specs — barrel público del motor de specs (en construcción).

Fase 0 del rediseño (ver docs/PLAN_SPECS_REDISENO.md e issue #1163): por ahora
este paquete es andamiaje vacío, cero comportamiento. Todo el código real de
specs sigue viviendo en `backend/specs/` (registry) y
`backend/services/spec_coerce.py` / `spec_persist.py` (persistencia) hasta la
Fase 1 (move verbatim + shims ⏰ LEGACY en los paths viejos).

Estructura objetivo (se puebla fase a fase, no de una):
    registry/   — SpecDef, CategoriaRegistry (mudanza de backend/specs/)
    commands/   — persist, coerce, value_aliases, seed (escritura)
    queries/    — definitions, equipo_specs, validation, search_source, aliases (lectura)
    normalize/  — value_funnel.mapear_valor (el embudo de alias de valor)

Mismo patrón que `services/categorias/`: commands = única puerta de escritura,
queries nunca mutan, todo recibe `conn`, sin dependencia de FastAPI.
"""

__all__: list[str] = []
