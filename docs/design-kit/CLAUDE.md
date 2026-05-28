# Rambla Rental — Design System Reference for Claude Code

This file is the authoritative quick-reference for everything UI/design in this repo.
Read this before touching any component, page, or stylesheet.

Full visual docs: `docs/design-kit/index.html` + `docs/design-kit/extended.html`.
Pattern specimens: `docs/design-kit/patterns/*.html`.

---

## Your scope (Claude Code)

**You touch:** design system, UI components, styles, layouts, copy in `.tsx` views, micro-interactions, Tailwind classes, `kit/` folder.

**You do NOT touch:**
- `backend/` (Express, Postgres, migrations, controllers)
- `src/lib/api.ts`, `src/lib/auth.ts`, `src/lib/iva.ts`, `src/hooks/use*.ts` data layer
- `/api/*` routes anywhere
- `scripts/*`, `tools/*`, `playwright.config.ts`, `vite.config.ts`, `Dockerfile`
- `src/data/equipment.ts` types (read-only for you — backend changes them)

If a UI task needs backend changes (new endpoint, new field, schema), **say so and stop**. Don't invent stubs.

---

## Stack

- **Framework**: TanStack Router + React 19 (Vite)
- **Styling**: Tailwind v4 with `@theme inline` — single source of truth: `src/styles.css`
- **Fonts**: TT Commons (primary, weights 400/500/600/700) + Champ Black (900, display only) — shipped locally in `src/assets/fonts/`. JetBrains Mono via CDN in `index.html`.
- **Icons**: Lucide React — `import { X } from "lucide-react"` (individual imports). Stroke width 1.5 default, sized via `h-* w-*` Tailwind utilities.
- **State**: Zustand for cart + fly-to-cart (`src/lib/*-store.ts`)
- **Anim**: Framer Motion for transitions that need it

---

## Color tokens (from `src/styles.css`)

| Token | Value | Use |
|---|---|---|
| `--amber` | `#FAB428` | Brand accent — Pantone 1235 C. **Never alter.** |
| `--amber-soft` | `amber at 18% opacity` | Hover bg, focus ring fill |
| `--amber-hot` | `#FFCC55` | Light step for `bg-amber-tape` signature stripes |
| `--ink` | `oklch(0.14 0.01 60)` | Primary text, buttons, UI |
| `--ink-pure` | `#000` | Hero display text, print |
| `--foreground` | `oklch(0.18 0.01 60)` | Body text (slightly lighter than ink) |
| `--background` | `oklch(0.985 0.005 90)` | Page bg (warm near-white "hueso") |
| `--surface` | `oklch(0.97 0.008 85)` | Cards, panels |
| `--surface-elevated` | `oklch(1 0 0)` | Elevated cards, inputs |
| `--hairline` | `oklch(0.18 0.01 60 / 12%)` | Borders, dividers |
| `--muted-foreground` | `oklch(0.42 0.01 70)` | Secondary text |
| `--verde` | `#009971` | Success, Confirmado · Pantone 7724 C |
| `--azul` | `#1097DB` | Info, Presupuesto · Pantone 299 C |
| `--naranja` | `#E9552F` | Warning · Pantone 172 C |
| `--rosa` | `#ED7BAD` | Accent 5 · Pantone 211 C |
| `--destructive` | `oklch(0.62 0.22 27)` | Errors, Cancelado, delete |
| `--ring` | `amber at 60%` | Focus ring |

**Charts order (always):** amber → azul → naranja → verde → rosa.
Use `var(--chart-1)` … `var(--chart-5)` — they alias the colors above.

**Dynamic vars** (set by JS at runtime, read-only in CSS):
- `--amber-pct` (0%–100%) — topbar amber scroll progress (see TopBar pattern)
- `--cart-strip-h` — cart strip presence height

---

## Z-index scale

Use these names. Do not invent.

| Token | Value | Use |
|---|---|---|
| `--z-sub-toolbar` | 30 | Sub-sticky toolbars (filter row in catalog list) |
| `--z-cat-bar` | 40 | Category tabs sticky bar |
| `--z-cart-strip` | 45 | Cart status strip (between cat-bar and topbar) |
| `--z-topbar-amber` | 49 | Topbar amber layer (under topbar) |
| `--z-topbar` | 50 | Topbar |
| `--z-scrim` | 60 | Drawer scrim, fly-to-cart layer |
| `--z-drawer` | 61 | Drawers, modals |

**Note:** Fly-to-cart `+1` pill uses `z-[60]` Tailwind class directly (matches `--z-scrim`).

---

## Typography

```css
/* Display — Champ Black 900. Hero showpieces + wordmark only. */
.t-display-1   /* clamp(3.5rem, 9vw, 8.5rem)   · lh 0.9 · lowercase */
.t-display-2   /* clamp(2.25rem, 5vw, 4rem)    · lh 1.0 · lowercase */

/* Headings — TT Commons */
.t-h1          /* 30px · w700 */
.t-h2          /* 24px · w700 */
.t-h3          /* 18px · w600 */

/* Body */
.t-body        /* 16px · lh 1.55 */
.t-small       /* 14px · muted */

/* Mono — JetBrains Mono */
.t-eyebrow     /* 10px · tracking 0.25em · uppercase · muted */
.t-mono        /* tabular-nums */

/* Wordmark — Champ Black + lowercase + tracking 0.01em */
.wordmark
```

**Rules:**
- Champ Black ONLY for `.t-display-*`, `.wordmark`, hero showpieces. Everything else is TT Commons.
- Display text: always `text-transform: lowercase`. UI headings: Title Case.
- Always close taglines/heros with a period. No `!`, no `…`.

---

## Spacing & sizing

**No `--space-*` tokens exist.** Use Tailwind directly:
- `p-2` (8px), `p-3` (12px), `p-4` (16px), `p-6` (24px), `p-8` (32px), `p-12` (48px)
- `gap-2`, `gap-3`, `gap-4`, `gap-6` for flex/grid
- Container: `max-w-7xl mx-auto px-4 lg:px-12`

Touch targets minimum `min-h-[44px] min-w-[44px]` on mobile interactive elements.

---

## Shadows

**No `--shadow-*` tokens exist.** Use Tailwind inline arbitrary values for signature shadows:

```tsx
/* CartMiniBar bottom-fixed — sombra hacia arriba */
className="shadow-[0_-8px_32px_-8px_rgba(0,0,0,0.15)]"

/* CartMiniBar hover preview — sombra suave hacia arriba */
className="shadow-[0_-12px_24px_-8px_rgba(0,0,0,0.08)]"

/* Cards, dropdowns — Tailwind defaults */
className="shadow-sm"   /* cards en reposo */
className="shadow-md"   /* dropdowns, popovers */
className="shadow-lg"   /* drawers, modales */
```

---

## Motion

**No `--duration-*` or `--ease-*` tokens.** Inline:
- Snappy settle: `transition duration-150 ease-out` (most UI)
- Slow / hero: `duration-300 ease-out`
- Framer Motion easing for fly-to-cart: `[0.22, 1, 0.36, 1]` (signature)
- Framer Motion pop: `scale: [1, 1.25, 0.95, 1]`, `duration: 0.45`, `ease: "easeOut"`

Keyframes defined in `styles.css`:
```css
@keyframes expand-in { /* opacity + translateY -6→0 */ }
@keyframes slide-up  { /* translateY 100%→0 — for drawers */ }
```

---

## Radii

`--radius: 0.75rem` (12px) is the base. Derived:
- `--radius-sm` 8px · `--radius-md` 10px · `--radius-lg` 12px
- `--radius-xl` 16px · `--radius-2xl` 20px · `--radius-3xl` 24px · `--radius-4xl` 28px

Use Tailwind: `rounded-sm`, `rounded`, `rounded-lg`, `rounded-xl`, `rounded-2xl`, `rounded-full`.

---

## Custom utilities (defined in `styles.css`)

| Utility | What it does |
|---|---|
| `.hairline` | `border-color: var(--hairline)` — pair with `border` for 1px hairline |
| `.bg-amber-tape` | Diagonal amber stripes (`amber` ↔ `amber-hot`, 24px each) — signature pattern |
| `.wordmark` | Champ Black + lowercase + tracking 0.01em + line-height 0.9 |
| `.grain` | `::before` overlay with subtle radial-dot noise (use on hero bg) |
| `.tabular` | `font-variant-numeric: tabular-nums` (prices, dates, counts) |
| `.text-balance` | `text-wrap: balance` for headlines |
| `.safe-t` / `.safe-b` / `.safe-x` | `padding: env(safe-area-inset-*)` — for sticky bars near notch/home-bar |
| `.font-display` / `.font-mono` | Family helpers (already mapped via `@theme inline`) |

**Logo / seal classes** (used inside the SVG `<Logo>`):
- `.topbar-seal .seal-badge` — the amber R-badge background
- `.topbar-seal .seal-r` — the bone "R" inside
- When `.topbar-snap` is on, colors swap (badge → bone, R → amber)

---

## Components — APIs

### Button
```tsx
import { Button } from "@/components/ui/button";
// variants: "primary" | "secondary" | "ghost" | "amber" | "destructive"
// sizes:    "default" | "sm" | "lg" | "icon"
<Button variant="primary" size="lg">Reservar</Button>
```

### TopBar
```tsx
import { TopBar } from "@/components/rental/TopBar";
// variant: "default" (catálogo) | "cliente" (portal)
// amberOnScroll: true → reads --amber-pct, snaps at 65%
<TopBar amberOnScroll />
```

### CartMiniBar
```tsx
import { CartMiniBar } from "@/components/rental/CartMiniBar";
// Mount once near the root of catalog pages. Reads cart store.
// The data-cart-icon attribute on its icon is the landing target
// for the FlyToCartLayer's +1 animation.
<CartMiniBar allEquipos={allEquipos} />
```

### FlyToCartLayer
```tsx
import { FlyToCartLayer } from "@/components/rental/FlyToCartLayer";
// Mount once. Listens to fly-to-cart-store.
// Triggers: useFlyToCart().triggerFly({ x, y }) from any "Agregar" button.
<FlyToCartLayer />
```

### EstadoBadge
```tsx
// estados: borrador | presupuesto | solicitado | confirmado |
//          retirado | devuelto | cancelado | perdido | atrasado
<EstadoBadge estado="confirmado" />
```

---

## Patterns (see `docs/design-kit/patterns/`)

| Pattern | Where it lives | Snap / canonical values |
|---|---|---|
| **TopBar amber-on-scroll** | `TopBar.tsx` + `routes/index.tsx` | Snap at **65%** of `--amber-pct`. Logo gets `[filter:brightness(0)_invert(1)]`. Date pill → `bg-background border-background/80`. Cart btn → `bg-ink text-amber`. |
| **CartMiniBar bottom-fixed** | `CartMiniBar.tsx` | `border-t-2 border-amber/60`, `bg-background/98`, `shadow-[0_-8px_32px_-8px_rgba(0,0,0,0.15)]`, `backdrop-blur-xl`, `pb-[max(0.75rem,env(safe-area-inset-bottom))]`. Hover preview uses `group/cart` + `group-hover/cart` Tailwind groups. |
| **Chip Rail overflow** | `routes/index.tsx` (list mode only) | `overflow-x-auto scrollbar-none`, `shrink-0` on all chips + label. Active state: `border-amber/60 bg-amber/15 font-semibold`. Real chips: `["Pack boda", "Pack entrevista", "Sony FX3", "Aputure 600d", "RØDE NTG", "Pack 3 LEDs", "Manfrotto"]`. |
| **Fly-to-cart +1** | `FlyToCartLayer.tsx` + `fly-to-cart-store.ts` | Pill `h-9 w-9` amber + `ring-2 ring-amber/40`, `z-[60]`. Curva canónica: `[0.22, 1, 0.36, 1]`, `duration: 0.55`. Pop al recibir: `scale: [1, 1.25, 0.95, 1]`, `duration: 0.45`, `easeOut`. Triggered via `useFlyToCart().triggerFly({ x, y })`. |

---

## Data formatting

Use the helpers in `src/lib/format.ts`. Never format manually.

```ts
formatARS(24500)        // → "$ 24.500"
formatARS(2840500)      // → "$ 2.840.500"
formatRentalRange(s, e) // → "lun 2 → jue 5 jun."
```

---

## Mobile — critical rules

```tsx
{/* In index.html <head> — already there */}
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
```

```css
/* In styles.css — already there */
@media (max-width: 767px) {
  input, textarea, select { font-size: max(16px, 1em); } /* no iOS zoom */
}
* { -webkit-tap-highlight-color: transparent; }
```

For your components:
- Use `.safe-t` / `.safe-b` on any sticky bar near the notch/home-bar
- Use `100dvh` not `100vh` for full-screen panels
- `min-h-[44px] min-w-[44px]` on tappable elements
- `overscroll-behavior: contain` on drawers / bottom sheets

---

## Voice & tone (copy)

- **Always "vos"** — reservá, elegí, confirmá. Never "usted" or "tú".
- **Lowercase** for wordmark, taglines, heroes. Normal Title Case for UI headings.
- **Period at end** of taglines and hero titles. No `!`, no `…`.
- **Prices**: `$ 24.500` (`$` + space + dot separator).
- **Dates**: `lun 2 jun.` short. `lun 2 → jue 5 jun.` ranges.
- **Jornadas**: `3 J` compact (cards), `3 jornadas` full.
- **Errors**: first person, specific. `"Ingresá un correo válido."` not `"Error: email inválido"`.
- **Empty states**: actionable. `"No hay equipos para estas fechas."` not `"Sin resultados"`.
- **Hero taglines** (one chosen randomly per visit, in `lib/hero-taglines.ts`): `"rental, estudio, rambla."` · `"con rambla, en mardel."` · `"en rambla, tu proyecto."` · `"en rambla, tu rodaje."`.

---

## Dark mode

Activate with `.dark` class or `data-theme="dark"` on `<html>`.
The `:root` and `.dark` blocks in `styles.css` swap `--background`, `--foreground`, `--surface`, `--hairline`, `--card`, `--muted`, `--primary`.
**`--amber` stays as-is in both modes** — accent never changes.

---

## Patterns to NEVER break

1. **Never substitute TT Commons / Champ Black with Google fonts.** They ship locally in `src/assets/fonts/`.
2. **Champ Black is display-only** — never headings, never UI labels.
3. **Never hardcode hex colors** in `.tsx` files. Use Tailwind utilities (`text-amber`, `bg-ink`) or CSS vars (`var(--amber)`).
4. **`strokeWidth={1.5}` on all Lucide icons** unless overridden by `<Logo>` or a one-off intentional.
5. **Import Lucide individually** — never `import * from "lucide-react"`.
6. **All prices through `formatARS()`** — never `n.toLocaleString()` ad-hoc.
7. **`dvh` not `vh`** for full-height panels on mobile.
8. **`viewport-fit=cover` + `.safe-*` utilities** on any sticky top/bottom bar.
9. **`var(--amber)` is `#FAB428` — Pantone 1235 C. Never alter.** This is in the brand book.
10. **Don't invent new tokens.** If a value isn't here, look in `src/styles.css`. If still not there, use an inline Tailwind arbitrary value and add a comment why.

---

## When you're not sure

- Open the relevant pattern specimen: `docs/design-kit/patterns/*.html`.
- Open `docs/design-kit/index.html` for visual tokens & components.
- Open `docs/design-kit/extended.html` for mobile, micro-interactions, copy rules, dataviz, etc.
- If the design system disagrees with what's in the repo, **the repo wins** (this doc may drift). Flag the drift in the PR.
