# `services/specs/` — motor de specs (rediseño F0-F6 completo; categorías queda aparte)

> **Estado de las 4 bocas del embudo: 3 activas, 1 diferida a propósito.**
> `registry/`, `queries/{validation,search_source}.py` y `commands/{coerce,persist,seed}.py`
> son código real. Los 18 shims `⏰ LEGACY` de la Fase 1 (paths viejos `backend/specs/`,
> `services/spec_coerce.py`, `spec_persist.py`, `seeds/registry_seeder.py`) se **podaron
> en la Fase 6** — este paquete es la única ubicación, no quedan re-exports.
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
> tener algo real para probar.
>
> **Canal C aditivo desde `specs_ingesta` (2026-07, F7 de ese módulo, no una fase propia
> de éste):** `commands/propuestas.py` + `queries/propuestas.py` cablean la cola
> `spec_propuestas_pendientes` que existía huérfana en el schema (creada para el skill
> `gear-compatibility`, que nunca le escribió). `specs_ingesta.commands.proponer` es el
> primer productor real. Verificado contra Postgres real: INSERT+RETURNING, JSONB
> auto-decodifica a dict al leer, `aplicar_propuesta`/`descartar_propuesta` sacan el ítem
> de pendientes, el CHECK constraint de `tipo` rechaza valores inválidos. Regla dura:
> **nunca muta el registry** — `aplicar_propuesta` solo cierra el ítem de la cola después
> de que el humano ya editó el registry a mano (código = fuente única) y re-sembró.
>
> **`queries/equipo_specs.py::get_equipo_specs_rows`** (2026-07, aditivo, no una fase propia):
> query único del JOIN equipo_specs+spec_definitions+categoria_spec_templates para "specs ya
> persistidas de un lote de equipos" — antes vivía duplicado inline en `database/equipos.py`
> (`attach_specs_estructuradas` para la ficha pública, `attach_specs_destacados` para los
> quick facts de card), cada uno con su propio SQL contra las mismas 3 tablas. Devuelve rows
> crudos; cada caller sigue decidiendo su propia política de display (bool=false se omite en
> la ficha, se muestra "No" explícito en el preview pre-persist de `specs_ingesta`, es un
> checkbox en el form admin — 3 audiencias, 3 decisiones de UX legítimas, NO drift). Lo que
> estaba mal no era la política, era el query duplicado — encontrado auditando por qué un
> bool=false se trataba "distinto en cada lugar" tras cargar specs reales (Iniciativa A).
> **2026-07-04:** consolidar el SQL en una función no alcanzaba — `proyectar_lista`
> (`services/catalogo/proyeccion.py`) seguía llamando `attach_specs_estructuradas` Y
> `attach_specs_destacados` por separado, cada una pidiendo `get_equipo_specs_rows` de
> nuevo para el mismo lote de ids (2 ejecuciones del JOIN por carga de catálogo). Ambas
> funciones ahora aceptan `rows_by_equipo` opcional; `proyectar_lista` lo pide una sola
> vez y se lo pasa a las dos. Encontrado investigando un reporte de "la búsqueda de
> equipos se siente lenta" (la causa real era la carga inicial del catálogo, no la
> búsqueda en sí).
>
> **`CategoriaRegistry` ya no declara navegación** (Fase 6, desenredo categorías↔specs):
> solo `nombre` (ancla a una categoría real por nombre) + `specs`. `sub_categorias`/
> `grupo_visual`/`prioridad` a nivel categoría se sacaron — eran parámetros que el
> seeder aceptaba pero nunca escribía (`_ensure_categoria_raiz`/`_ensure_subcategoria`
> solo resolvían por nombre, nunca creaban ni actualizaban nada con esos valores). El
> árbol del catálogo lo maneja el dueño 100% a mano desde `/admin/categorias`.
>
> Plan completo + fases → [`docs/PLAN_SPECS_REDISENO.md`](../../../docs/PLAN_SPECS_REDISENO.md)
> · tracking → issue [#1163](https://github.com/tixenre/rental/issues/1163).

## Por qué existe (antes de tener código)

Es un **strangler-refactor en el lugar**, no un rewrite paralelo: el modelo de datos
(`spec_definitions` + `equipo_specs`) está sano y se conserva verbatim. Lo que cambia es
la organización del código (a CQRS-lite, espejo de `services/categorias/`) y se agrega,
100% aditivo, el **embudo de alias de valor** (normaliza/valida/busca/compat con una sola
pieza) + la **búsqueda derivada de specs** en vivo.

## Estructura actual (F0-F6 completas; lo que sigue sin fase asignada)

```
services/specs/
  __init__.py      # barrel público. __all__ es el contrato real.        ✓ Fase 1
  errors.py        # ErrorSpec (400), SpecNoExiste (404), ValorNoCanonico (400)  ✓ Fase 0
  registry/        # SpecDef, CategoriaRegistry — mudanza de backend/specs/     ✓ Fase 1
    models.py      #   CategoriaRegistry: solo nombre + specs (desenredada, Fase 6)
    catalogo/      #   camaras/lentes/iluminacion/modificadores/adaptadores/filtros
    shared/        #   enums/lighting/optica/physical
  commands/        # escritura — única puerta de mutación
    persist.py     #   persistir_specs — LLAMA a mapear_valor para enum    ✓ Fase 3
    coerce.py      #   coerce_and_serialize — fallback si el embudo no matchea  ✓ Fase 1
    seed.py        #   seed_all_categorias — solo raíz + specs + templates ✓ Fase 1+2+6
    propuestas.py  #   Canal C: encolar/aplicar/descartar_propuesta (spec_propuestas_pendientes) ✓ aditivo 2026-07
    value_aliases.py  # CRUD ad-hoc de spec_value_aliases (admin) ✗ no existe, sin fase asignada — NO confundir con propuestas.py (spec_value_aliases es la tabla de aliases YA curados; spec_propuestas_pendientes es la cola de candidatos sin revisar)
  queries/         # lectura — nunca mutan
    validation.py     # validate_dataset — SIN enchufar (sin conn, sin caller vivo)  ✓ Fase 1
    search_source.py  # specs_search_expr() — campo más de CAMPOS_EQUIPO           ✓ Fase 4
    propuestas.py      # listar_propuestas_pendientes — Canal C                    ✓ aditivo 2026-07
    definitions.py     # ✗ no existe — mapear_valor hace su propia lectura de spec_definitions
    equipo_specs.py    # get_equipo_specs_rows (specs persistidas de un lote) + specs_en_nombre_de_equipo (specs en_nombre para el nombre público, vía categoria_specs) ✓ aditivo 2026-07
    aliases.py          # expansión de término (refinamiento; search_source.py ya cubre lo básico) ✗ no existe, sin fase asignada
  normalize/
    value_funnel.py    # mapear_valor(conn, spec_def_id, raw) — EXISTE, llamado desde persist.py  ✓ Fase 2+3
```

No hay `services/specs/registry/models.py::SubCategoria` — se borró en Fase 6 junto
con el campo `sub_categorias` (nadie más lo usaba).

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

## Gotchas de la Fase 6

- **Un parámetro que una función acepta no significa que lo use.**
  `_ensure_categoria_raiz(conn, nombre, prioridad, grupo_visual, dry_run)` recibía
  `prioridad`/`grupo_visual` desde `seed_categoria_from_registry`, pero el cuerpo de la
  función era literalmente `return buscar_id_por_nombre(conn, nombre)` — los ignoraba
  por completo (la categoría "ya NO se crea", solo se resuelve). Mismo patrón en
  `_ensure_subcategoria`. El desenredo se confirmó leyendo el CUERPO de la función, no
  solo su firma — una firma con parámetros no es evidencia de que se usen.
- **Podar 18 shims con imports repetidos en el mismo archivo → `Edit` con
  `replace_all` cuando la indentación es idéntica.** La mayoría de los ~50 imports a
  reescribir eran la misma línea (`from specs import REGISTRY`) repetida dentro de
  varias funciones de test con la misma indentación (4 espacios) — un `replace_all`
  por línea-exacta fue seguro y mucho más rápido que editar cada ocurrencia. Cuando la
  indentación variaba (nivel de función vs. dentro de un `with`), se verificó cada
  bloque con `Read` antes de decidir si el `replace_all` era seguro.
- **El shim de `seeds/registry_seeder.py` re-exportaba `REGISTRY`/`CategoriaRegistry`/
  `SpecDef` además de las funciones del seeder** (documentado en su propio docstring:
  "porque `tests/test_seeder_resiliente.py` hace `from seeds.registry_seeder import
  seed_all_categorias, REGISTRY`"). Al podarlo, esos 3 nombres se resuelven contra el
  barrel (`from services.specs import ...`), no contra `commands/seed.py` — confundir
  el nuevo home de cada símbolo con el del shim que lo re-exportaba rompe el import.

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
