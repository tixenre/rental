## Objetivo

Mostrar chips removibles con los filtros activos (marca + categorías + búsqueda) justo encima del listado en **móvil**, para quitar uno puntual con un tap sin reabrir el sheet.

## Diagnóstico

Hoy en móvil, una vez aplicados filtros desde el sheet, no hay feedback visible de qué está activo (solo el badge numérico en el botón ⚙). Para sacar uno hay que abrir el sheet y desmarcar.

## Propuesta visual

```text
┌─ TopBar ───────────────────────────────────────┐
├─ 📅 04 jun → 06 jun · 2j   🔍   ⚙ ③          │ ← sticky
├─────────────────────────────────────────────────
│  Canon ✕   Lentes ✕   Iluminación ✕   Limpiar │ ← NUEVO
│  ▸ Adaptador EF-RF…   $13.500 /día        +   │
```

- Cada chip muestra el valor + ícono `✕` (tap = quita ese filtro).
- Si hay 2+ filtros activos, al final aparece un botón "Limpiar" sutil.
- Si no hay filtros, no se renderiza nada (cero ruido).
- Solo móvil (`sm:hidden`) — desktop ya tiene controles visibles en `ListFilters`.
- Scroll horizontal si no entran en una línea (`overflow-x-auto`, sin wrap).

## Estilo

Coherente con chips existentes:
- Activo: `bg-ink text-amber rounded-full px-3 py-1 text-xs` con `X` 12px a la derecha.
- Búsqueda activa: chip `🔍 "texto" ✕` que limpia `query`.

## Cambios técnicos

- **Nuevo** `src/components/rental/ActiveFiltersChips.tsx`
  - Props: `selectedCategories`, `onToggleCategory`, `selectedBrand`, `onBrand`, `query`, `onQuery`, `onClear`.
  - Retorna `null` si no hay nada activo.
  - `sm:hidden`.

- `src/routes/index.tsx` → en `ListMode`, insertar `<ActiveFiltersChips …/>` después de `<ListFilters/>` y antes de `space-y-1.5`. Pasar `query` / `setQuery` (ya disponibles).

## Fuera de alcance

- Desktop (sin cambios).
- Lógica de filtrado, sheet, pill de fechas, barra sticky.
