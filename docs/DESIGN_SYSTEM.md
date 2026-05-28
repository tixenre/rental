# Design System — Rambla Rental

> **Esta es la referencia canónica del design system del repo.** Lo que
> está acá vale para cualquier código en `src/`. Si una pantalla nueva
> tiene que decidir un color, un tamaño tipográfico, un radio, una
> animación o un texto — empezás acá.
>
> El **kit portable** (`docs/design-kit/`) es un export de Claude Design
> pensado para llevar el look a otros proyectos. **No es la fuente de
> verdad de este repo.** Cuando el kit y este doc difieren, manda este
> doc + `src/styles.css` (ver "Source-of-truth ladder" más abajo).

---

## Stack real

- **Frontend:** Vite + React 19 + TanStack Router + Tailwind v4 +
  shadcn/Radix UI + lucide-react. **NO Next.js**, aunque el CLAUDE.md del
  kit lo diga.
- **Backend:** FastAPI + PostgreSQL en Railway.
- **Fonts:** TT Commons (primary, full axis) + Champ Black (display only)
  vendoreadas en `src/assets/fonts/`. JetBrains Mono desde Google Fonts.
- **Iconos:** lucide-react, import individual, `strokeWidth` por default
  (no forzamos 1.5 — el kit lo recomienda; en producción mezclamos 2 que
  shadcn usa con 1.5 en piezas branded).
- **Locale:** Spanish (Argentina). Currency: ARS via `formatARS()` de
  `src/lib/format.ts`.

---

## Tokens en `src/styles.css`

### Colores (lo que hay hoy)

| Token | Valor | Uso |
|---|---|---|
| `--amber` | `#FAB428` | Brand accent, hero bg, hover highlight |
| `--amber-soft` | `amber @ 18%` | Tinted bg, focus ring fill |
| `--amber-hot` | `#FFCC55` | Paso claro para amber-tape pattern |
| `--ink` | `oklch(0.14 0.01 60)` | Primary text, buttons, body |
| `--ink-pure` | `#000000` | Hero display text, print |
| `--background` (bone) | `oklch(0.985 0.005 90)` | Page background |
| `--surface` | `oklch(0.97 0.008 85)` | Cards, panels |
| `--surface-elevated` | `oklch(1 0 0)` | Elevated cards, inputs, modales |
| `--hairline` | `ink @ 12%` | Borders, dividers |
| `--muted-foreground` | `oklch(0.42 0.01 70)` | Secondary text, eyebrows |
| `--rosa` | `#ED7BAD` | Status palette |
| `--azul` | `#1097DB` | Status palette (Presupuesto) |
| `--verde` | `#009971` | Status palette (Confirmado) |
| `--naranja` | `#E9552F` | Status palette (Warning) |
| `--destructive` | `oklch(0.62 0.22 27)` | Errors, delete, Cancelado |

**Regla del color (single-accent discipline):** la página es **bone + ink
+ amber**. La paleta secundaria (rosa/azul/verde/naranja) **sólo** para
status de pedido y gráficos — nunca en superficies de marketing.

**Orden de gráficos** (siempre): amber → azul → naranja → verde → rosa.

Las utilities Tailwind correspondientes (`bg-amber`, `text-ink`,
`border-hairline`, `bg-rosa/10`, etc.) las genera Tailwind v4 directo de
estos tokens vía el bloque `@theme inline` al inicio de `src/styles.css`.

### Tipografía

```css
--font-display: "Champ Black", "TT Commons", ui-sans-serif, ...;
--font-sans:    "TT Commons", ui-sans-serif, -apple-system, ...;
--font-mono:    "JetBrains Mono", ui-monospace, monospace;
```

**Reglas:**
- **Champ Black** = SÓLO para hero taglines (`.t-display-1`/`.t-display-2`)
  y el `.wordmark` del logo. Headings de UI, body, labels → TT Commons.
- **Display text siempre `lowercase`**. *"un lugar donde pasan cosas."*
- **Headings de UI** en Title Case normal con TT Commons.
- **Eyebrows / chrome / numbers** → JetBrains Mono, uppercase, tracking
  ancho. *`CATÁLOGO · 187 EQUIPOS · MAR DEL PLATA`*.
- **Numbers** tabulares siempre que aparezcan (precios, fechas, counts,
  IDs). Tailwind: `tabular-nums` o nuestra utility `.tabular`.

### Radii

```css
--radius:     0.75rem  /* base = 12px */
--radius-sm:  8px      /* inputs, chips chicos */
--radius-md:  10px     /* buttons, icon containers */
--radius-lg:  12px     /* cards (default) */
--radius-xl:  16px     /* feature blocks */
--radius-2xl: 20px     /* studio CTA hero */
--radius-3xl: 24px     /* — */
--radius-4xl: 28px     /* — */
/* + rounded-full = 9999px para pills, filter chips, CTAs */
```

### Z-index (project-specific, NO el genérico del kit)

```css
--z-topbar:       50  /* TopBar sticky */
--z-topbar-amber: 49  /* Variante amber-on-scroll del topbar */
--z-scrim:        60  /* Overlays (cart drawer, modal scrim) */
--z-drawer:       61  /* Drawer/sheet contents sobre el scrim */
--z-cart-strip:   45  /* Cart mini bar bottom-fixed */
--z-cat-bar:      40  /* Category bar sticky */
--z-sub-toolbar:  30  /* Sub-toolbar (search + filters bajo el topbar) */
```

> **No usamos** el ladder genérico del kit (`--z-raised/dropdown/sticky/modal/toast/tooltip`).
> Si una pantalla nueva necesita un z-index, primero mirá si hace match
> con alguno de los siete arriba — `--z-scrim` y `--z-drawer` son los más
> reusables.

### Tokens que el kit documenta y NO existen en el repo hoy

El bundle v3 del kit documenta:
- **Spacing scale** (`--space-1`…`--space-24`)
- **Shadow scale** (`--shadow-sm/md/lg/xl`)
- **Motion** (`--duration-fast/base/slow/xslow`, `--ease-default/out/bounce`)

**Estos NO están en `src/styles.css` hoy.** Para spacing usamos Tailwind
defaults (`gap-4`, `p-6`); para shadow usamos `shadow-sm`/`shadow-md`/etc.
de Tailwind; para motion usamos `transition-colors duration-150` y
`framer-motion` directo. Agregar estos tokens es una iniciativa
pendiente (PR C del plan del kit) — cuando entren, este doc se actualiza.

---

## Recipes tipográficas

Defined as utility classes en `src/styles.css`:

```
.t-display-1   /* Champ Black, clamp(56px, 9vw, 128px), lh 0.88, lowercase */
.t-display-2   /* Champ Black, clamp(40px, 6vw, 72px), lh 0.92 */
.t-h1          /* TT Commons 700, 30px */
.t-h2          /* TT Commons 700, 24px */
.t-h3          /* TT Commons 600, 18px */
.t-body        /* TT Commons 400, 16px, lh 1.55 */
.t-small       /* TT Commons 400, 14px, muted */
.t-eyebrow     /* JetBrains Mono 500, 10px, tracking 0.25em, uppercase, muted */
.tabular       /* font-variant-numeric: tabular-nums */
.wordmark      /* Champ Black, lowercase, tracking -0.01em */
.grain         /* dot-grain texture overlay ~40% opacity */
```

---

## Componentes — ubicaciones canónicas

| Categoría | Dónde vive | Notas |
|---|---|---|
| **Primitivas UI** (Button, Input, Card, Dialog, …) | `src/components/ui/*` | shadcn/Radix base. Naming shadcn (`variant="default"`, no `"primary"`). |
| **Componentes de aplicación (`rental/`)** | `src/components/rental/*` | EquipmentCard, TopBar, Footer, CartMiniBar, EstadoBadge integrados con queries + estado. |
| **Componentes admin** | `src/components/admin/*` | Tablas, modales, sidebar del back-office. |
| **Kit portátil ports** | `src/components/kit/*` (llegará con PR #577) | Versiones presentacionales del kit. Pensados para convivir con los integrados. |

### Button (`src/components/ui/button.tsx`)

```tsx
import { Button } from "@/components/ui/button";

// variants: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link" | "amber"*
// sizes:    "default" (h-9) | "sm" (h-8) | "lg" (h-10) | "icon" (h-9 w-9)
// shape:    "rounded" (default) | "pill"*
//   * agregados por la iniciativa del kit (PR #577 cuando merge)

<Button variant="default">Reservar</Button>
<Button variant="amber" shape="pill" asChild><a href="/estudio">→</a></Button>
```

> **No renombrar `default` a `primary`** — eso rompería decenas de
> `<Button variant="default">` que existen hoy. La signature de marca
> (`amber` + `pill`) entra como **adición**, no como reemplazo.

### EstadoBadge

Hoy en producción vive una sola versión: `src/components/rental/EstadoBadge.tsx`,
integrada con la lógica de pedido y usa `bg-blue-50` genérico.

Cuando merge PR #577, va a sumarse en paralelo `src/components/kit/EstadoBadge.tsx`
— versión presentacional con la paleta secundaria de marca
(`bg-azul/10`, `bg-verde/10`, …). Issue #575 mapea la migración
componente-por-componente de la integrada al look del kit, una pantalla
por vez.

### Otros componentes del kit (cuando merge PR #577)

PR #577 va a traer al repo, bajo `src/components/kit/`, las versiones
presentacionales de:

- `AddonPills` — items "incluye" sobre rows de equipo.
- `EmptyState` — pattern "nada para mostrar".
- `PriceBlock` — precio + tarifa display.
- `ViewToggle` — segmented control con pill deslizante.
- `StatCard` — número grande para dashboards.
- `Input` + `SearchInput` + `FieldLabel` — variantes branded de inputs.

También va a montar una ruta pública sin login `/kit-preview` que los
muestra todos para QA visual.

Hasta entonces, la referencia visual viva está en `docs/design-kit/preview/*.html`
(specimens del kit portable) y en `docs/design-kit/index.html` (showcase).

---

## Mobile — reglas críticas

```html
<!-- 1. viewport-fit=cover siempre -->
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```

```css
/* 2. Safe areas — usar env(safe-area-inset-*) */
.topbar      { padding-top: env(safe-area-inset-top); }
.bottom-bar  { padding-bottom: calc(0.75rem + env(safe-area-inset-bottom)); }
.cart-drawer { max-height: 85dvh; padding-bottom: env(safe-area-inset-bottom); }

/* 3. Tap highlight transparente — usar el del :active propio */
* { -webkit-tap-highlight-color: transparent; }

/* 4. Anti-zoom de iOS — inputs ≥ 16px */
input, textarea, select { font-size: max(16px, 1em); }

/* 5. Drawer overscroll — no propagar el scroll del body */
.cart-drawer, .bottom-sheet { overscroll-behavior: contain; }

/* 6. Full-height usar dvh, no vh */
.modal, .full-screen { height: 100dvh; }
```

**Touch targets:** mínimo 44×44px en cualquier elemento interactivo. Si
un chip es chico, extendé el hit area con `padding` o pseudo-element
`::before`, no agrandés el chip visible.

**Thumb zone:** los CTAs primarios (Reservar, Confirmar, Agregar)
**en la mitad inferior** de la pantalla. Nunca en el top 22% — ahí va
chrome y navegación, no acciones críticas.

---

## Focus y accesibilidad

```css
/* Siempre :focus-visible, nunca :focus crudo */
:focus-visible {
  outline: 3px solid var(--amber);
  outline-offset: 2px;
}
input:focus-visible, textarea:focus-visible {
  outline: none;
  border-color: var(--amber);
  box-shadow: 0 0 0 3px var(--amber-soft);
}
```

**Contraste WCAG:**
- ink sobre amber = 7.2:1 (AAA)
- amber sobre ink = 7.2:1 (AAA)
- ink sobre bone = 16.4:1 (AAA)

Los tres pares principales pasan AAA con holgura. No hay excusa para
romperlos — si un texto no se lee, usá `ink` sobre lo que sea.

---

## Micro-interactions

```css
/* Press state — todos los buttons */
button:active {
  transform: scale(0.97);
  transition: transform 120ms cubic-bezier(0.32, 0.72, 0, 1);
}

/* Card hover interactivo — usá la utility Tailwind hoy. Cuando exista el
   token --shadow-md en src/styles.css, podés switchear a box-shadow: var(--shadow-md). */
.card-interactive:hover {
  transform: translateY(-2px);
  @apply shadow-md;
}

/* Stagger en grid de catálogo */
.catalog-grid > *:nth-child(n) {
  animation-delay: calc(n * 40ms);
}
```

**Reverse signature (ink ↔ amber):** los botones primarios de marca
(`variant="amber"` o el `default` cuando se hace el upgrade) invierten
fondo y texto en hover. *"Pasa el mouse y se prende."*

**Cart count bump:** cuando se agrega un equipo al carrito, el badge del
contador hace `scale [1, 1.25, 0.95, 1]` (ease bounce, ~200ms). Spec
real en `src/components/rental/CartMiniBar.tsx`.

**+1 fly to cart:** específico de Rambla, documentado en el specimen
`docs/design-kit/preview/patterns-fly-to-cart.html`. Componente
implementado: `src/components/rental/FlyToCartLayer.tsx`. Curva canónica
`cubic-bezier(0.22, 1, 0.36, 1)`, duración 550ms.

**TopBar amber-on-scroll:** específico de Rambla, specimen en
`docs/design-kit/preview/patterns-topbar-amber-scroll.html`.
Mecánica: CSS variable `--amber-pct` calculada por la página, el header
hace `color-mix(in oklch, amber X%, background 92% alpha)`. Snap a 65%
del progreso del hero invierte logo + date pill + user button.

---

## Voz y tono (copy rules)

- **Siempre "vos"** (voseo rioplatense). *Reservá, elegí, confirmá.*
  Nunca *usted*, nunca *tú*.
- **Minúsculas en wordmark, taglines y heroes.** Title Case normal en
  headings de UI.
- **Punto final en taglines y titulares de hero.** No `!`, no `…`.
  *"un lugar donde pasan cosas."*
- **Precios:** `$ 24.500` ($ con espacio, punto como separador de
  miles). Siempre vía `formatARS()`.
- **Fechas:** `lun 2 jun.` (formato corto), `lun 2 → jue 5 jun.` (rangos).
- **Jornadas:** `3 J` (compact en cards), `3 jornadas` (full).
- **Errores:** específicos y en primera persona del usuario.
  *"Ingresá un correo válido."* (no *"Error: email inválido"*).
- **Empty states:** accionables. *"No hay equipos para estas fechas."*
  (no *"No se encontraron resultados"*).
- **Sin emoji** en UI de producción. Excepciones (como glifos, no como
  emoji): `✨` via `<Sparkles />` de lucide en el badge addon; `★` literal
  en "destacado".

---

## Skeleton / loading

```css
.skeleton {
  background: linear-gradient(90deg,
    var(--surface) 25%,
    var(--surface-elevated) 50%,
    var(--surface) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease infinite;
  border-radius: var(--radius-sm);
}

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

**Regla:** el skeleton **espeja el layout del componente real** para no
generar CLS (Content Layout Shift) al hidratar.

---

## Dark mode

El repo ya tiene tokens semánticos (`--background`, `--surface`,
`--foreground`, etc.) que auto-switchean con la clase `.dark` o
`data-theme="dark"` en `<html>`. **Amber se queda como accent en ambos
modos** — no se ajusta.

Hoy la app **no expone un toggle** público de dark mode (la mayoría del
contenido es bone + amber por diseño). Si se agrega, no requiere
adaptar componentes que ya usan los tokens semánticos correctamente.

---

## Print

```css
@media print {
  .nav, .topbar, .sidebar, [data-no-print] { display: none !important; }
  body { background: white; color: #000000; font-size: 11pt; }
  .wordmark { color: #FAB428; }
  @page { margin: 20mm; size: A4; }
}
```

Útil para presupuestos / remitos / contratos que el dueño imprime
ocasionalmente.

---

## Patterns que nunca se rompen

1. **Nunca un substitute de Google Fonts para TT Commons o Champ Black.**
   Las fuentes vendoreadas en `src/assets/fonts/` son las del manual oficial
   de marca.
2. **Champ Black sólo para display.** No para headings de UI, no para
   labels, no para body, no para botones.
3. **Nunca hardcodear hex.** Siempre `var(--amber)`, `bg-amber`,
   `text-ink`. Si el color que necesitás no tiene token, hablalo antes
   de inventar.
4. **Lucide icons individualmente.** `import { Camera, Search } from
   "lucide-react"` — nunca `import * from "lucide-react"`. Tree-shaking
   funciona pero el patrón individual es más explícito.
5. **Todos los precios vía `formatARS()`.** Nunca formato manual con
   `.toLocaleString()` ad-hoc.
6. **`dvh` no `vh`** para elementos full-height en mobile. iOS Safari
   redimensiona el viewport con la barra de URL — `vh` salta, `dvh` no.
7. **`viewport-fit=cover` + `env(safe-area-inset-*)`** en toda pantalla
   con topbar o bottom bar sticky.
8. **El core de reservas es sagrado** (MEMORIA: barra de calidad).
   Cero overlap de pedidos; cualquier cambio en disponibilidad pasa por
   el motor de reservas existente, no se reimplementa.

---

## Source-of-truth ladder (cuando algo está en varios lados)

1. **`src/styles.css`** — los tokens que el build de producción usa.
   Si Tailwind v4 genera `bg-amber` es porque `--color-amber` vive acá.
2. **`src/components/*`** — los componentes que renderean en producción.
3. **Este doc (`docs/DESIGN_SYSTEM.md`)** — explica el por qué.
4. **`docs/design-kit/` (showcase + kit portable)** — referencia visual
   y exportable. Puede driftear; cuando difiere con (1)/(2)/(3), pierde.

En cada PR de UI: si tocás algo en (1) o (2), tocá también (3) y (4) si
corresponde. El supervisor cuida que no quede drift silencioso.

---

## Cómo leer este doc

- **Sos un dev que va a tocar UI**: leé "Tokens", "Componentes", la
  sección del componente que vas a tocar, y "Patterns que nunca se
  rompen" antes de empezar.
- **Sos PM/diseñador iterando en Claude Design**: leé "Voz y tono",
  "Mobile rules", el specimen relevante en `docs/design-kit/preview/*`.
- **Sos sesión de Claude Code arrancando**: leé "Stack real", "Tokens",
  "Patterns que nunca se rompen", y `docs/MEMORIA.md` para criterio.

Si dudás cómo aplicar algo, leé el código real en `src/components/*` —
casi siempre hay un ejemplo vivo.
