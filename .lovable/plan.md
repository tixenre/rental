## Objetivo

Hoy el pill del header solo muestra "21 may → 22 may". El usuario no sabe a qué hora retira ni devuelve, ni cuántas jornadas le cobramos. Lo aclaramos en el pill (móvil + desktop) y reforzamos en el modal.

## Cambios

### 1. `src/components/rental/TopBar.tsx` — pill con horas y jornadas

Reemplazar el contenido del pill de fechas (línea ~144) por una composición de dos líneas en móvil y una sola en desktop:

- Línea principal: `21 may 09:00 → 22 may 09:00` (con `tabular-nums` para los horarios)
- Línea/badge secundaria: `· 1 jornada` o `· N jornadas` usando `useCart().days()`

Cuando no hay fechas elegidas: mantener "Elegir fechas" con un sub-texto tenue tipo "Definí retiro y devolución".

Ícono calendario sin cambios. Mantener el touch target y el estilo amber del borde.

### 2. `src/components/rental/RentalDateModal.tsx` — etiquetas más claras

- Renombrar headers de columna: `Inicio` → `Retiro` y `Devolver` → `Devolución`.
- Debajo del calendario, agregar una fila pequeña centrada con el resumen: `N jornada(s) · retiro 09:00 · devolución 09:00`, leyendo `days()`, `startTime`, `endTime` del store.
- Pequeño hint bajo los inputs `time`: "Horario sujeto a confirmación" (texto muted, 11px).

### 3. Cálculo de jornadas — `src/lib/cart-store.ts`

La función `days()` actual cuenta días naturales (`ceil(ms/día) + 1`) sin considerar las horas. Para que coincida con la lógica de retiro/devolución del rubro:

- Si `endTime <= startTime` → jornadas = diferencia de días naturales (ej. retiro lunes 09:00, devolución martes 09:00 = 1 jornada).
- Si `endTime > startTime` → jornadas = diferencia de días naturales + 1.
- Mínimo 1.

Esto se usa también para el subtotal del carrito, así que verificar que `CartDrawer` siga mostrando el total correcto (no debería cambiar para el caso típico de mismo horario de retiro/devolución).

## Fuera de alcance

- Selector de horarios disponibles (slot picker). Seguimos con `<input type="time">`.
- Reglas de horario por sucursal o feriados.
- Cambios en el backend de pedidos.

## Archivos a tocar

- `src/components/rental/TopBar.tsx`
- `src/components/rental/RentalDateModal.tsx`
- `src/lib/cart-store.ts`
