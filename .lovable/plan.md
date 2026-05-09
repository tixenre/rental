## Objetivo

Al hacer click en un equipo, mostrar los **equipos incluidos** (sub-equipos) de forma clara. Inline acordeón en modo lista, modal en modo grilla. Solo lectura. Aplicable a todos los equipos (los que no tengan incluidos muestran ficha simple con descripción + specs).

## 1. Modelo de datos

En `src/data/equipment.ts`, extender el tipo `Equipment`:

```ts
type IncludedItem = { id?: string; name: string; qty?: number; note?: string };
type Equipment = {
  // ...campos actuales
  includes?: IncludedItem[];
};
```

- `id` opcional → si está, podemos linkear al equipo real del catálogo.
- `name` siempre, para items sueltos sin ficha propia (ej. "C-Stand", "Softbox 60cm").
- `qty` default 1.
- Helper `e()` actualizado para aceptar `includes` en el flags object.
- Pre-cargar los `includes` de los 6 combos existentes (`cm1`–`cm6`) usando los IDs reales del catálogo cuando coincidan (ej. `cm3` Combo Evento → `c4` ZVE1 + `l1` GM 24/70).
- Equipos no-combo quedan con `includes` undefined.

## 2. Componente compartido `IncludedList`

Nuevo `src/components/rental/IncludedList.tsx`:

- Recibe `item: Equipment`.
- Renderiza:
  - Descripción del equipo (si existe).
  - Bloque "Incluye" con lista de sub-equipos (thumb chico + nombre + marca si tiene id, qty con `× N` cuando >1).
  - Bloque "Specs" si `item.specs.length > 0`.
  - Si no hay nada que mostrar (sin incluidos, sin specs, sin descripción extra) → mensaje "Sin información adicional".
- Solo lectura, sin botones de carrito (el botón de agregar sigue en el row/card padre).

## 3. Modo Lista — acordeón inline

`src/components/rental/EquipmentRow.tsx`:

- Agregar estado local `expanded` (useState).
- Toda la zona de info (thumb + nombre, NO el botón +/-) se vuelve clickeable → toggle.
- Pequeño chevron a la derecha del nombre que rota cuando está abierto.
- Al expandir, debajo del row aparece un panel con `IncludedList`, animado con `framer-motion` (`AnimatePresence` + `height: auto`).
- Mantener accesible: `<button>` envolviendo la zona clickeable, `aria-expanded`.

## 4. Modo Grilla — modal

- `src/components/rental/EquipmentCard.tsx`: la imagen y el nombre se vuelven clickeables → abren modal. El botón Agregar/contador queda separado (stopPropagation).
- Nuevo `src/components/rental/EquipmentDetailDialog.tsx` usando `Dialog` de shadcn (ya disponible en `src/components/ui/dialog`):
  - Header: marca + nombre + badges (combo/nuevo).
  - Imagen grande (EmptyImage agrandado).
  - `IncludedList`.
  - Precio + botón Agregar al carrito (reusa lógica de cart-store).
- Estado de apertura controlado en `EquipmentCard` (un dialog por card está bien dado el volumen).

## 5. Detalle técnico

- Se reusa `IncludedList` en ambos lugares para mantener consistencia.
- Sin cambios de backend: cuando luego pobles `includes` desde la DB, este componente lo refleja automáticamente.
- Sin cambios al carrito ni al flujo de pedido.

## 6. Fix colateral (hydration warning)

Hay un warning de hidratación porque `useState(() => window.matchMedia(...))` en `src/routes/index.tsx` (Index) corre distinto en SSR vs cliente. Se arregla inicializando `mode` en `"grid"` (estable en SSR) y moviendo la detección mobile a un `useEffect` que actualice a `"list"` después del montaje.

## Archivos afectados

- `src/data/equipment.ts` — tipo + datos de includes en combos.
- `src/components/rental/IncludedList.tsx` — nuevo.
- `src/components/rental/EquipmentDetailDialog.tsx` — nuevo.
- `src/components/rental/EquipmentRow.tsx` — acordeón inline.
- `src/components/rental/EquipmentCard.tsx` — abre dialog al click.
- `src/routes/index.tsx` — fix hydration de `mode`.
