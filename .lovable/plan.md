## Objetivo

Mostrar los equipos agrupados por categoría dentro del sheet "Agregar equipo" del editor de pedidos, ordenando las categorías por una **prioridad** definida en el backend (reutilizable también en el catálogo público y en cualquier listado futuro).

## Modelo de datos (FastAPI / Postgres)

La tabla `etiquetas` ya existe `(id, nombre)`. Le agregamos:

```text
prioridad INTEGER NOT NULL DEFAULT 100
```

- Menor número = más arriba.
- Default 100 para que las nuevas categorías queden al final hasta que alguien les fije prioridad.
- Se aplica **a todas las etiquetas**, no solo a las "categoría principal" (orden=0). En la práctica el orden lo usa quien agrupe por categoría principal; otros usos (filtros por subtag) podrán reutilizarlo.

### Seed inicial (orden pedido por el usuario)

| Prioridad | Categoría |
|----:|---|
| 10 | Cámaras |
| 20 | Lentes |
| 30 | Luces |
| 40 | Modificadores |
| 50 | Soportes / Trípode |
| 60 | Grips / Griperia |
| 70 | Sonido |
| 80 | Monitores |
| 90 | Baterías |
| 100 | (resto) |

Los nombres exactos se mapean contra los que ya existen en `etiquetas`. Lo que no matchee queda en 100 y se puede ajustar luego desde la UI.

## Backend (`backend/`)

1. **Migración** (en `database.py` initialización idempotente):
   - `ALTER TABLE etiquetas ADD COLUMN IF NOT EXISTS prioridad INTEGER NOT NULL DEFAULT 100`
   - `CREATE INDEX IF NOT EXISTS idx_etiq_prioridad ON etiquetas(prioridad, nombre)`

2. **Seed** (one-shot al arrancar, solo para etiquetas con `prioridad = 100` y nombre conocido) — así no pisa cambios manuales del usuario.

3. **`GET /api/categorias`**: incluir `prioridad` en cada item y ordenar `ORDER BY et.prioridad ASC, et.nombre ASC` en lugar de alfabético.

4. **`GET /api/equipos`**: incluir `prioridad` en cada etiqueta devuelta (hoy devuelve solo el nombre).

5. **Nuevos endpoints admin** (protegidos con `require_admin`):
   - `GET  /api/admin/etiquetas` → lista `[{ id, nombre, prioridad, total }]` ordenada por prioridad.
   - `PATCH /api/admin/etiquetas/{id}` → body `{ prioridad?: int, nombre?: string }`.
   - (Opcional ahora, recomendado) `POST /api/admin/etiquetas/reorder` → body `{ ids: number[] }` que setea prioridad = 10, 20, 30… según el orden recibido (más práctico para drag-and-drop).

## Frontend

### `src/lib/admin/api.ts`
- Tipo `Etiqueta = { id; nombre; prioridad; total? }`.
- `adminApi.listEtiquetas()`, `adminApi.updateEtiqueta(id, patch)`, `adminApi.reorderEtiquetas(ids)`.
- Extender `Categoria` (respuesta de `/api/categorias`) con `prioridad`.

### `/admin/settings` — nueva sección "Categorías"
Pantalla simple, encima de "Importar CSV":

- Lista vertical de categorías con: nombre, contador de equipos, input numérico de prioridad y handle de drag (`@dnd-kit/sortable`, ya disponible vía shadcn pattern; si no, usamos botones ▲▼ para no agregar dependencia).
- "Guardar orden" → `reorderEtiquetas([ids])` → toast + invalidar `["categorias"]` y `["admin","etiquetas"]`.
- Edición inline de prioridad numérica con `onBlur` → `updateEtiqueta`.

Decisión de diseño: arrancamos con **botones ▲▼ + input numérico** (sin nueva dependencia). Si después se siente lento, sumamos drag-and-drop.

### Sheet de pedidos (`EquipoSearchSheet` en `PedidoPage.tsx`)
- Pedir `useQuery(["categorias"])` para obtener orden y prioridad.
- Helper `categoriaPrincipal(eq)` = `eq.etiquetas?.[0] ?? "Sin categoría"`.
- Construir `Map<categoria, Equipo[]>` y ordenar las claves por la prioridad que viene del API (las que no aparezcan en `/api/categorias` van al final).
- Renderizar la lista como secciones con header sticky:

  ```text
  Cámaras                              3
  ─────────────────
  · Sony FX3                  + 
  · Komodo                    + 
  Lentes                               5
  ─────────────────
  ...
  ```
- Si hay `q` (búsqueda), seguimos filtrando equipos antes de agrupar; categorías sin matches se ocultan.
- "Sin categoría" siempre al final.

### Catálogo público (`src/routes/index.tsx`)
- Hoy `apiCategories` se calcula con `Array.from(new Set(...)).sort()` (alfabético).
- Cambio: pedir `useCategorias()` (ya existe en `src/hooks/useEquipos.ts`) y usar el orden devuelto por el backend (que ya estará ordenado por prioridad). Las categorías derivadas que no estén en la respuesta del backend van al final, alfabéticas.
- No se toca el agrupado/render existente, solo el array `apiCategories`.

## Orden de ejecución

1. Migración + seed + endpoints en `backend/` (1 commit).
2. Tipos y métodos en `src/lib/admin/api.ts`.
3. UI de categorías en `/admin/settings`.
4. Agrupado en `EquipoSearchSheet`.
5. Reordenar `apiCategories` en el catálogo público.
6. QA: crear pedido, abrir sheet, ver agrupado; cambiar prioridad en settings y verificar que se reordena en el sheet y en el home.

## Notas

- No se toca Supabase (los pedidos siguen yendo al FastAPI).
- `resolveCategory` (heurística por keywords en `useEquipos.ts`) se mantiene como fallback para equipos sin etiquetas; el orden lo dicta `/api/categorias`.
- El campo `prioridad` queda disponible para futuros usos: orden de subtags, sidebar de filtros, reportes, etc.
