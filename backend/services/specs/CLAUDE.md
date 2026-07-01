# `services/specs/` — motor de specs (en construcción, Fase 2 hecha)

> **Estado: registry + persistencia movidos, el embudo EXISTE pero está APAGADO.**
> `registry/`, `queries/validation.py` y `commands/{coerce,persist,seed}.py` son código
> real, movido verbatim desde `backend/specs/`, `backend/services/spec_coerce.py`,
> `backend/services/spec_persist.py` y `backend/seeds/registry_seeder.py` (paths viejos =
> shims ⏰ LEGACY hasta la **Fase 6**). La tabla `spec_value_aliases` y
> `normalize/value_funnel.py::mapear_valor` ya existen y funcionan (Fase 2) — pero
> **nadie los llama todavía**: `commands/coerce.py` y `queries/validation.py` no invocan
> `mapear_valor`. Eso es la **Fase 3** ("enchufar el embudo a las 4 bocas"). Hoy
> `spec_value_aliases` nace vacía (ningún `SpecDef` del catálogo declara `value_aliases`
> real todavía — la curación de qué alias vale la pena es trabajo aparte, no de esta
> fase). Plan completo + fases → [`docs/PLAN_SPECS_REDISENO.md`](../../../docs/PLAN_SPECS_REDISENO.md)
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
    persist.py     #   persistir_specs — todavía NO llama al embudo      ✓ Fase 1 (mudado)
    coerce.py      #   coerce_and_serialize — todavía NO llama al embudo ✓ Fase 1 (mudado)
    seed.py        #   seed_all_categorias + _sync_value_aliases         ✓ Fase 1+2
    value_aliases.py  # CRUD ad-hoc de spec_value_aliases (admin/cola IA) ✗ no existe, sin fase asignada
  queries/         # lectura — nunca mutan
    validation.py  #   validate_dataset — _check_value todavía NO llama al embudo (Fase 3)  ✓ Fase 1
    definitions.py     # ✗ no existe — mapear_valor hace su propia lectura de spec_definitions
    equipo_specs.py    # ✗ Fase futura, no existe
    search_source.py   # proyección specs→texto buscable                ✗ Fase 4, no existe
    aliases.py          # expansión de término para búsqueda            ✗ Fase 4, no existe
  normalize/
    value_funnel.py    # mapear_valor(conn, spec_def_id, raw) — EXISTE, funciona, nadie lo llama todavía  ✓ Fase 2
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
- **`mapear_valor` compara SIEMPRE vía `busqueda.normalizar.normalizar`, en los dos
  lados** (el `raw` de entrada Y cada canónico/alias leído de la DB) — nunca se
  reimplementa el "sin acentos/case-insensitive" en SQL. Es la misma fuente única que ya
  usa el motor de búsqueda (`backend/busqueda/`, decisión 2026-06-06); un segundo
  normalizador en paralelo es el tipo de drift que esa decisión evitó.
- `SpecDef.value_aliases` (Python) solo declara — **el seeder es quien escribe**
  `spec_value_aliases` (`commands/seed.py::_sync_value_aliases`, llamado desde
  `seed_categoria_from_registry` tras `_upsert_spec_definition`). Si agregás
  `value_aliases` a un `SpecDef` y no corre el seeder, la tabla no se entera — mismo
  gotcha que `categorias.total` en el módulo categorias (campo declarado sin writer).

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
  (`normalize/value_funnel.py`) — ya existe, úsalo.
- No cargar `value_aliases` "reales" en el catálogo (`registry/catalogo/*.py`) como parte
  de trabajo de infraestructura — la curación (qué sinónimos vale la pena declarar) es
  una tarea aparte, de criterio del dueño, no algo que se decide de paso.
- No mover el motor de compatibilidad ni reescribir el seeder "ya que estamos" — no lo
  pide ningún objetivo de la iniciativa; es exactamente el riesgo que el plan evitó a
  propósito.
