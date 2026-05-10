## Objetivo

Categorías jerárquicas (2 niveles) con:
- Un equipo puede tener N categorías hoja.
- Filtrar por padre incluye automáticamente todos los hijos.
- Ejemplo: Sony a7 V → `Foto` + `Video`. Aparece en ambas y dentro de `Cámaras`.

## Fase 1 — Backend: estructura del árbol

**Migración `etiquetas`:**
- `parent_id INTEGER NULL REFERENCES etiquetas(id) ON DELETE SET NULL`
- Índice `(parent_id, prioridad, nombre)`
- Constraint: `parent_id != id` y el padre no puede tener a su vez `parent_id` (forzar 2 niveles).

**Seed del árbol** (idempotente por nombre):

```text
Cámaras (10)              → Video, Foto, Acción
Lentes (20)               → Zoom E, Zoom EF, Fijos EF, Especiales, Vintage
Adaptadores y Filtros (25)→ Adaptadores, Filtros 82mm
Iluminación (30)          → LED daylight/bicolor, LED RGB, Tungsteno, Fluorescente, On-camera, Práctica/efecto
Modificadores (40)        → Softbox, Difusión, Reflectores, Banderas
Soportes (50)             → Trípodes video, Trípodes foto, C-Stands, Estabilización, Slider/Dolly, Car mount
Grip (60)                 → Brazos, Clamps, Wall plates/pins, Pinzas, Líneas seguridad, Sopapa, Lastre
Sonido (70)               → Inalámbricos, Shotgun/Boom, On-camera, Estudio/Podcast, Intercom
Monitores y Video (80)    → Monitores, Grabadores, Transmisión, Follow Focus/Matebox
Energía (90)              → V-Mount, NP/LP-E6, Distribución
Media y Datos (100)       → SD, CFexpress, Lectores
Estudio y Producción (110)→ Set/Backdrops, Paquetes
```

**Endpoints (`backend/routes/equipos.py`):**
- `GET /api/categorias` → árbol `[{id, nombre, prioridad, children:[...]}]`. `?flat=1` para retrocompat.
- `GET /api/equipos?categoria=<id>` → CTE recursiva: matchea si el equipo está asignado a esa etiqueta o a cualquier descendiente.
- `GET /api/admin/etiquetas` → incluye `parent_id`.
- `POST /api/admin/etiquetas` y `PATCH /api/admin/etiquetas/{id}` → aceptan `parent_id` (validar 2 niveles + no-ciclo).
- `PUT /api/admin/equipos/{id}/etiquetas` → reemplaza la lista completa de etiquetas hoja del equipo.

## Fase 2 — Clasificación con revisión previa

**Script `backend/scripts/seed_categorias.py`:**
1. Crea/actualiza el árbol de etiquetas.
2. Recorre los 142 equipos y aplica reglas de nombre/marca/modelo → set de etiquetas hoja propuesto.
3. Genera `/mnt/documents/clasificacion_propuesta.csv` con columnas: `id, nombre, marca, etiquetas_propuestas, notas`.
4. **No escribe asignaciones todavía.** Vos revisás el CSV.
5. Segundo paso (`--apply` o un endpoint admin) que toma el CSV revisado y ejecuta las asignaciones.

Casos especiales pre-cargados:
- Sony a7 V, ZV-E1 → `Foto` + `Video`.
- FX3, RED, C200 → `Video`.
- GoPro, Insta360 → `Acción`.

## Fase 3 — Frontend: tipos y hooks

**`src/lib/api.ts` y `src/lib/admin/api.ts`:**
- `Categoria` gana `parent_id?: number | null` y `children?: Categoria[]`.
- Helpers: `flattenCategorias(tree)`, `descendantIds(tree, id)`, `getParent(byId, cat)`.

**`src/hooks/useEquipos.ts`:**
- `useCategorias()` devuelve `{ tree, flat, byId }`.

## Fase 4 — UI catálogo público (recomendación)

**Recomiendo: chips expandibles con drawer en mobile.**

Razón: en 402px un dropdown jerárquico se siente desconectado del contenido y obliga a 2 taps para volver a ver opciones. Los chips expandibles muestran el contexto completo sin abrir/cerrar menús, y ya tenés el lenguaje visual de chips en el catálogo.

**Implementación:**
- Fila horizontal scrollable de chips de **nivel padre** (Cámaras, Lentes, Iluminación…).
- Tap en padre → activa filtro padre **y** revela una segunda fila debajo con sus hijos (Foto, Video, Acción).
- Tap en hijo → filtro más fino. Tap de nuevo en el padre → vuelve al filtro padre. "Todos" limpia.
- Indicador visual: padre activo en sólido, hijo activo con ring, padres inactivos con borde.
- En desktop la segunda fila aparece inline; en mobile colapsada en un chip "▾ subcategorías" si supera el ancho.

## Fase 5 — Sheet de pedidos

`EquipoSearchSheet` en `PedidoPage.tsx`:
- Agrupa por **categoría hoja**, con encabezado de padre arriba (sticky de 2 niveles).
- Equipos con varias hojas aparecen en cada grupo correspondiente (con stock compartido — la disponibilidad sigue siendo por equipo).

## Fase 6 — Admin

**`/admin/settings` — Sección Categorías (árbol):**
- Vista indentada con expand/collapse por padre.
- Acciones por nodo: agregar hijo, renombrar, mover (cambiar `parent_id`), reordenar (▲▼ + input prioridad), borrar.
- Botón "Guardar orden" hace bulk reorder por nivel.

**`/admin/equipos` — Editor de etiquetas por equipo:**
- En la fila/detalle de cada equipo, multi-select de etiquetas **hoja** (los padres se infieren).
- Mostrar chips de las etiquetas asignadas con el padre como prefijo (ej: `Cámaras · Foto`).
- Guardar llama a `PUT /api/admin/equipos/{id}/etiquetas`.

## Orden de entrega sugerido

1. Migración + seed del árbol (sin asignar equipos aún).
2. Endpoints actualizados (`categorias` árbol, `equipos` con filtro recursivo).
3. Tipos/hook frontend + catálogo con chips expandibles.
4. Script de clasificación → CSV de revisión → vos confirmás → aplicar.
5. Editor de etiquetas en `/admin/equipos` y editor de árbol en `/admin/settings`.
6. Sheet de pedidos con agrupado de 2 niveles.
