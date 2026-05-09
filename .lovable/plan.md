## Idea

En móvil, juntar el pill de fechas y la búsqueda en una sola fila sticky justo debajo del header. El pill ocupa la mayor parte del ancho con la info de fechas/jornadas; al lado, un botón redondo con la lupa que abre un campo de búsqueda expandible. Así ambas funciones quedan siempre a mano sin gastar dos filas.

```
┌──────────────────────────────────────┐
│ rambla | RENTAL    🛒²   👤          │  ← TopBar (sin pill)
├──────────────────────────────────────┤
│ 📅 04 jun 11:00 → 06 jun 09:00  · 2j │ 🔍│  ← sticky bar nueva
│                                      │   │
└──────────────────────────────────────┘
```

Tap en 🔍 → la fila se transforma: input full-width con el campo abierto + ✕ para volver al estado pill.

En desktop el TopBar ya tiene los selectores de fecha. Mantenemos la barra sticky actual (búsqueda + toggle grid/list + contador) sin cambios visibles.

## Cambios

### 1. `TopBar.tsx`

Eliminar la fila 2 mobile (el pill `Elegir fechas`). El TopBar mobile queda en una sola fila compacta: logo + carrito + usuario. Esto reduce su altura a ~56px y libera espacio para la nueva barra sticky.

### 2. `src/routes/index.tsx` — barra sticky combinada (mobile)

En el contenedor sticky existente (línea ~212), agregar una nueva fila visible solo en móvil (`md:hidden`) por encima del search/toggle actual:

- Estado por defecto (`searchOpen=false`): `[ pill fechas (flex-1) ] [ botón lupa 40x40 ]`. El pill es el mismo trigger del modal de fechas (reutilizar lógica de `TopBar`: abrir `RentalDateModal`). Muestra la misma info que ahora: `dd MMM HH:mm → dd MMM HH:mm` + `· N j`.
- Estado abierto (`searchOpen=true`): `[ input full-width con lupa interna y autoFocus ] [ ✕ ]`. Al cerrar vuelve al estado pill y limpia query si está vacío.

El `RentalDateModal` ya existe y se controla con `dateModalOpen`. Levantamos ese estado al index (o creamos un store mínimo) — opción más simple: extraer un componente `<MobileStickyBar />` que maneja su propio `dateModalOpen` y `searchOpen` y recibe `query`/`setQuery` por props.

El bloque sticky existente (search input + toggle grid/list + contador) pasa a `hidden md:flex` para no duplicar la búsqueda en mobile. El toggle grid/list y el contador quedan en una fila secundaria mobile (sin la búsqueda).

Ajustar `top-[...]` del sticky: ahora que el TopBar mobile baja a ~56px, usar `top-14` (56px) en mobile y mantener `sm:top-[60px]`.

### 3. Persistencia visual

- La barra nueva usa el mismo fondo `bg-background/95 backdrop-blur-md` y `border-b hairline` para integrarse con el TopBar.
- Toque mínimo 40px para el botón de lupa.
- El pill conserva las dos líneas de info (fecha+hora arriba, "N jornadas" abajo) pero más compactas si hace falta.

## Fuera de alcance

- Cambios en desktop (mantiene la barra sticky actual con search + toggle).
- Búsqueda con sugerencias/autocomplete.
- Persistir `searchOpen` entre navegaciones.

## Archivos a tocar

- `src/components/rental/TopBar.tsx`
- `src/routes/index.tsx`
- (posible) `src/components/rental/MobileStickyBar.tsx` (nuevo, para no inflar `index.tsx`)
