## Problemas a resolver

1. En móvil el modal de fechas ocupa más de una pantalla y no se ven los botones "Aplicar" / "Limpiar". Hay que scrollear y no es obvio cómo confirmar.
2. Los `<input type="time">` permiten cualquier minuto. Queremos restringir a `:00` y `:30` en todo el flujo (modal y header desktop).

## Cambios

### 1. `RentalDateModal.tsx` — versión compacta en móvil

- Layout en columna full-height en móvil (`h-[100dvh]` o `max-h-[95dvh]`), con header sticky arriba y footer sticky abajo (con `safe-area-inset-bottom`). El calendario va en el medio con scroll propio.
- Calendario en móvil: `numberOfMonths={1}` (1 mes); en `sm+` mantener `2`. Reducir padding a `p-2` y tamaño de celdas para que entre cómodo.
- Reordenar resumen Retiro / Devolución apilado verticalmente en móvil (en vez de fila con flecha) para no quedar muy comprimido.
- Footer siempre visible: botón "Aplicar" full-width amber + link "Limpiar fechas" arriba a la izquierda. En desktop mantener el layout actual (un row).
- Agregar botón ✕ explícito en el header del modal (además del que trae Dialog) para ofrecer salida obvia.
- Mostrar el badge "N jornada(s) · retiro · devolución" dentro del footer (sobre el botón Aplicar) en lugar de debajo del calendario, así queda siempre visible junto a la CTA.

### 2. Selector de hora cada 30 min — nuevo componente `TimeStepSelect`

Crear `src/components/rental/TimeStepSelect.tsx`: un `<select>` nativo con opciones `00:00, 00:30, 01:00, ... 23:30` (48 valores). Devuelve `string` formato `HH:mm`. Ventajas: nativo en móvil (rueda iOS), accesible con teclado, imposible elegir minutos intermedios.

Reemplazar los `<input type="time">` actuales:
- `RentalDateModal.tsx` (retiro y devolución).
- `TopBar.tsx` `DateField` (desktop).

### 3. Normalizar horas existentes en el store

En `cart-store.ts`, los defaults `09:00` ya son válidos. Agregar utilitario `snapTo30(hhmm)` que redondee al múltiplo de 30 más cercano y aplicarlo en `setStartTime` / `setEndTime` para blindar cualquier valor que llegue de afuera (por ejemplo, persistencia previa).

## Fuera de alcance

- Bloquear horarios pasados / fuera de horario comercial.
- Mostrar disponibilidad por slot horario.
- Cambiar el calendario por uno de otra librería.

## Archivos a tocar

- `src/components/rental/RentalDateModal.tsx`
- `src/components/rental/TopBar.tsx`
- `src/components/rental/TimeStepSelect.tsx` (nuevo)
- `src/lib/cart-store.ts`
