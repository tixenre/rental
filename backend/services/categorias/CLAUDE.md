# `services/categorias/` — categorías tree management

Single source of truth for category rules, validation, and tree traversal.
The module is split into **commands** (writes) and **queries** (reads).

## Structure

```
services/categorias/
  __init__.py      # Barrel público. __all__ es el contrato real — si algo no
                    # está ahí, es interno del paquete (ver su docstring).
  errors.py        # Typed exceptions: ErrorValidacion (400), CategoriaNoExiste
                    # (404, hereda de ErrorValidacion), NombreDuplicado (409).
  commands/
    crud.py        # create/update/delete/reorder de la categoría en sí +
                    # helpers de seed (crear_si_no_existe, asignar_padre_si_no_tiene)
    assignment.py  # set/add/remove/copy categorías EN equipos (equipo_categorias)
  queries/
    ancestry.py    # traversal (ancestros/descendientes/root) + lecturas de
                    # equipo↔categoria: categoria_ids_de_equipo (1 equipo, solo
                    # IDs) y categorias_de_equipos (batch, objeto completo) —
                    # viven juntas acá, no las separes por singular/plural.
    read.py        # Lookups directos sobre `categorias` sola (id/nombre), sin
                    # join a equipo_categorias y sin traversal.
    tree.py         # árbol completo para catálogo público + admin (total en vivo)
    audit.py        # reportes agregados: equipos_sin_categoria, categorias_sin_equipos
    validation.py   # profundidad máxima (3 niveles), ciclos, nombre único
```

## Rules

- **Commands** are the only way to mutate category data.
- **Queries** never mutate data — they only read and return.
- Commands import from queries as needed (e.g. `validar_existe`). Queries never import from commands.
- No FastAPI dependency: all functions receive `conn`. Auth (`require_admin`) es
  responsabilidad de la ruta que llama, no del módulo — todo call-site que muta
  vive hoy detrás de `require_admin` (verificado); si agregás una ruta nueva que
  llame a `commands/`, no te olvides del guard.

## What NOT to do

- No category CRUD in route files without going through `commands/`.
- No category tree/lookup reads in route files without going through `queries/`.
- Simple category reads/lookups no van con SQL inline en otro módulo — pero
  reports que cruzan categorías con OTRO dominio (specs, pedidos, ranking) sí
  pueden hacer su propio JOIN contra `equipo_categorias`/`categorias` cuando el
  query es específico de ese report (ver `ranking_service.py`,
  `routes/specs/compatibilidad.py`, `routes/specs/diagnostico.py`,
  `routes/alquileres/documentos.py` — todos ya usan el módulo para lo genérico
  y joinean directo solo para su agregación puntual). La regla es "no
  reimplementes CRUD/lookup de categorías en otro lado", no "cero SQL que
  mencione la tabla".

## Comportamientos no obvios (leer antes de tocar)

- **`eliminar()` rechaza borrar una categoría con sub-categorías.**
  `categorias.parent_id` es `ON DELETE SET NULL` — sin este guard, borrar un
  padre huerfanaría sus hijas a raíz en silencio. Reasigná o borrá las hijas
  primero.
- **`reordenar()` dedupea ids repetidos** (gana la primera aparición) y valida
  existencia en un solo `WHERE id = ANY(%s)` antes de escribir — 2 round-trips,
  no 2N.
- **Las funciones `_masivo` de `assignment.py` son no-op con `equipo_ids=[]`**
  (evitan el `IN ()` inválido), no lanzan. `set_categoria_masivo` /
  `add_categoria_masivo` sí validan `categoria_id` aunque la lista esté vacía.
- **`categorias.total` (columna, no la clave del dict) no la escribe nadie.**
  Quedó de #131 (ranking) pero `actualizar_ranking` nunca la toca — siempre da
  0. `queries/read.py::listar_categorias_flat` la expone tal cual (documentado
  ahí); si necesitás un conteo real, usar `queries/tree.py::listar_arbol_admin`
  (JOIN en vivo).
- **`categorias_sin_equipos` (audit.py) no tiene consumidor todavía.** Reservada
  para la feature de completitud de catálogo (skill `catalogo`) — no es código
  muerto, no la borres por falta de caller.
- **`asignar_categorias()` diffea contra el estado actual antes de escribir**
  (no DELETE+INSERT incondicional): el form de equipo la llama en cada save,
  aunque no se haya tocado la sección de categorías, y un reemplazo ciego
  generaba dead rows en `equipo_categorias` (+ un UPDATE de más en
  `equipos.nombre_publico` vía `actualizar_nombres_de`) en cada guardado sin
  cambios reales. Si el set y el orden no cambiaron, es un no-op total. No
  reintroducir el DELETE-completo — `set_categoria_masivo` sí lo hace a
  propósito (es un reemplazo masivo explícito, no un save incidental).
