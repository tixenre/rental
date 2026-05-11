# Auditoría mobile — checklist + status

> Crítico para launch porque la mayoría del tráfico de un rental viene de móvil
> (clientes consultando desde sets, productoras, etc.). Sin mobile, no hay launch.

## Cómo correr la auditoría

### Manual (rápido, sin setup)

1. Abrir Chrome → DevTools (F12) → toggle device toolbar (Cmd+Shift+M).
2. Elegir viewport: **iPhone SE** (375×667), **iPhone 14 Pro** (393×852), **Pixel 7** (412×915).
3. Recorrer todas las páginas listadas abajo, marcando cada checkpoint.
4. Reportar cualquier problema nuevo como issue con label `bug,priority:high`.

### Automatizado (futuro — issue separado)

Sistema sugerido: **Playwright** con viewports preset. Cada PR corre smoke tests:

```ts
test.use({ viewport: { width: 375, height: 667 } }); // iPhone SE
test("home no tiene scroll horizontal", async ({ page }) => {
  await page.goto("/");
  const overflowX = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflowX).toBe(false);
});
```

Aún no implementado.

---

## Checklist por checkpoint

Para cada página, verificar **todos** estos puntos antes de marcar como OK:

| | Checkpoint | Cómo verificarlo |
|---|---|---|
| ☐ | Sin scroll horizontal | El `scrollWidth` no excede el `innerWidth` |
| ☐ | Todos los botones ≥ 40px | Tocar con el dedo sin precisión, fácil |
| ☐ | Textos legibles | Tamaño ≥ 14px para texto base, ≥ 16px para inputs |
| ☐ | Inputs no zoomean al focus | iOS hace zoom si font-size < 16px |
| ☐ | Imágenes escalan bien | `object-contain` o `object-cover`, no se distorsionan |
| ☐ | Modales caben | `max-h-[90dvh]` o `h-[100dvh]` con overflow-y scroll |
| ☐ | Carrito accesible | Botón siempre visible (sticky bottom o header) |
| ☐ | Fechas accesibles | El selector se abre y permite elegir sin trabarse |
| ☐ | Imágenes con `loading="lazy"` | Performance — solo carga lo que se ve |
| ☐ | Touch feedback | `:active` con cambio visible al tocar |

---

## Páginas a auditar

### Públicas

| Página | URL | Status | Notas |
|---|---|---|---|
| Catálogo (grid) | `/` | 🟢 OK | Hero escala bien (text-5xl→7xl→[7rem]). Cards responsive. |
| Catálogo (list mode) | `/` con toggle list | 🟢 OK | Row simplificado post-PR #111. Sin expand inline. |
| Ficha de equipo | `/equipo/{id}` | 🟢 OK | Layout mobile-first con precio sticky bottom (PR #111). |
| El Estudio | `/estudio` | 🟡 Verificar | FAQ accordion + booking form en mobile. |
| Preguntas frecuentes | `/preguntas-frecuentes` | 🟢 OK | Layout simple, accordions. |
| Login cliente | `/cliente/login` | 🟢 OK | Formulario centrado, inputs full-width. |
| Registro cliente | `/cliente/registro` | 🟢 OK | Idem. |

### Portal cliente

| Página | URL | Status | Notas |
|---|---|---|---|
| Lista de pedidos | `/cliente/portal` | 🟢 OK | Acordeón expandible por pedido. |
| Perfil | `/cliente/perfil` | 🟢 OK | Form simple. |

### Componentes críticos

| Componente | Status | Notas |
|---|---|---|
| TopBar | 🟢 OK | Logo PNG (PR #105), botón user 40px (este PR). |
| MobileStickyBar | 🟢 OK | Fechas + search + filtros. Tap targets 40px. |
| RentalDateModal | 🟢 OK | `h-[100dvh] sm:h-auto sm:max-h-[90dvh]`. |
| CartDrawer | 🟢 OK | `h-[100dvh] w-full max-w-md`. |
| EquipmentCard | 🟡 Verificar | Botones +/- son h-7 (28px) pero adentro de pill con padding. |
| EquipmentRow | 🟢 OK | Botones h-9 mobile, h-7 desktop. Imagen lazy (este PR). |
| Footer | 🟢 OK | Layout mobile-first (PR #79). |

---

## Hallazgos resueltos en esta PR

### Inputs disparaban zoom en iOS

**Problema:** iOS hace zoom automático al focus en cualquier input con `font-size < 16px`. Los formularios de `/cliente/perfil`, `/cliente/registro` y otros usaban `text-sm` (14px).

**Fix:** regla CSS global en `styles.css`:

```css
@media (max-width: 767px) {
  input, textarea, select {
    font-size: max(16px, 1em);
  }
}
```

Fixea **todos** los inputs del proyecto sin tocar componentes. Desktop (`md+`) sigue con `text-sm` si lo tiene.

### Botón usuario en TopBar muy chico

**Problema:** mobile tenía `w-8 h-8` (32px) — bajo el mínimo Apple HIG de 44px.

**Fix:** `w-10 h-10` (40px) en mobile. Suficientemente grande sin desbalancear el header.

### Imágenes sin lazy loading

**Problema:** `EquipmentRow` y la lista de pedidos del cliente mostraban imágenes sin `loading="lazy"` — el browser las descargaba todas al cargar.

**Fix:** `loading="lazy"` agregado.

---

## Hallazgos pendientes (issues abiertos)

| | |
|---|---|
| Tap targets en cards/rows (+/- buttons) | h-7 (28px) dentro de pill con padding — funcional pero podríamos ir a h-9. Bajo prioridad. |
| Touch feedback en botones | Falta `:active` con animación clara. UX polish. |
| Sistema de auditoría automatizada | Playwright + viewport tests — issue separado. |

---

## Re-auditar cuando

- Se agregue una página nueva.
- Se cambie el diseño de TopBar, Cart, DateModal o Footer (componentes globales).
- Se actualice Tailwind o shadcn (puede romper sizing).
- Antes de cada deploy a producción si hubo cambios de UI.

Mantener este doc actualizado con cada fix.
