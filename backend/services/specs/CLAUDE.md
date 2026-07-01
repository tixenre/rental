# `services/specs/` — motor de specs (en construcción, Fase 0)

> **Estado: andamiaje.** Este paquete todavía no tiene lógica. El código real de specs
> sigue en `backend/specs/` (registry), `backend/services/spec_coerce.py`,
> `backend/services/spec_persist.py` y `backend/specs/validation.py` hasta que la
> **Fase 1** (move verbatim) los traslade acá. Plan completo + fases →
> [`docs/PLAN_SPECS_REDISENO.md`](../../../docs/PLAN_SPECS_REDISENO.md) · tracking →
> issue [#1163](https://github.com/tixenre/rental/issues/1163).

## Por qué existe (antes de tener código)

Es un **strangler-refactor en el lugar**, no un rewrite paralelo: el modelo de datos
(`spec_definitions` + `equipo_specs`) está sano y se conserva verbatim. Lo que cambia es
la organización del código (a CQRS-lite, espejo de `services/categorias/`) y se agrega,
100% aditivo, el **embudo de alias de valor** (normaliza/valida/busca/compat con una sola
pieza) + la **búsqueda derivada de specs** en vivo.

## Estructura objetivo (se puebla fase a fase — ver el plan)

```
services/specs/
  __init__.py      # barrel público. __all__ es el contrato real.
  errors.py        # ErrorSpec (400), SpecNoExiste (404), ValorNoCanonico (400)
  registry/        # SpecDef, CategoriaRegistry — mudanza de backend/specs/ (Fase 1)
    models.py
    catalogo/
    shared/
  commands/        # escritura — única puerta de mutación
    persist.py     #   persistir_specs — choke-point del embudo (Fase 1, luego Fase 3)
    coerce.py      #   coerce_and_serialize (Fase 1, luego Fase 3)
    value_aliases.py  # CRUD de spec_value_aliases (Fase 2/3, nuevo)
    seed.py        #   seed_all — MOVE VERBATIM del seeder, no se reescribe (Fase 1)
  queries/         # lectura — nunca mutan
    definitions.py
    equipo_specs.py
    validation.py  #   _check_value mapea vía el embudo (Fase 1, luego Fase 3)
    search_source.py  # proyección specs→texto buscable (Fase 4, nuevo)
    aliases.py         # expansión de término para búsqueda (Fase 4, nuevo)
  normalize/
    value_funnel.py    # mapear_valor(conn, spec_def_id, raw) — el embudo (Fase 2/3, nuevo)
```

## Reglas (van a regir desde que haya código; se aplican ya al diseñar cada fase)

- **Commands** son la única forma de mutar `spec_definitions`/`equipo_specs`.
- **Queries** nunca mutan.
- Commands importan de queries si hace falta. Queries nunca importan de commands.
- No FastAPI: todo recibe `conn`. Auth es responsabilidad de la ruta que llama.
- El **seeder se mueve verbatim** (Fase 1) — no se reescribe. Es la pieza que cascadea
  sobre datos reales (`purge_stale_specs` hace `DELETE ... CASCADE`); reescribirlo por
  prolijidad es riesgo sin ganancia. Ver trade-offs en el plan.
- El **motor de compatibilidad** (`routes/specs/compatibilidad.py`) no se muda acá — se le
  da una puerta de lectura limpia, pero la lógica de matching queda donde está.
- `spec_value_aliases` es **tabla**, no columna JSONB en `spec_definitions` — se consulta
  en las dos direcciones (alias→canónico al persistir, canónico→[alias] al buscar).

## Qué NO hacer

- No agregar lógica nueva de specs en `routes/specs/*.py` — pasa a `commands/`/`queries/`
  a medida que cada fase las mueve.
- No inventar un segundo mecanismo de normalización de valores en paralelo al embudo
  (`normalize/value_funnel.py`) cuando exista.
- No mover el motor de compatibilidad ni reescribir el seeder "ya que estamos" — no lo
  pide ningún objetivo de la iniciativa; es exactamente el riesgo que el plan evitó a
  propósito.
