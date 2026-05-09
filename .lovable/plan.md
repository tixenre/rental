# Bug: se pueden seleccionar más unidades que el stock

## Diagnóstico
El control "+" se deshabilita cuando `qty >= disponible`, pero `disponible` solo existe cuando el usuario eligió fechas (`useDisponibilidad`). Sin fechas, `disponible === undefined` y el botón nunca se bloquea, por lo que el carrito acepta cantidades ilimitadas.

Además:
- El botón inicial "Agregar" (cuando `qty === 0`) solo valida `sinStock`, no el tope.
- En `CartDrawer` el "+" hace lo mismo: solo valida contra `disponible`.
- `useCart.add` no aplica ningún tope.

El equipo siempre trae `cantidad` (stock total) desde el backend, así que podemos usarlo como tope cuando no hay fechas.

## Solución (solo frontend)

### 1. Tope efectivo = `min(disponible ?? cantidad, cantidad)`
Helper local en cada componente que muestra el control:
```ts
const cap = disponible ?? item.cantidad ?? Infinity;
const reachedMax = qty >= cap;
```

### 2. `EquipmentRow.tsx` y `EquipmentCard.tsx`
- Reemplazar la condición actual (`disponible !== undefined && qty >= disponible`) por `reachedMax`.
- Botón "+" (incremento) deshabilitado si `reachedMax`.
- Mostrar tooltip / título "Stock máximo alcanzado" cuando aplica.
- En el botón inicial "Agregar" (qty===0): si `cap <= 0` → "Sin stock" (ya cubierto), pero también respetar `reachedMax` por si `cantidad` viene en 0.

### 3. `CartDrawer.tsx`
- Reemplazar la lectura de `getDisponible(it)` por `min(getDisponible(it) ?? it.cantidad, it.cantidad)` y bloquear "+" igual que arriba.
- Si una cantidad ya cargada supera el tope (porque cambiaron fechas y bajó el stock), mostrar warning visual y un botón "Ajustar al máximo".

### 4. `cart-store.ts` — defensa en profundidad
- Cambiar `add(id)` a `add(id, max?: number)` y aplicar `Math.min(next, max)` cuando se pase.
- Pasar `max` desde los call sites (Card, Row, Drawer).
- `setQty` opcional: aceptar `max` y clamp.

### 5. Toast cuando se intenta superar
- Reutilizar `sonner` ya configurado.
- Mensaje: "Stock máximo: {cap} unidades".

## Archivos a tocar
```
src/lib/cart-store.ts                  (add/setQty con max opcional)
src/components/rental/EquipmentRow.tsx (cap + disable + toast)
src/components/rental/EquipmentCard.tsx (cap + disable + toast)
src/components/rental/CartDrawer.tsx   (cap + warning si supera)
```

## Out of scope
- Validación server-side (la hace el backend al `POST /api/alquileres`).
- Sincronización en tiempo real del stock.
- Cambios visuales mayores: solo el disable + un toast discreto.
