## Diagnóstico

1. **No es sticky.** En `src/styles.css` líneas 155-162 hay `overflow-x: hidden` en `html, body`. Esa propiedad convierte al body en un contenedor de scroll y rompe `position: sticky` de descendientes (TopBar y la barra de fechas). Por eso al hacer scroll, todo se va con el contenido.

2. **El pill ocupa más alto del necesario.** Tiene dos líneas (`Elegir fechas` + `RETIRO Y DEVOLUCIÓN` en mono caps) que sumadas al padding y al border miden ~64px. Sumado al toggle/contador de la segunda fila, la barra mide casi 130px.

## Cambios

### 1. Arreglar sticky — `src/styles.css`

Reemplazar `overflow-x: hidden` por `overflow-x: clip` en `html, body`. `clip` evita scroll horizontal sin crear un nuevo contexto de scroll, así sticky vuelve a funcionar. Fallback: en navegadores muy viejos (Safari < 16) hace lo mismo que `visible` — aceptable porque ya enderezamos las causas reales del overflow (h1 hero, etc.).

### 2. Layout más compacto en móvil — `MobileStickyBar.tsx` + `index.tsx`

Pill compacto:
- Una sola línea cuando no hay fechas: `📅 Elegir fechas` (sin caption secundaria).
- Cuando hay fechas: una línea `📅 04 jun 11:00 → 06 jun 09:00 · 2j` con `truncate`. Eliminar la segunda línea de "jornadas" — el `· 2j` queda al final.
- Reducir padding del pill: `py-2` → `py-1.5`, font-size `text-[13px]` para que entre cómodo. Altura final ~38px.
- Botón lupa mantiene 40x40 (touch target).

Toggle + contador (segunda fila):
- Bajar a una sola fila más liviana: ocultar el contador en `xs` mobile (`hidden xs:block`) o moverlo dentro del toggle como `· 142`.
- Reducir padding del contenedor sticky: `py-3` → `py-2`.

Resultado esperado: barra sticky ~88px en móvil (40 pill + 8 gap + 32 toggle + 8 padding) en lugar de ~130px.

### 3. Ajustar offsets sticky

Con TopBar mobile en una sola fila (~56px) y barra sticky abajo, mantener `top-14` como ya está. Verificar que ningún wrapper intermedio tenga `overflow:hidden`/`auto`. Si la página entera está dentro de un `<main className="overflow-hidden">` o similar hay que cambiarlo a `overflow-x: clip`.

## Fuera de alcance

- Animar la transición pill ↔ búsqueda.
- Cambiar el TopBar.
- Tocar el desktop.

## Archivos a tocar

- `src/styles.css`
- `src/components/rental/MobileStickyBar.tsx`
- `src/routes/index.tsx` (segunda fila del sticky)
- Posible: revisar `<main>` / wrappers en `__root.tsx` si tienen overflow problemático
