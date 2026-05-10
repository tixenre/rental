
Ahora sí me queda claro. Tres cosas separadas, con **etiquetas como bolsa global de búsqueda** que incluye todo lo demás más palabras libres.

## Modelo

| Concepto | Dónde vive | Estructura | Ejemplos |
|---|---|---|---|
| **Categorías** | Tabla `categorias` propia | Árbol 2 niveles (parent_id), multi-asignación a equipos | Cámara → Foto, Lente → Montura E |
| **Marca** | Columna `equipos.marca` | Texto plano | Sony, Canon, Aputure |
| **Modelo** | Columna `equipos.modelo` | Texto plano | a7 V, FX3, 300X Bi-color |
| **Etiquetas** | Tabla `etiquetas` + join | Lista plana, libre | a7v, sony, foto, cámara, 4k60, fullframe, f/2.8, 5600k |

### Cómo se relacionan

Las **etiquetas** son una bolsa de strings de búsqueda. Para cada equipo se compone de:
1. **Auto** (no editable, se regenera): nombre de cada categoría asignada (incluyendo padres del árbol), `marca`, `modelo`, palabras del nombre.
2. **Manuales** (editables): lo que el admin agregue libre — "4K60", "f/2.8", "5600K", "V-Mount", "Vintage", "Cine", lo que sea.

Esto convierte a `etiquetas` en el índice universal para el buscador y filtros rápidos, mientras que **las categorías siguen siendo la navegación oficial del catálogo**.

## Cambios DB

1. **Nueva tabla `categorias`** (taxonomía dedicada)
   - `id`, `nombre`, `prioridad`, `parent_id` (FK self, 2 niveles), `slug`.
   - Seed con el árbol que ya armamos.
2. **Nueva join `equipo_categorias`** (`equipo_id`, `categoria_id`, `orden`).
3. **`etiquetas` se simplifica de vuelta**
   - Drop `parent_id` (ya no es jerárquica).
   - Agrega columna `origen TEXT NOT NULL DEFAULT 'manual'` con valores `'auto'` (derivada) o `'manual'` (puesta a mano). Permite regenerar las auto sin pisar las manuales.
   - El join `equipo_etiquetas` se queda igual.
4. **Migración**
   - Mover los nodos del árbol que están hoy en `etiquetas` → `categorias` (con su parent y prioridad).
   - Mover sus asignaciones de `equipo_etiquetas` → `equipo_categorias`.
   - Borrar esos nodos de `etiquetas`.
   - Por cada equipo, generar etiquetas `auto` desde `marca`, `modelo`, nombres de sus categorías (hoja + padre).
   - Lo que quede en `etiquetas` (si algo era spec libre) se marca `origen='manual'`.

## Backend

- **Trigger / función `regenerar_etiquetas_auto(equipo_id)`** que se llama cuando cambian categorías, marca o modelo. Borra las etiquetas `origen='auto'` del equipo y las regenera. No toca las `manual`.
- `GET /api/categorias` → árbol desde `categorias`.
- `GET /api/equipos?categoria=<id>` → CTE recursivo sobre `categorias`/`equipo_categorias`.
- `GET /api/etiquetas` → todas, con `total` (count). Búsqueda global hace `LIKE` contra etiquetas.
- `PUT /api/admin/equipos/{id}/categorias` → setea categorías hoja → dispara regenerar.
- `PUT /api/admin/equipos/{id}/etiquetas` → setea solo las `manual` (las `auto` quedan intactas).
- CRUD admin `/admin/categorias/*` (árbol) y `/admin/etiquetas/*` (libres).
- Autoclasificación → escribe en `equipo_categorias`, regenera auto-tags en consecuencia.

## Frontend

- Tipos: `Categoria` (con `parent_id`, `children`) y `Etiqueta` (plano, con `origen`).
- Hooks separados `useCategorias()` y `useEtiquetas()`.
- **`/admin/settings`** dos secciones:
  - **Categorías**: árbol editable (lo que ya hicimos, apuntando al endpoint nuevo).
  - **Etiquetas**: lista plana de las `manual` distintas (rename/merge/delete). Las `auto` se muestran en gris read-only con su origen.
  - **Clasificación auto**: aclara que aplica a categorías y regenera etiquetas.
- **`/admin/equipos`** detalle: tres campos:
  - **Categorías** (multi-select del árbol).
  - **Marca / Modelo** (inputs ya existentes).
  - **Etiquetas manuales** (free-text con autocompletar). Debajo, chip-list read-only de las `auto` para que el admin vea qué se generó.
- **Catálogo público**:
  - Filtros por **categoría** (ya existe, sin cambio visual).
  - Buscador global usa el campo `etiquetas` para matchear (cubre marca/modelo/categoría/keywords sin lógica especial).
  - Chips de specs en card/detail muestran solo las `manual` interesantes.

## Orden de ejecución

1. Migración SQL: crear `categorias` + `equipo_categorias`, copiar árbol, agregar `origen` a `etiquetas`, dropear `parent_id`, generar etiquetas auto iniciales.
2. Backend: función de regeneración + nuevos endpoints + filtros.
3. Tipos y hooks frontend.
4. Admin settings: separar categorías y etiquetas en dos secciones.
5. Editor de equipo con los tres campos.
6. Buscador global del catálogo apoyado en etiquetas.

¿Avanzo así?
