## Objetivo

Mantener el diseño editorial/brand BATTI ya armado (hero amarillo, wordmark, ilustraciones, paleta) y enriquecerlo con las mejores ideas de UX que tiene `ramblarental.com.ar`, sin crear página de producto. Solo dos vistas: **Grid** (exploración curada con carruseles) y **Lista** (rápida, densa, para quien sabe qué busca).

---

## Qué nos llevamos del sitio actual

Después de revisar `ramblarental.com.ar`, lo que vale la pena adoptar:

1. **Bandas de carruseles temáticos** en la home: "Ingresos" (novedades), "Combos", y luego un carrusel por categoría (Cámaras, Lentes, Luces, etc.) con CTA "Ver todas".
2. **Categorías reales** del catálogo: Cámaras, Lentes, Monitores, Luces, Tungsteno, Modificadores, Comunicación, Flash, Stands, Grips, Trípode, Sonido, Baterías, Filtros, Brazo Mágico (15 cats reales vs. las 7 actuales).
3. **Formato de precio argentino**: `$97.500,00 / 1 Jornada` en vez de USD.
4. **WhatsApp visible** en el header (top bar amarilla con `+54 9 223 585 2510`).
5. **Link "¿Cómo Funciona?"** y **Login** en el extremo derecho.
6. **CTA fechas** prominente ("Seleccioná un período de alquiler — Ver precios y disponibilidad").
7. **Combos** como tipo de producto destacado (kits que combinan equipos).
8. **Datos reales de productos** (Sony FX3, Red Komodo X, Sony GM 24/70, etc.) con sus precios reales para que el mock se sienta verdadero.

Lo que **no** copiamos: el estilo Booqable genérico, las cards blancas planas, la falta de jerarquía editorial. Mantenemos la dirección actual.

---

## Cambios concretos

### 1. Toggle Grid/Lista — dos modos bien diferenciados

Hoy el toggle solo cambia la grilla de cards. Lo convertimos en dos **modos de página** distintos:

- **Modo Grid (curado / explorar)** → bandas horizontales con carruseles. Pensado para descubrir.
- **Modo Lista (índice / buscar)** → tabla densa de todos los equipos. Pensado para escanear rápido.

El selector queda en la barra sticky (mismo lugar que ahora) pero más prominente, con labels: "Explorar" / "Lista completa".

### 2. Modo Grid — bandas tipo editorial

Reemplaza la grilla plana actual por un scroll vertical con secciones:

```text
[ Hero amarillo "un lugar donde pasan cosas" ] ← se mantiene
[ Banda: Ingresos ────────────────────► ]   carrusel horizontal
[ Banda: Combos  ────────────────────► ]   carrusel, cards más anchas
[ Bloque: Categorías (mosaico 4×4) ]        ilustraciones + contador
[ Banda: Cámaras ────────────────────► ]   "Ver todas" →
[ Banda: Lentes  ────────────────────► ]
[ Banda: Luces   ────────────────────► ]
[ Banda: Sonido  ────────────────────► ]
... resto de categorías
[ Footer ]
```

Cada banda:
- Título grande con `wordmark` (display), contador chico al lado, link "Ver todas" a la derecha.
- Cards con scroll horizontal, snap-points, flechas prev/next discretas.
- Reusa `EquipmentCard` actual (no se tocan los componentes de card).

### 3. Modo Lista — índice denso

- Reusa `EquipmentRow` actual.
- Suma una **barra de filtros sticky** arriba: chips por categoría (multi-select), filtro por marca, rango de precio, y el buscador ya existente.
- Sidebar de categorías se oculta (la lista es ya el índice).
- Densidad alta: filas más compactas, sin ilustraciones grandes, foco en nombre + marca + categoría + precio + botón "+".

### 4. Datos mock realistas

Actualizamos `src/data/equipment.ts` con productos y precios reales del sitio: Sony FX3 ($122.500), Red Komodo X ($359.000), Sony GM 24/70 ($76.500), Hollyland Solidcom C1 ($68.000), Combo RGB Amaran 300 ($87.900), Kit Arri 3und ($90.000), etc. Categorías ampliadas a las 15 reales. Agregamos un flag `isNew: boolean` y `isCombo: boolean` para alimentar las bandas "Ingresos" y "Combos".

Formato de precio: helper `formatARS(n)` → `$97.500,00`. Sufijo `/ 1 Jornada`.

### 5. TopBar — pequeñas mejoras

- Sumar **WhatsApp pill** (`+54 9 223 585 2510`) a la izquierda en desktop, ícono solo en mobile.
- Sumar link **"¿Cómo funciona?"** (sin página por ahora, solo modal placeholder o `#`).
- Mantener el wordmark, el selector de fechas y el carrito tal cual.

### 6. Nuevos componentes

```text
src/components/rental/
  CarouselRow.tsx          ← banda horizontal con título + scroll snap + flechas
  CategoryMosaic.tsx       ← grilla 4×4 de categorías con ilustración + contador
  ListFilters.tsx          ← chips de categoría + marca + precio para modo Lista
  WhatsappPill.tsx         ← botón pill con ícono + número
src/lib/
  format.ts                ← formatARS, formatDays
```

`src/routes/index.tsx` se reorganiza para alternar entre `<GridMode />` y `<ListMode />` según el toggle. La lógica de filtros/búsqueda actual pasa a `ListMode`.

---

## Detalles técnicos

- Carruseles: scroll-snap CSS nativo (`snap-x snap-mandatory`) + botones que hacen `scrollBy({ left: ±width })`. Sin librería extra.
- Filtros del modo Lista: estado local en el componente, sin URL params (lo dejamos para una iteración siguiente si lo querés).
- Mocks: el archivo `equipment.ts` queda con ~40-50 ítems reales del sitio, suficiente para que las bandas se vean pobladas.
- Sin backend todavía: todo sigue siendo frontend con mock data, como pediste.

---

## Fuera de scope (para después)

- Página de detalle de producto.
- Conexión real al backend / Booqable / Lovable Cloud.
- Selector de fechas funcional con disponibilidad real.
- Login y "¿Cómo funciona?" como páginas reales.
- Footer editorial completo.

¿Avanzo con esto?