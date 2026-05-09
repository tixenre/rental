Vamos a implementar todas las mejoras de a una, en orden de impacto vs esfuerzo. Cada paso es un commit independiente que podés revisar antes de seguir al siguiente.

## Orden de implementación

### Fase 1 — UX inmediato (alto impacto, bajo esfuerzo)
1. **Resaltar fila expandida** en list view (borde/acento de color primario + fondo sutil).
2. **Animación de chevron** ▶ → ▼ al expandir/colapsar.
3. **Cerrar con `Esc`** la fila expandida (y el modal/sheet en grid).
4. **`aria-expanded` + focus management** en filas (foco vuelve al trigger al cerrar).

### Fase 2 — Mobile polish
5. **Swipe-down para cerrar** el bottom sheet en mobile (gesto nativo).
6. **Filtros en bottom sheet** en mobile (en vez de modal centrado).
7. **Sticky header de filtros** al hacer scroll en listados largos.

### Fase 3 — Performance
8. **Lazy-load de imágenes** (`loading="lazy"` + `decoding="async"`) y `srcset` responsive donde aplique.
9. **Prefetch de ficha al hover** en grid (precargar datos del equipo).
10. **Virtualización** del listado si hay 50+ equipos (react-virtual / tanstack-virtual).

### Fase 4 — Navegación por teclado
11. **Enter/Space** para expandir fila enfocada, **flechas ↑↓** para moverse entre filas, **Home/End** para saltar.

### Fase 5 — SEO / Compartir (cambio estructural)
12. **Ruta dedicada `/equipo/$slug`** con su propio `head()` (title, description, og:image del equipo, twitter card).
13. **JSON-LD `Product`** por equipo para rich snippets.
14. Mantener `/?eq=xxx` como redirect a `/equipo/$slug` para no romper links existentes.

## Detalles técnicos

- **Resaltado**: usar tokens semánticos (`ring-primary`, `bg-accent/30`) — sin colores hardcodeados.
- **Animación chevron**: `transition-transform rotate-90` cuando `aria-expanded=true`.
- **Esc**: hook `useEffect` con `keydown` listener cuando hay fila abierta.
- **Sheet swipe**: shadcn `Sheet` ya soporta drag, sólo configurar.
- **Lazy images**: pasar `loading`/`decoding` props al componente de imagen en `EquipmentCard` y `EquipmentRow`.
- **Virtualización**: solo activarla con threshold (>50 items) para no complicar el caso común.
- **Ruta `/equipo/$slug`**: nueva file-based route, loader que trae el equipo desde Lovable Cloud, `head()` dinámico desde loader data, JSON-LD inyectado en el render.

## Plan de trabajo

Voy a ir implementando **una mejora por turno** (a veces dos si son muy chicas y relacionadas, ej. 1+2). Después de cada cambio, te confirmo qué se hizo y seguimos con la siguiente. Si en algún punto querés saltarte una o cambiar el orden, me avisás.

¿Arrancamos con la Fase 1 (mejoras 1+2 juntas: resaltar fila + chevron animado)?
