# Plan — Rediseño del módulo `specs` (iniciativa)

> **Estado:** plan **aprobado por el dueño** (2026-07-01), **F0-F6 implementadas** (ver tabla de
> fases abajo). Documento de trabajo / hoja de ruta — el _porqué_ y el _cómo_; el detalle de qué
> se hizo en cada fase vive en el issue de tracking [#1163](https://github.com/tixenre/rental/issues/1163)
> y en `services/specs/CLAUDE.md`. Queda pendiente el rediseño de **categorías** (compartir hijas
> entre ramas), deliberadamente diferido — ver "Decisiones del dueño" abajo.
>
> **Origen:** decidido tras un pase de diseño (mapeo del código real → 3 arquitecturas → juicio → síntesis)
> y una conversación de diseño con el dueño. Las decisiones acordadas están abajo.

## Objetivo

`specs` = **fuente única de datos del equipo**: ficha técnica + faceta de filtro + **búsqueda de texto
derivada en vivo** + **fundación sólida del sistema de compatibilidad** (feature futuro que se basará en
esta data → tiene que estar sólida _antes_). De paso: reorganizar a **CQRS-lite** (como
`services/categorias/`), agregar el **embudo de alias de valor**, y **desenredar** specs de la taxonomía
de categorías.

## Veredicto: STRANGLER-refactor en el lugar, NO rewrite paralelo

La intuición "módulo nuevo + viejo legacy" es **mitad correcta**:

- ✅ **Para el CÓDIGO:** sí se crea un paquete nuevo `backend/services/specs/` (CQRS-lite), y lo viejo
  queda con shims `⏰ LEGACY` hasta el swap.
- ❌ **Para los DATOS:** **no** corren dos modelos en paralelo. El modelo de datos actual está **sano** y
  todo lo nuevo es **aditivo**. No existe ninguna _forcing function_ que justifique el riesgo de un
  rewrite paralelo (doble mantenimiento + big-bang de swap, para cero ganancia). Va contra "el core que
  anda no se toca; lo nuevo se acopla alrededor".

**Fundamento (verificado contra el código):**
- Único write-gate de valores: `services/spec_persist.py::persistir_specs` → un solo choke-point donde el
  embudo normaliza al persistir → `equipo_specs.value` queda siempre canónico.
- El motor de compat matchea por igualdad de string ya persistido (`compatibilidad.py` L372) + jerarquía
  por `enum_opts.index` → el embudo lo **alimenta** sin tocar una línea ('FF' y 'Full-frame' dejan de
  divergir porque nunca se persiste 'FF').
- `_check_value` (validation) hoy **solo rechaza**, no normaliza → el embudo es un hueco **real y 100%
  aditivo**.
- La búsqueda no toca specs hoy → derivarla es **una expresión escalar más** (patrón `_FICHA_EXPR` ya en
  prod), cero cambio de esquema.
- El desenredo categorías↔specs es **código muerto**: el seeder ya neutralizó la creación del árbol.

## Modelo de datos objetivo

**Se conserva verbatim** (no se re-serializa ningún valor, no cambian PKs ni FKs): `spec_definitions`
(flags de presentación + flags de compat `es_compatibilidad`/`compatibilidad_modo`/`rol_compatibilidad` +
`enum_options` + `aliases` de concepto), `equipo_specs` (PK `(equipo_id, spec_def_id)`, `value TEXT`),
`categoria_spec_templates`, `spec_familia_jerarquia`, `unidades`, `equipo_compatibilidad`,
`spec_propuestas_pendientes`.

**Se agrega (100% aditivo, patrón esquema en 2 capas — `init_db()` + Alembic):**

```sql
CREATE TABLE spec_value_aliases (
  spec_def_id    INT  NOT NULL REFERENCES spec_definitions(id) ON DELETE CASCADE,
  alias          TEXT NOT NULL,
  valor_canonico TEXT NOT NULL,
  PRIMARY KEY (spec_def_id, alias)
);
CREATE INDEX idx_value_alias_canon ON spec_value_aliases(spec_def_id, valor_canonico);
```

**Tabla, no columna JSONB** (decisión consciente): el embudo se consulta en dos direcciones (alias→canónico
al persistir; canónico→[alias] al buscar) → una tabla indexable en ambas gana, y la curación crece
por-fila desde la cola de propuestas IA + el admin. `enum_options` = lista CERRADA de canónicos;
`spec_value_aliases` = los sinónimos que apuntan a esos canónicos (nunca mezclados). El registry Pydantic
(`SpecDef`) gana un campo `value_aliases: dict[str, list[str]]` (single-source declarativa) que el seeder
vuelca con `ON CONFLICT DO UPDATE`; invariante: todo canónico ∈ `enum_options`.

## Estructura CQRS-lite (`backend/services/specs/`)

Espeja `services/categorias/` verbatim en forma: barrel `__init__.py` con `__all__` = contrato; commands
importan de queries, queries nunca de commands; todo recibe `conn`; sin dep FastAPI; `CLAUDE.md` propio.

```
backend/services/specs/
  __init__.py            # barrel público; __all__ es el contrato
  errors.py              # ErrorSpec(400), SpecNoExiste(404), ValorNoCanonico
  CLAUDE.md              # reglas del paquete + qué es canónico
  registry/              # single-source declarativa (mudanza de backend/specs/)
    models.py            #   SpecDef (+ value_aliases nuevo), CategoriaRegistry, Registry
    catalogo/            #   camaras.py … filtros.py — SOLO SpecDefs tras el desenredo
    shared/              #   enums.py, optica/lighting/physical factories
  commands/              # escritura — únicas que mutan
    persist.py           #   persistir_specs (MOVE verbatim) — choke-point del embudo
    coerce.py            #   coerce_and_serialize (MOVE verbatim) + enchufe del embudo
    value_aliases.py     #   NUEVO: CRUD de spec_value_aliases (cola IA + admin)
    seed.py              #   seed_all (MOVE verbatim de registry_seeder.py — NO reescribir)
  queries/               # lectura — nunca mutan
    definitions.py       #   lecturas de spec_definitions (por cat, por id, faceta)
    equipo_specs.py      #   valores por equipo (ficha, filtros)
    validation.py        #   validate_dataset (MOVE) — _check_value mapea vía embudo
    search_source.py     #   NUEVO: proyección specs→texto buscable (expresión escalar)
    aliases.py           #   NUEVO: expansión de término (concepto + valor) para búsqueda
  normalize/
    value_funnel.py      #   NÚCLEO: mapear_valor(conn, spec_def_id, raw) → canónico|None
```

Candado: `test_specs_sql_safety.py` (espeja `test_contenido_sql_safety.py`) prohíbe `FROM
spec_definitions/equipo_specs` nuevo fuera del paquete.

**El seeder se MUEVE verbatim, NO se reescribe** (es la pieza más destructiva: `purge_stale_specs` hace
`DELETE FROM spec_definitions` con CASCADE a `equipo_specs` — reescribir eso por prolijidad es
second-system effect). **El motor de compat NO se mueve** (es lógica de compat, no CRUD): se le da una
puerta de lectura limpia y queda donde está.

## El embudo — una pieza, cuádruple uso

Una tabla curada + un normalizador (`normalize/value_funnel.py::mapear_valor`). La misma función sirve a
las cuatro bocas (la lógica de mapeo nunca se duplica):

`mapear_valor(conn, spec_def_id, raw) -> str | None`: normaliza `raw` (reusando `busqueda/normalizar.py`)
→ si ∈ `enum_options` devuelve el canónico → si no, busca en `spec_value_aliases` → si no matchea, `None`
(fail-open: cae al comportamiento actual).

1. **Normaliza al persistir** — `coerce` antepone `mapear_valor`; como `persistir_specs` es el único
   write-gate, `equipo_specs.value` queda siempre canónico. ('FF'/'35mm' → 'Full-frame'.)
2. **Valida mapeando** en vez de rechazar — `_check_value` llama `mapear_valor` antes de rechazar.
3. **Búsqueda** — `queries/aliases.py` expande el término por aliases de concepto (`IBIS`) y de valor
   (`FF`→Full-frame).
4. **Compatibilidad — cero código nuevo**: el motor opera sobre `value` ya canónico → 'FF' y 'Full-frame'
   guardaron ambos 'Full-frame' y matchean. **El embudo arregla la compat por construcción.**

Reversible: tabla vacía → comportamiento idéntico a hoy. Apagar = vaciar la tabla (data, no código).

## Búsqueda derivada de specs

En vivo, no materializada. `busqueda/` sigue siendo el motor único; specs se suma como **consumidor**:
una expresión escalar `_SPECS_EXPR` (simétrica a `_FICHA_EXPR`) que agrega por equipo los **valores** (ya
canónicos), los **labels**, los **aliases de concepto** y los **aliases de valor**. Se pasa como un campo
más a `construir` → fuzzy (pg_trgm) + unaccent + ranking gratis. En vivo = agregar un spec o un sinónimo
aparece en la búsqueda sin reindexar. Performance: se mide en staging (LABEL before/after); si pesa,
GIN/tsvector con evidencia, no preventivo.

## Desenredo de categorías

De **código, no de datos**. En la DB ya son tablas separadas; el único vínculo (`categoria_raiz_id`, un
id) se conserva. En `specs/categorias/*.py` cada archivo declara hoy tres cosas: (a) categoría navegable,
(b) sub_categorias (Montura E/RF/EF), (c) `specs=[SpecDef]`. (a) y (b) están **funcionalmente muertas** (el
seeder ya no las crea; el árbol lo maneja el dueño a mano). Tras el desenredo, cada archivo declara **solo
`specs=[...]`** anclado a su categoría raíz por nombre. Cero migración de DB.

## Compat-readiness

La fundación ya existe y está sana (flags + `spec_familia_jerarquia` + `equipo_compatibilidad` + motor que
matchea por igualdad/jerarquía/cross-spec). El rediseño la deja lista **sin re-tocarla**: (1) valores
canónicos garantizados por el embudo → deja de fallar por 'FF'≠'Full-frame' y de arriesgar `ValueError` en
`.index()`; (2) puerta de lectura limpia (queries) para que el futuro dev de compat enchufe sin cavar en el
esquema; (3) flags y jerarquía intactos.

## Plan por fases (cada una shippa sola y es reversible)

| Fase | Qué | Estado |
|---|---|---|
| **F0** | Andamiaje `services/specs/` (barrel + errors + CLAUDE.md) | ✅ hecha |
| **F1** | **Move verbatim** (registry/coerce/persist/validation/seeder) + shims `⏰ LEGACY` | ✅ hecha |
| **F2** | Tabla `spec_value_aliases` (`init_db` + Alembic) + `mapear_valor` — **apagado** | ✅ hecha |
| **F3** | Enchufar embudo a las 4 bocas + sembrar enums de compat críticos | ✅ hecha (verificación en staging pendiente — ver issue) |
| **F3.5** | _(opcional)_ pase batch idempotente que re-normaliza `equipo_specs.value` viejos | ⏸ no hecha (opcional, sin necesidad detectada) |
| **F4** | Búsqueda derivada (`_SPECS_EXPR` como campo más) | ✅ hecha (verificación en staging pendiente — ver issue) |
| **F5** | **Eliminar tags/etiquetas** (PR propio + dump previo) | ✅ hecha |
| **F6** | Podar shims `⏰ LEGACY` + desenredo final (sub_categorias/grupo_visual muertos) | ✅ hecha |

## Trade-offs honestos

1. **Ventana muerta al inicio:** F0+F1 son plomería que el dueño no-dev no puede "ver" (plan de prueba =
   "fijate que todo sigue igual"). Es fe, no evidencia. Se mitiga yendo rápido; el gate real es
   CI + supervisor. El primer valor testeable llega en F3.
2. **Tabla vs columna** para el embudo: elegí tabla (un JOIN extra en `_SPECS_EXPR` + un lookup al
   persistir, ambos baratos y fuera del hot-path de lectura) a cambio de la expansión inversa indexada +
   curación por-fila. Única desviación de la base más segura, fundada.
3. **Seeder se mueve, no se reescribe** (rechazo del rebuild por prolijidad — es la pieza que cascadea
   sobre datos reales).
4. **Compat no se mueve** (856 líneas no triviales que ningún objetivo pide mover).
5. **Búsqueda en vivo** puede pesar en catálogos grandes; se mide, no se optimiza preventivamente.
6. **El embudo canonicaliza al persistir:** un `value_aliases` mal curado canonicaliza mal en silencio.
   Mitigación: fail-open, test golden por alias sembrado, la lista de `discarded` expone lo no-mapeado,
   PK impide ambigüedad. Riesgo de curación humana, no eliminable por diseño.

## Decisiones del dueño (2026-07-01)

- ✅ **Aprobado el plan en grande.**
- ✅ **Tags afuera** (F5).
- ✅ **Categorías después** (revisión separada, mismo patrón CQRS-lite, cuando specs esté).
- Pendiente de confirmar en su fase: (1) canonicalización automática al guardar; (2) pase batch F3.5;
  (3) dump de etiquetas manuales antes de borrar; (4) borrar sub_categorias muertas tras grep;
  (5) orden F0-F1-primero vs comprimir para llegar antes al embudo.

## Follow-up (tarea aparte, futura)

**Sistema de ingesta y normalización de specs** — cómo entra la data (scraping/CSV/B&H → normalización →
propuestas). Es una tarea de diseño **separada**, a abordar **cuando este rediseño esté**. Se le hará su
propio plan + issue.

**Extraer compatibilidad a `services/compatibilidad/`** — `routes/specs/compatibilidad.py` (856 líneas)
tiene el motor de matching completo (`_compute_compat` + helpers + cache de familias) puesto directo en
la route, sin pasar por `commands/`/`queries/`, y con **tablas propias** (`equipo_compatibilidad`,
`spec_familia_jerarquia`) que no son de specs. El plan lo dejó afuera a propósito ("no lo pide ningún
objetivo de la iniciativa") — es la continuación natural si se quiere terminar de ordenar el árbol
completo, mismo patrón "motor único" que `services/contenido/` (lee de otro motor, tiene su propia
puerta). `someday`, issue [#1174](https://github.com/tixenre/rental/issues/1174).

## Deuda diferida (issues aparte, NO bloquean)

`unidad` VARCHAR vs `unidad_id` FK (drift de sync); `favorito` vs `destacado` solapados; `multi_enum`
serializado TEXT + `_parse_multi_enum_value` heurístico. Se marcan `⏰ LEGACY`; el embudo reduce la
fragilidad del multi_enum sin re-serializarlo.
