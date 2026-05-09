
# Rediseño Rambla Rental — editorial / cinematográfico

Voy a reconstruir la interfaz del catálogo de alquiler con una estética editorial cinematográfica (pensada para rental de equipos de cine/foto), manteniendo el flujo actual pero más claro, rápido y con mucha más jerarquía visual. Todo con datos simulados (mock) en español.

## Dirección visual

- **Paleta**: negro profundo de fondo, blanco hueso para texto, un único acento ámbar/dorado (similar al amarillo actual pero más sofisticado) y grises neutros para superficies.
- **Tipografía**: una display serif de alto contraste para títulos (tipo editorial de revista de cine) + una sans geométrica para UI y datos. Números tabulares para precios.
- **Tono**: mucho aire, tipografía grande, fotos protagonistas, microdetalles (líneas finas, etiquetas tipo "ficha técnica", numeración de items, badges discretos).
- **Movimiento**: transiciones sutiles con framer-motion (fade/slide al cargar grid, hover en tarjetas, entrada del carrito).

## Estructura de la app

Una sola ruta principal `/` (catálogo) más una ruta de detalle `/equipo/$slug`.

```
src/routes/
  index.tsx              → Catálogo (hero + filtros + grid)
  equipo.$slug.tsx       → Ficha de equipo
src/components/rental/
  TopBar.tsx             → Logo, selector de fechas, usuario, contador de ítems
  CategorySidebar.tsx    → Categorías + Marcas (colapsable en mobile)
  SearchSortBar.tsx      → Búsqueda + ordenamiento + toggle grid/lista
  EquipmentCard.tsx      → Tarjeta de equipo (grid)
  EquipmentRow.tsx       → Fila de equipo (lista)
  CartDrawer.tsx         → Panel lateral con ítems seleccionados
  DateRangePicker.tsx    → Desde / Hasta con horas
  EmptyImage.tsx         → Placeholder "sin foto" estilizado
src/data/equipment.ts    → Mock data (categorías, marcas, ~40 equipos)
src/lib/cart-store.ts    → Estado global del carrito (zustand)
```

## Mejoras de UX clave sobre el sitio actual

1. **Hero compacto** arriba con el nombre del rental, tagline y selector de fechas grande y claro (en lugar de inputs apretados arriba a la izquierda).
2. **Sidebar de categorías** con conteo por categoría, marca activa resaltada, búsqueda dentro de marcas, colapsable en mobile como drawer.
3. **Tarjetas de equipo** rediseñadas: imagen 4:3, marca como kicker pequeño, nombre prominente, precio con jerarquía clara, botón "Agregar" en lugar de stepper visible siempre (el stepper aparece al agregar). Hover muestra acciones secundarias (ver detalle, favorito).
4. **Estado seleccionado**: borde sutil + check en esquina, no marco amarillo grueso.
5. **Carrito como drawer lateral** persistente, con resumen de fechas, subtotal por jornada y total estimado, botón "Solicitar cotización".
6. **Vista lista** densa con miniatura, specs y precio alineados — útil para usuarios que conocen el equipo.
7. **Búsqueda con resultados instantáneos** y resaltado del término.
8. **Página de detalle** por equipo con galería, descripción, specs, precio por jornada / fin de semana / semana, "Agregar al pedido".
9. **Skeletons** al cargar y empty states cuidados.
10. **Responsive real**: en mobile, sidebar como bottom sheet, grid 2 columnas, top bar sticky.

## Datos mock

Un archivo `src/data/equipment.ts` con ~40 equipos repartidos en categorías (Cámaras, Lentes, Iluminación, Audio, Soportes, Accesorios, Adaptadores) y marcas reales (Canon, Sony, Sigma, Aputure, Godox, Manfrotto, DJI, etc.), con precios en pesos por jornada. Sin imágenes reales — uso un placeholder editorial bonito (gradiente + ícono + marca de agua de la marca).

## Detalles técnicos

- Tokens de color y tipografía definidos en `src/styles.css` con `oklch`. Sin colores hardcodeados en componentes.
- Estado del carrito y filtros en `zustand` (ligero, sin servidor).
- Animaciones con `framer-motion` (ya usable, lo instalo).
- Tipografías cargadas desde Google Fonts en `__root.tsx` (por ejemplo *Fraunces* display + *Inter Tight* sans, o *Editorial New* alternativa).
- SEO: `head()` en cada ruta con título y descripción propios, H1 único.
- Sin backend — todo cliente. Si más adelante querés persistir pedidos o tener panel admin, activamos Lovable Cloud.

## Lo que NO incluye (pueden ser próximos pasos)

- Checkout real, pagos, login.
- Imágenes reales de los equipos (uso placeholders; podés subir fotos después).
- Panel de administración del catálogo.
- Disponibilidad real según fechas (se muestra como UI pero no valida stock).

¿Le doy para adelante con esto?
