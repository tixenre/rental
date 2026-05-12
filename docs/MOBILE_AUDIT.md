# Auditoría mobile — criterio, checklist + status

> Crítico para launch porque la mayoría del tráfico de un rental viene de móvil
> (clientes consultando desde sets, productoras, etc.). Sin mobile, no hay launch.

## Criterio

**Cada ruta debe tener un layout mobile pensado a propósito, no solo un escalado responsive automático.**

Una ruta cumple el criterio cuando:

1. **Hay un patrón mobile visible en el código** — dual render
   (`md:hidden` / `hidden md:block`), sticky bar, sheet fullscreen, lista
   card-based, etc. *No alcanza* con un grid que colapse por default.
2. **Pasa el checklist** de la sección "Checklist por checkpoint" abajo
   (sin scroll horizontal, tap targets ≥ 40px, texto legible, inputs sin
   zoom iOS, modales que entran en `h-[100dvh]`, imágenes lazy).
3. **Está validada manualmente** en viewport **375×667 (iPhone SE)** —
   el mínimo objetivo del proyecto.
4. **Está marcada 🟢 OK** en las tablas de status de este documento,
   con una nota corta del patrón usado.

Este criterio aplica a **toda ruta nueva** antes de mergear, y a **toda ruta
existente** cada vez que se la toca. El wrapper `<PublicLayout>` provee TopBar
y Footer mobile-aware, pero **no garantiza el criterio** — el contenido de
cada página tiene que cumplirlo por su cuenta.

## Superficie mobile

No todo se renderiza en mobile. El criterio de triage:

- ✅ **Renderiza y funciona bien** → no tocar salvo regresión.
- ⚠️ **Renderiza pero con problemas** → fix o decisión de ocultar.
- ❌ **No renderiza** → fuera del scope mobile (no crear issues).

| Componente / Sección | Estado mobile | Notas |
|---|---|---|
| MobileStickyBar | ✅ solo mobile | Fechas + búsqueda + filtros |
| TopBar mobile | ✅ logo centrado + icono usuario | |
| EquipmentRow (list) | ✅ thumb cuadrado, precio inline | |
| EquipmentCard (grid) | ✅ 2 cols mobile | Responsive utils a revisar (#5) |
| RentalDateModal | ✅ `h-[100dvh]` | |
| CartDrawer | ✅ full-width | |
| CategoryMosaic | ✅ renderiza | |
| Footer | ✅ mobile compacto | |
| BrandCarousel | ❌ oculto (`hidden sm:block`) | Ocultado mayo 2026 — no queda bien sin flechas |
| CarouselRow arrows | ❌ `hidden sm:flex` | El contenido del carrusel puede ser visible |
| ListFilters (panel) | ❌ `hidden md:block` | En mobile usa MobileFiltersSheet |
| TopBar pill de fechas | ❌ `hidden md:flex` | En mobile está en MobileStickyBar |
| TopBar acciones desktop | ❌ `hidden md:flex` | |
| Footer desktop | ❌ `hidden md:block` | |
| Precio columna desktop | ❌ `hidden sm:block` | En mobile está inline |

---

## Label `mobile`

Todos los issues relacionados con la experiencia mobile llevan la label
`mobile` en GitHub. Alcance:

- ✅ Incluye: rutas y componentes del cliente (`/`, `/equipo/*`, `/cliente/*`, `/estudio`)
- ✅ Incluye: `/admin/pedidos`, `/admin/dashboard` (el dueño los usa desde el celu)
- ❌ Excluye: el resto del admin por ahora

Ver convención completa en `docs/ISSUE_LABELS.md`.

```bash
gh issue list --state open --label "mobile"
```

---

## Cómo evaluar contra el criterio

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
| Login cliente | `/cliente/login` | 🟡 Verificar | Funciona por defecto pero sin responsive utils explícitas. |
| Registro cliente | `/cliente/registro` | 🟢 OK | Form en card centrada `max-w-sm`, `grid-cols-1 sm:grid-cols-2`, submit `w-full py-2.5`. Regla CSS global cubre anti-zoom iOS. Code audit confirma 🟢. |

### Admin (prioritario mobile)

| Página | URL | Status | Notas |
|---|---|---|---|
| Pedidos | `/admin/pedidos` | 🔴 Pendiente | Lista y detalle de pedidos desde celu |
| Dashboard | `/admin/dashboard` | 🔴 Pendiente | KPIs desde celu |

### Portal cliente

| Página | URL | Status | Notas |
|---|---|---|---|
| Lista de pedidos | `/cliente/portal` | 🟢 OK | Acordeón expandible por pedido. |
| Perfil | `/cliente/perfil` | 🟢 OK (mobile) | Header sticky + sub-header amarillo + form `grid-cols-1 sm:grid-cols-2`. Nombre/apellido tienen `text-base sm:text-sm` explícito. Submit `w-full py-3` (~48px). **Nota**: tiene drift de chrome (issue #256) — el patrón mobile per se está bien. |

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

## Re-auditar cuando (gate de merge)

Esta sección define **cuándo no se puede mergear** sin haber validado mobile:

- **En cada PR** que toque rutas cliente, `/admin/pedidos` o `/admin/dashboard`
  (gate explícito de merge — ver PROTOCOLO.md Fase 1.5). Sin auditoría mobile
  validada, el PR queda en draft.
- Se agregue una página nueva → agregarla a la tabla de páginas, evaluarla
  contra el criterio, marcar 🟢/🟡/🔴.
- Se cambie el diseño de TopBar, Cart, DateModal o Footer (componentes
  globales) — re-validar todas las rutas que los usan.
- Se actualice Tailwind o shadcn (puede romper sizing).
- Antes de cada deploy a producción si hubo cambios de UI.
- Como rutina general: cada 2-4 semanas.

Mantener este doc actualizado con cada fix.
