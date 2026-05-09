## Objetivo
Reemplazar el catálogo estático por el backend `https://ramblarental.up.railway.app`, agregar disponibilidad real por fechas y enviar pedidos al endpoint `/api/alquileres`. Si el backend falla, caer al mock para no romper la preview.

## Lo que ya funciona en el backend (verificado con curl)
- `GET /api/equipos?per_page=500&solo_visibles=true` → 142 equipos. Devuelve `id, nombre, marca, modelo, cantidad, precio_jornada, foto_url, etiquetas[], kit[]`.
- `GET /api/disponibilidad?fecha_desde&fecha_hasta` → mapa `{ "<id>": unidades_disponibles }`.
- CORS habilitado para `https://ramblarental.lovable.app` (dominio publicado).

## Lo que NO funciona todavía (Claude/back lo resuelve)
Estos puntos los dejo documentados pero NO los toco desde el front:
1. `GET /api/categorias` devuelve `[]` (vacío).
2. Los equipos vienen con `etiquetas: []`, así que no hay categoría real → todos caerían como "Accesorios".
3. CORS solo permite el dominio publicado. Las URLs de preview (`id-preview--*.lovable.app`) están bloqueadas — agregar wildcard o lista.
4. Falta confirmar el shape de `POST /api/alquileres` (probablemente ya implementado por Claude).

## Cambios en el frontend

### 1. Variable de entorno
- Crear `.env.local` con `VITE_API_URL=https://ramblarental.up.railway.app`.

### 2. Adaptador `backendToEquipment` (`src/hooks/useEquipos.ts`)
- Mapear `foto_url` → `fotoUrl`, ya existente.
- Cuando `etiquetas[]` está vacío: derivar categoría heurísticamente desde `nombre/modelo` (palabras clave: "lente", "cámara", "luz", "trípode", etc.) en una util `inferCategory()`. Es paliativo hasta que el back tagee.
- Mantener `_backendId` como número para el POST de pedido.

### 3. Hook `useEquipos` con fallback al mock
- Envolver la query en try/catch: si falla o devuelve 0 items, retornar `equipment` (mock estático) y exponer flag `usingFallback`.
- En dev, mostrar un pill discreto en `TopBar` cuando `usingFallback === true` ("Modo offline").

### 4. Disponibilidad real
- En `src/routes/index.tsx`, `useDisponibilidad(startDate, endDate)` ya está conectado.
- En `EquipmentRow` y `EquipmentCard`: si hay rango y el equipo tiene `_backendId`, leer `disponibilidad[_backendId]`. Mostrar "X disponibles" debajo del precio. Deshabilitar "Agregar" cuando `qty solicitada > disponibles`.
- Toast cuando el usuario intenta superar el stock.

### 5. Envío de pedido (`CartDrawer`)
- Agregar paso final con form mínimo: nombre, email, teléfono opcional. Validación con Zod.
- Al confirmar:
  ```ts
  apiPostPedido({
    cliente_nombre, cliente_email, cliente_telefono,
    fecha_desde: format(startDate, "yyyy-MM-dd"),
    fecha_hasta: format(endDate, "yyyy-MM-dd"),
    items: cart.map(c => ({
      equipo_id: c.eq._backendId!,
      cantidad: c.qty,
      precio_jornada: c.eq.pricePerDay,
    })),
  })
  ```
- Filtrar items sin `_backendId` (mock-only) con warning.
- Estados: loading, success (toast + clear cart + cerrar drawer), error (mostrar mensaje del backend).

### 6. Memoria
- Actualizar `mem://index.md`: el catálogo ya no es estático, ahora viene del backend con fallback al mock.

## Archivos a tocar
```
.env.local                          (crear, VITE_API_URL)
src/hooks/useEquipos.ts             (fallback + inferCategory + estado disponibilidad)
src/lib/cart-store.ts               (helpers para validar stock, si hace falta)
src/components/rental/EquipmentRow.tsx     (badge disponibilidad)
src/components/rental/EquipmentCard.tsx    (badge disponibilidad)
src/components/rental/CartDrawer.tsx       (form cliente + submit)
src/components/rental/TopBar.tsx           (badge "modo offline" en dev)
src/routes/index.tsx                       (pasar disponibilidad a las rows)
mem://index.md                             (actualizar nota)
```

## Lo que queda pendiente para Claude (back)
- Llenar `etiquetas` en cada equipo o devolver `categoria` explícita.
- Implementar `GET /api/categorias` con totales reales.
- Ampliar CORS a `*.lovable.app` (o al menos a las URLs de preview).
- Confirmar/exponer `POST /api/alquileres` con el shape del cliente (ver `apiPostPedido` en `src/lib/api.ts`).
- Idealmente: campos `descripcion`, `specs`, `is_combo`, `kit/includes` en `/api/equipos` para no perder esa info al migrar.

## Out of scope (esta tanda)
- Auth de usuario (signup/login contra el backend Python).
- Fotos reales en equipos / lazy loading.
- Pantalla "mis pedidos" leyendo del backend.
