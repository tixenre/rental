## Selector de fechas tipo Booqable en el TopBar

Reemplazar los dos `DateField` separados del TopBar por **una sola píldora clickeable** que muestra el rango ("6 may 11:00 → 7 may 10:00" o "Elegí fechas") y abre un **modal de rango** inspirado en la captura.

### Componente nuevo: `RentalDateModal.tsx`

Dialog (shadcn) con:

1. **Header**: "Tu Rental" + cerrar (X).
2. **Resumen editable** arriba — dos columnas (Inicio / Devolver), cada una con fecha + hora subrayadas, inicio en azul, devolución en rojo, flecha entre ambas. Click en la fecha enfoca el calendario, click en la hora abre input nativo.
3. **Doble calendario** (mes actual + siguiente) lado a lado con navegación `‹ ›`. Selección de rango: primer click = inicio, segundo = devolución, tercero = reinicia.
4. **Estados visuales por día** (mock — no hay backend aún):
   - Pasados → gris rayado, deshabilitados
   - Disponibles → píldora verde
   - Día parcial / "hoy" → verde claro con número subrayado
   - Ocupado simulado → ámbar (1-2 días random para mostrar la lógica)
   - Rango seleccionado → contorno azul + relleno suave entre inicio y fin
5. **Footer**: "✕ Limpiar fechas" a la izquierda, botón **"Aplicar"** ámbar a la derecha. Aplicar cierra el modal y guarda en el store.

### Cambios en `TopBar.tsx`

- Eliminar los dos `DateField` y la flecha.
- Insertar un único botón píldora con ícono calendario que muestra:
  - Sin fechas: "Elegí tus fechas"
  - Con fechas: `6 may 11:00 → 7 may 10:00` (formato ES, abreviado).
- Click → abre `RentalDateModal`.
- En mobile la píldora se compacta a "Fechas" + ícono.

### Store

`cart-store.ts` ya tiene `startDate/endDate/startTime/endTime/setDates/setStartTime/setEndTime` — no requiere cambios.

### Detalles técnicos

- Usar `Dialog` de shadcn (`src/components/ui/dialog`) para el contenedor.
- Usar `react-day-picker` (ya viene con shadcn `Calendar`) en `mode="range"` con `numberOfMonths={2}`, sobreescribiendo `classNames` para conseguir el look de píldoras verdes/ámbar (no el cuadrado por defecto).
- `modifiers` para `busy` (mock: el lunes siguiente al hoy) → estilo ámbar; `disabled` para días pasados.
- `formatRange` helper en `src/lib/format.ts` para la etiqueta del botón.
- En viewport <768px: un solo mes visible, modal full-screen.

### Fuera de alcance

- Disponibilidad real por equipo (requiere backend / Lovable Cloud).
- Bloqueos por stock cruzado con el carrito.
- Selección de hora avanzada (slots, mínimo de alquiler) — se mantiene `<input type="time">`.

¿Avanzo con esto?