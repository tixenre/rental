# `services/specs/` — motor de specs (en construcción, Fase 1 hecha)

> **Estado: registry + persistencia movidos, embudo/búsqueda todavía no.** `registry/`,
> `queries/validation.py` y `commands/{coerce,persist,seed}.py` son el código real, movido
> verbatim desde `backend/specs/`, `backend/services/spec_coerce.py`,
> `backend/services/spec_persist.py` y `backend/seeds/registry_seeder.py`. Esos paths viejos
> quedan como shims ⏰ LEGACY (re-exportan desde acá) hasta la **Fase 6**, que los borra.
> `commands/value_aliases.py`, `normalize/value_funnel.py` (el embudo) y
> `queries/{search_source,aliases}.py` (búsqueda derivada) son **Fases 2-4, todavía no
> existen**. Plan completo + fases → [`docs/PLAN_SPECS_REDISENO.md`](../../../docs/PLAN_SPECS_REDISENO.md)
> · tracking → issue [#1163](https://github.com/tixenre/rental/issues/1163).

## Por qué existe (antes de tener código)

Es un **strangler-refactor en el lugar**, no un rewrite paralelo: el modelo de datos
(`spec_definitions` + `equipo_specs`) está sano y se conserva verbatim. Lo que cambia es
la organización del código (a CQRS-lite, espejo de `services/categorias/`) y se agrega,
100% aditivo, el **embudo de alias de valor** (normaliza/valida/busca/compat con una sola
pieza) + la **búsqueda derivada de specs** en vivo.

## Estructura objetivo (se puebla fase a fase — ver el plan)

```
services/specs/
  __init__.py      # barrel público. __all__ es el contrato real.        ✓ Fase 1
  errors.py        # ErrorSpec (400), SpecNoExiste (404), ValorNoCanonico (400)  ✓ Fase 0
  registry/        # SpecDef, CategoriaRegistry — mudanza de backend/specs/     ✓ Fase 1
    models.py
    catalogo/      #   camaras/lentes/iluminacion/modificadores/adaptadores/filtros
    shared/        #   enums/lighting/optica/physical
  commands/        # escritura — única puerta de mutación
    persist.py     #   persistir_specs — choke-point del embudo         ✓ Fase 1 (mudado)
    coerce.py      #   coerce_and_serialize                              ✓ Fase 1 (mudado)
    seed.py        #   seed_all_categorias — MOVE VERBATIM del seeder    ✓ Fase 1 (mudado)
    value_aliases.py  # CRUD de spec_value_aliases                       ✗ Fase 2/3, no existe
  queries/         # lectura — nunca mutan
    validation.py  #   validate_dataset — _check_value mapeará vía el embudo en Fase 3  ✓ Fase 1 (mudado)
    definitions.py     # ✗ Fase futura, no existe
    equipo_specs.py    # ✗ Fase futura, no existe
    search_source.py   # proyección specs→texto buscable                ✗ Fase 4, no existe
    aliases.py          # expansión de término para búsqueda            ✗ Fase 4, no existe
  normalize/
    value_funnel.py    # mapear_valor(conn, spec_def_id, raw) — el embudo ✗ Fase 2/3, no existe
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

## Gotchas de la Fase 1 (para F2-F6, no repetirlos)

- **Imports lazy dentro de funciones no se cazan con un grep anclado a `^`.**
  `validate_dataset` tenía `from . import REGISTRY` *dentro* del cuerpo de la función
  (import diferido, no top-level) — un grep de `^from \.` no lo encuentra porque está
  indentado. Al mover `validation.py` esto rompió 6 tests hasta que se encontró con
  pyflakes + corriendo la suite (no alcanza con revisar los imports de la primera línea
  de cada archivo).
- **`mock.patch("path.viejo.funcion")` no intercepta una llamada interna que ahora vive
  en el módulo nuevo.** Si `A` llama a `B` dentro del mismo módulo (`seed_all_categorias`
  → `seed_categoria_from_registry`, ambas en `commands/seed.py`), un patch apuntando al
  shim (`seeds.registry_seeder.seed_categoria_from_registry`) solo reemplaza el atributo
  del shim — la llamada real se resuelve contra los globals de `commands/seed.py`, no del
  shim. Los tests que mockeaban una llamada *interna* tuvieron que actualizar el path del
  `patch(...)` al módulo nuevo (`tests/test_seeder_resiliente.py`). Los shims garantizan
  que los *imports* resuelvan, no que un `mock.patch` de una llamada interna siga
  interceptando — para eso hay que patchear donde la función CALLER vive ahora.

## Qué NO hacer

- No agregar lógica nueva de specs en `routes/specs/*.py` — pasa a `commands/`/`queries/`
  a medida que cada fase las mueve.
- No inventar un segundo mecanismo de normalización de valores en paralelo al embudo
  (`normalize/value_funnel.py`) cuando exista.
- No mover el motor de compatibilidad ni reescribir el seeder "ya que estamos" — no lo
  pide ningún objetivo de la iniciativa; es exactamente el riesgo que el plan evitó a
  propósito.
