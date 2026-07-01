# `services/specs/` — motor de specs (en construcción, Fase 4 hecha)

> **Estado de las 4 bocas del embudo: 3 activas, 1 diferida a propósito.**
> `registry/`, `queries/{validation,search_source}.py` y `commands/{coerce,persist,seed}.py`
> son código real, movido verbatim desde los paths viejos (shims ⏰ LEGACY hasta la
> **Fase 6**).
>
> - **Persistir** ✅ — `commands/persist.py::persistir_specs` (el choke-point real, el
>   mismo que llama `PUT /admin/equipos/{id}/specs`) prueba `mapear_valor` para
>   `tipo="enum"` antes de la coerción vieja (fail-open).
> - **Compat** ✅ — gratis, sin código: viene de que persistir ahora guarda canónico.
> - **Buscar** ✅ — `queries/search_source.py::specs_search_expr()` es un campo más de
>   `busqueda.construir` en `routes/equipos/core.py::CAMPOS_EQUIPO`. En vivo, no
>   materializada (mismo patrón que `_FICHA_EXPR`, sin índice — medir en staging si pesa).
> - **Validar** ❌ diferida — `queries/validation.py::validate_dataset` no tiene ningún
>   llamador en vivo (solo un test que lintea fixtures, sin `conn`); forzarle DB-coupling
>   para cero consumidores reales es más cambio de diseño del que pide esta iniciativa.
>   Se retoma si/cuando tenga un caller real.
>
> `formato` (Cámaras y Lentes) tiene `value_aliases` reales sembrados
> (`FF`→Full-frame, `S35`→Super 35) — el resto del catálogo sigue sin curar (tarea
> aparte, de criterio del dueño). `queries/aliases.py` (expansión de término, un
> refinamiento sobre lo que `search_source.py` ya cubre) sigue sin existir — no bloqueaba
> tener algo real para probar. Plan completo + fases →
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
  __init__.py      # barrel público. __all__ es el contrato real.        ✓ Fase 1
  errors.py        # ErrorSpec (400), SpecNoExiste (404), ValorNoCanonico (400)  ✓ Fase 0
  registry/        # SpecDef, CategoriaRegistry — mudanza de backend/specs/     ✓ Fase 1
    models.py
    catalogo/      #   camaras/lentes/iluminacion/modificadores/adaptadores/filtros
    shared/        #   enums/lighting/optica/physical
  commands/        # escritura — única puerta de mutación
    persist.py     #   persistir_specs — LLAMA a mapear_valor para enum    ✓ Fase 3
    coerce.py      #   coerce_and_serialize — fallback si el embudo no matchea  ✓ Fase 1
    seed.py        #   seed_all_categorias + _sync_value_aliases           ✓ Fase 1+2
    value_aliases.py  # CRUD ad-hoc de spec_value_aliases (admin/cola IA) ✗ no existe, sin fase asignada
  queries/         # lectura — nunca mutan
    validation.py     # validate_dataset — SIN enchufar (sin conn, sin caller vivo)  ✓ Fase 1
    search_source.py  # specs_search_expr() — campo más de CAMPOS_EQUIPO           ✓ Fase 4
    definitions.py     # ✗ no existe — mapear_valor hace su propia lectura de spec_definitions
    equipo_specs.py    # ✗ Fase futura, no existe
    aliases.py          # expansión de término (refinamiento; search_source.py ya cubre lo básico) ✗ no existe, sin fase asignada
  normalize/
    value_funnel.py    # mapear_valor(conn, spec_def_id, raw) — EXISTE, llamado desde persist.py  ✓ Fase 2+3
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

## Gotchas de la Fase 3

- **`enum_options` no siempre llega como lista Python.** En Postgres real (JSONB) el
  driver lo auto-decodea a `list`; en fakes de test (SQLite, `enum_options TEXT`) llega
  como JSON string crudo. `coerce_and_serialize` ya lo manejaba (`_parse_opts`);
  `mapear_valor` al principio NO — asumía lista y hubiera iterado caracter por caracter de
  un string sin explotar (resultado silenciosamente mal, no un error visible). Se arregló
  reusando `_parse_opts` (mismo parseo, no uno segundo) — `normalize/` SÍ puede importar
  de `commands/` para esto (no es un ciclo: `commands/coerce.py` no importa de `normalize/`).
- **Los mocks de schema hecho-a-mano (`tests/test_persistir_specs_6a.py`, SQLite
  in-memory) no tienen las tablas nuevas.** Enchufar el embudo en `persistir_specs` hizo
  que ese test explotara con `no such table: spec_value_aliases` — el fake schema de ese
  archivo se arma a mano (no corre `init_db()`), así que toda tabla nueva que un choke-point
  empiece a consultar hay que agregarla ahí también. Buscar `CREATE TABLE spec_definitions`
  en `tests/*.py` antes de tocar un choke-point, para encontrar estos fakes.

## Gotchas de la Fase 4

- **`seed_categoria_from_registry(conn, nombre, ...)` necesita que `nombre` matchee EXACTO
  una categoría que ya existe en la DB** — el seeder solo resuelve, nunca crea (ver
  `_ensure_categoria_raiz`). Un test que ancla sus datos con un nombre sintético
  (`"ZZ-Algo-test"`, para no chocar con datos reales — convención de los `*_db.py`) y
  después llama al seeder pidiendo `"Cámaras"` falla en silencio: `raiz_id=None`, no
  crea ningún spec, y el fetch de `spec_def_id` de ese test explota con
  `NoneType is not subscriptable`. Para tests de specs que no necesitan el catálogo REAL
  (solo necesitan *algún* spec enum con aliases), construir uno sintético directo con
  `_upsert_spec_definition` + `_sync_value_aliases` bajo la categoría-ancla — no depender
  del seeder + nombre real (`test_specs_search_source_db.py`, `test_specs_value_aliases_db.py`).

## Qué NO hacer

- No agregar lógica nueva de specs en `routes/specs/*.py` — pasa a `commands/`/`queries/`
  a medida que cada fase las mueve.
- No inventar un segundo mecanismo de normalización de valores en paralelo al embudo
  (`normalize/value_funnel.py`) — ya existe, úsalo.
- No hacer una pasada de curación amplia de `value_aliases` como parte de trabajo de
  infraestructura — eso es tarea aparte, de criterio del dueño. Sí está bien sembrar un
  puñado mínimo, bien justificado (abreviaturas de uso real conocido, no adivinadas) al
  enchufar una boca nueva, para tener algo concreto que probar — como `formato` en
  Fase 3 (`FF`/`S35`). La curación real y amplia sigue pendiente.
- No mover el motor de compatibilidad ni reescribir el seeder "ya que estamos" — no lo
  pide ningún objetivo de la iniciativa; es exactamente el riesgo que el plan evitó a
  propósito.
