# Rambla Rental — Design System

A practical, branded design system for **Rambla Rental**, an audiovisual
equipment rental platform based in **Mar del Plata, Argentina**. The system
is rebuilt from the live `tixenre/rental` codebase plus the official Rambla
brand manual (`uploads/RAMBLA branding.pdf`).

> *"un lugar donde pasan cosas."* — the brand line, used as page hero on the
> public catalog.

---

## ⚠ Source-of-truth ladder (read before porting components)

Claude Design exports each component in two formats — and they can drift.
Order of authority when integrating into `src/components/*`:

1. **`index.html`** (the showcase landing). This is the canonical visual
   contract. When in doubt, this wins.
2. **`preview/components-*.html`** (per-component specimens). Detailed
   demos. Usually agree with the showcase, but can be older drafts. If
   they disagree with the showcase, the showcase wins.
3. **`kit/components/*.tsx`** (the React export). **Treat as draft.**
   Useful as a starting point for the port, but verify against the HTML
   above before trusting any class. The TSX can have silent drift —
   e.g. ViewToggle exported `rounded-full` while the showcase + specimen
   both draw it boxy.

When the TSX drifts from the HTML, fix the port in `src/components/*` to
match the HTML and leave `docs/design-kit/kit/*` untouched (it's a snapshot
of one Claude Design generation; the next regeneration corrects it).

See `docs/MEMORIA.md → 2026-05-28` for the full decision.

---

## What is Rambla?

Rambla Rental is a small/medium audiovisual rental house: cameras, lenses,
lighting, audio, supports, and a foto/video **studio space** (called
"El Estudio") available by the hour. The product is a single web app with
three surfaces:

| Surface | Path | Audience |
| --- | --- | --- |
| **Catálogo público** | `/` | walk-up customers browsing equipment |
| **Portal cliente**  | `/cliente/*` | logged-in customers reviewing their orders / profile |
| **Back-office admin** | `/admin/*` | the single operator who runs the shop |

It's run by **one operator**, with a few hundred pieces of equipment and a
moderate volume of monthly rentals. That scale shapes everything: the admin
is dense and decision-supportive, the public side is bright, generous, and
"un lugar donde pasan cosas".

### Source material

- **GitHub:** `tixenre/rental` — private repo, branch `main`. Read first:
  `MANIFIESTO.md` (project context for Claude), `README.md` (stack +
  setup), `src/styles.css` (Tailwind v4 theme tokens), and
  `src/routes/index.tsx` (public home page).
- **Stack:** React 19 + Vite + TanStack Router + Tailwind v4 + shadcn/Radix
  UI + lucide-react. FastAPI + PostgreSQL on the backend. Deployed to Railway.
- **Locale:** Spanish (Argentina). Currency: ARS, with `formatARS()`.
- **Brand manual** that originated the palette + wordmark style:
  `uploads/RAMBLA branding.pdf` (kept locally for reference).

If you have access, explore the GitHub repo further — every component,
icon, illustration, and tone decision is in there and any one of them is a
better source of truth than this snapshot.

---

## CONTENT FUNDAMENTALS

### Language

- **Spanish (rioplatense / Argentinian).** Voseo (*"elegí fechas y armá tu
  pedido"*) is the house default for direct address — never *tú* or *usted*.
- Headlines are **lowercase** and often run-on multi-line: *"un lugar /
  donde pasan / cosas."* — the period is part of the line.
- Body and labels are **sentence case**. Buttons too: *"Reservar"*,
  *"Conocé el Estudio"*, *"Ver pack todo incluido"*, *"Cerrar sesión"*.
- Eyebrow labels and chrome are **UPPERCASE MONO**, widely tracked:
  `Catálogo · 187 equipos · Mar del Plata`, `BUSCÁ POR · CATEGORÍAS`.
- "I vs you": we say *"te lo dejamos listo para retirar"*. The brand
  speaks **as a person, in second person to the customer**, in plural
  first when describing itself (*"te confirmamos"*, *"acá vive…"*).
- Numbers: **tabular** everywhere they appear (prices, dates, counts,
  IDs). Currency: `$ 24.500` (Argentine notation, period thousands).

### Tone

Friendly, young, neighborhood-shop confident. Never corporate, never
overhyped, never apologetic. A short list of recurring moves:

- **Concrete promises**, not adjectives. *"Te lo dejamos listo para
  retirar"* > *"Servicio excepcional"*.
- **Casual asides** in dense docs: *"Sin colgadas."*, *"Sin las 3
  dimensiones la issue queda incompleta y no se prioriza."* (from
  MANIFIESTO).
- **The brand line "un lugar donde pasan cosas"** is reused as a tagline
  and as the public hero. It's the single most repeated string.
- **Specific over generic**. Categories are named what users say: *Cámaras,
  Lentes, Iluminación, Audio, Soportes, Accesorios, Adaptadores*.
- **No emoji** in production UI. Two exceptions, both as glyphs and not
  emoji: a **✨** sparkles via lucide (`<Sparkles />`) on the addon
  badge, and **★** as a literal Unicode star on "destacado" badges. Both
  are decorative seals on chips, not in body copy.
- **Casing in chrome**: the eyebrow label *"buscá por"* is lowercase
  inside an uppercased mono context — it's deliberate, the wordmark below
  it is the shouty one.

### Sample phrases (lift these)

- Hero: `un lugar / donde pasan / cosas.`
- Sub-hero: *Cámaras, ópticas, luces, audio y soportes para producciones
  audiovisuales. Elegí fechas y armá tu pedido — te lo dejamos listo para
  retirar.*
- CTA copy: *Reservar*, *Conocé el Estudio*, *Ver pack todo incluido*,
  *Consultanos por WhatsApp*.
- Empty state: *Sin resultados. Probá con otra categoría, marca o término
  de búsqueda.*
- Eyebrows: `Catálogo · N equipos · Mar del Plata`, `Producto estrella`,
  `Espacio Rambla`, `Aceptamos:`, `Sesión`.
- Footer micro: `© 2026 Rambla Rental`, `Aceptamos: Efectivo · Transferencia · MercadoPago`.

---

## VISUAL FOUNDATIONS

The brand is **one signature color (amber), one type personality (chunky
display + tight grotesque), one shape (a hand-cut sun / seal)**. Everything
else is restraint.

### Colors

| Token | Usage | Value (oklch) |
| --- | --- | --- |
| `--amber` | Hero bg, hover state, accent, brand seal fill | `oklch(0.82 0.16 78)` ≈ `#F2A81D` |
| `--amber-soft` | Tinted backgrounds, ring halo | amber @ 18% alpha |
| `--ink` / `--ink-2` | Primary buttons, body text, dark hero (estudio CTA) | `oklch(0.14 0.01 60)` / `0.18` |
| `--background` (bone) | Page background — warm near-white, never `#fff` | `oklch(0.985 0.005 90)` |
| `--surface` | Card backgrounds, panels | `oklch(0.97 0.008 85)` |
| `--card` / `--surface-elevated` | Elevated cards, modals | `oklch(1 0 0)` |
| `--hairline` | All borders | ink @ 12% alpha |
| `--muted-foreground` | Secondary text, eyebrows | `oklch(0.42 0.01 70)` |
| `--rbl-rosa / azul / naranja / verde` | Status + charts only | secondary palette |
| `--destructive` | Errors, delete | `oklch(0.62 0.22 27)` |

**Single-accent discipline.** Outside the secondary palette (reserved for
charts and pedido status), the page is mostly **bone, ink and amber**. The
secondary palette never appears in marketing surfaces.

### Type

| Family | Use | Weights loaded |
| --- | --- | --- |
| **TT Commons** *(primary)* | All UI — body, labels, form text, buttons, AND headings | Full axis 100–900 + italics, shipped under `fonts/` |
| **Champ Black** *(complementary)* | Used **principally for titles** — the chunky brand wordmark style | 900 only, shipped under `fonts/` |
| **JetBrains Mono** *(tooling)* | Tabular numbers (prices, dates, counts), uppercase eyebrows, code | 400, 500 from Google Fonts |

These are the **real brand faces from the Rambla brand manual** (both
vendored under `fonts/`), not Google substitutes — the production codebase
ships Bricolage Grotesque + Inter Tight only because the agent operator hadn't
loaded the licensed faces into the build pipeline yet. When working in
this design system, **use TT Commons + Champ Black** — they are what the
brand book specifies.

The painted **logo wordmark** in `assets/rambla-wordmark.{webp,png}` is
custom art, not a font. Use the image for actual logo lockups; use the
`.wordmark` utility (Champ Black + lowercase + slight negative tracking)
for stylized hero type in body content.

### Backgrounds

- **Flat color blocks**, no gradients in production. The amber hero is a
  solid amber field. The estudio CTA is solid ink.
- Exception: the **dot-grain texture** (`grain` utility) is layered over
  flat blocks at ~40% opacity to add tactile noise.
- Exception: a small **gradient placeholder** used on equipment-photo
  empty states (`amber-soft → surface → amber-soft`) — only when the
  upstream photo URL is null.
- No background imagery in chrome — all imagery is **product photos
  centered on white tiles**. The product itself is the visual.
- The diagonal **amber-tape** stripe pattern exists as a utility for
  status banners and addon callouts, but is used sparingly.

### Animation

- **Subtle and short.** `framer-motion` is in the deps but used minimally —
  most components rely on Tailwind's `transition-all` / `transition-colors`
  at the default 150ms duration.
- **Fade + tiny y-translate on mount** for equipment cards (`opacity: 0,
  y: 8 → 1, 0` over 300ms, with a staggered `delay: min(i * 0.012, 0.25)`).
- **Hover**: `group-hover:scale-[1.02]` on product photos. No big lift,
  no rotation. Category tiles have `-translate-y-0.5` on hover.
- **No bounces, no spring physics** in chrome. The brand isn't a toy.

### Hover & press states

- **Hover, dark elements**: `bg-foreground` → `bg-amber` + `text-ink`.
  This is the signature reverse: primary buttons go from ink to amber on
  hover, swapping foreground and background colors.
- **Hover, surfaces**: hairline border → ink border + `bg-amber-soft`.
- **Hover, opacity-only**: legal links and footer micro use `hover:text-amber`.
- **Active / press**: `active:scale-95` on the cart `+` button; otherwise
  unstyled.
- **Focus visible**: `focus-visible:ring-1 focus-visible:ring-ring` where
  `--ring` is amber @ 60% alpha.
- **Selected**: amber border + a 1px amber shadow `shadow-[0_0_0_1px_var(--amber)]`
  forming a halo, plus an amber check disk in the top-right corner.

### Borders, hairlines, shadows

- One border weight everywhere: **1px hairline** at ink @ 12% alpha. Heavier
  weights (2px) only for the **date pill** (interactive amber border) and
  the **estudio CTA card** (2px ink border on amber bg).
- **Shadows are minimal.** Cards rest flat. Primary CTA buttons get a
  small `shadow` (~1px). Elevated dialogs use shadcn defaults.
- **No inner shadows.** No glassmorphism. Sticky bars use
  `bg-background/95 backdrop-blur-md` for slight depth.

### Corner radii

A consistent six-step ladder. Used loosely:

- **`--radius-sm` (8px)** — text inputs, small chips
- **`--radius-md` (10px)** — buttons, icon containers
- **`--radius-lg` (12px)** — cards (default)
- **`--radius-xl` (16px)** — feature blocks, larger surfaces
- **`--radius-2xl` (20px)** — the studio CTA hero card
- **`9999px` (full)** — pill chips, filter toggles, primary CTAs, the
  date selector, all icon-only round buttons

### Cards

- **Border + flat bg, no shadow.** `surface` bg, `hairline` border,
  `rounded-lg`. Hover: border darkens to ink, no lift.
- **Equipment cards** are 4:5 with a square white tile on top (product
  photo `object-contain p-3 bg-white`) and a 1-row info strip on the
  bottom (brand mono · name display · price tabular + qty/add button).
- **Selected** state: amber border + amber halo shadow + amber check disk.
- **Sin stock**: 50% opacity, plus a centered "Sin stock" pill overlay
  on the photo.

### Layout & rhythm

- **Generous side padding on the public side**: `px-4` mobile, `px-6` sm,
  `px-12` lg.
- **Sticky chrome at top**: a 64px TopBar with the date pill, then a 48px
  toggle/search bar that also sticks. Both translucent (`backdrop-blur`).
- **Section vertical rhythm**: `py-10 / py-14` on the public side. Big
  letters, big air, no fancy grid.
- **Mobile is a first-class layout, not a scaling.** Components ship
  dual-render: `md:hidden` mobile branch + `hidden md:block` desktop
  branch (see Footer, TopBar). Tap targets are ≥40×40 on mobile.

### Transparency & blur

- Translucent backgrounds **only on sticky chrome** (TopBar 95% bg,
  catalog filter bar 95% bg) + `backdrop-blur-md/xl`. Everything else is
  solid.
- Overlays (cart drawer, modal scrims) use `bg-background/70`.

### Imagery treatment

- Product photos are **centered on a pure white tile**, with the photo
  itself `object-contain` and `p-3` of breathing room. The backend
  pipeline pre-processes uploads (`_optimize_image`: whitespace auto-crop,
  6% padding, 1200×1200 square).
- No grain, no filters on product imagery — the goal is honest
  representation.
- **Hero photography** (studio shots) is intentionally not used; the
  studio page shows `PhotoPlaceholder` blocks with the `gradient + grain`
  treatment, waiting for real shoots.

### Fixed elements

- **TopBar (sticky)** — `z-40`, full width, hairline bottom.
- **Sub-toolbar** (filter chips, search, view toggle) — `z-30`, sticks
  under the TopBar.
- **Cart mini bar** (mobile only, list view) — bottom-fixed pill that
  expands the cart drawer.
- **Floating action button** in admin lists for "+ Nuevo equipo".

---

## ICONOGRAPHY

Three layers, in priority order:

### 1. Lucide React (default chrome)

The codebase uses **`lucide-react`** for every interface icon: navigation,
input affordances, status, social. Stroke weight `2`, default sizes `16px`
(buttons inline) and `20px` (standalone). The icon set is loaded from npm
in the actual app; for **design-system consumers** with no build step, use
the official CDN:

```html
<script src="https://unpkg.com/lucide@latest"></script>
<i data-lucide="camera"></i>
<script>lucide.createIcons();</script>
```

Common imports already in the codebase (lift the names):

> `Camera, Search, Calendar as CalendarIcon, ShoppingBag, User, LogOut,
> Plus, Minus, Check, X, ArrowRight, ArrowLeft, Sparkles, Loader2,
> Instagram, MessageCircle, MapPin, Phone, Mail, Clock, LayoutGrid, List,
> LayoutDashboard, Package, ClipboardList, Users, BarChart3, Settings,
> ChevronRight, FolderTree, Tag, Wrench, Building2, Palette, Lightbulb,
> Snowflake`

### 2. Custom category illustrations

`src/components/rental/illustrations/CategoryIllustration.tsx` ships a
**hand-drawn monoline set** specifically for the catalog category mosaic:
*Cámaras, Lentes, Iluminación, Audio, Soportes, Accesorios, Adaptadores*.

Style: 64×64 viewBox, `currentColor` stroke (so they tint with theme),
`stroke-width: 2.5`, rounded line caps + joins, a touch more whimsy than
lucide (the *Soportes* illustration is literally a director's chair —
a nod to the brand seal). **Lift these directly** — see
`preview/iconography-categories.html` for a runnable demo with the source
SVG paths inline.

### 3. Brand seal marks (PNG)

The "sun / seal" symbol — a wavy 12-pointed disc with letterforms or
illustrations punched out of the middle — is the brand's heaviest visual
signature. Four variants ship under `assets/`:

- `rambla-icon-r.png` — punched **R** (used as favicon @ 512×512)
- `rambla-icon-seal.png` — punched **e**
- `rambla-icon-chair.png` — punched director's chair (Soportes / studio)
- `rambla-badge.png` — circular **"RAMBLA · RENTAL"** badge with the
  sun-rising-over-water illustration

Use these as **decorative anchors**, not as inline icons. They render at
~48–128px. The seal is symbolic of the brand, not a clickable affordance.

### Emoji

**Not used** in production UI. The brand voice is casual, but the icon
language is restrained. The only "emoji-looking" glyphs that appear are
Unicode `✦` and `★` baked into chip text — they're treated as typography,
not as imagery.

### Substitutions to flag

- No icon font ships in the repo; everything is SVG via `lucide-react`.
- `BrandCard.tsx` falls back to `cdn.simpleicons.org` for known equipment
  brand logos (Sony, Canon, Nikon, etc.) when no per-brand SVG is uploaded.

---

## FONTS — vendored locally

The brand book (`uploads/RAMBLA branding.pdf`) specifies two typefaces:
**TT Commons** (primary) and **Champ Black** (complementary, chunky
display). Both ship under `fonts/` and are wired into
`colors_and_type.css` via `@font-face` declarations. **JetBrains Mono**
is loaded from Google Fonts and is *not* in the brand book — it's a
tooling-side choice for tabular numerics and code-style chrome.

If you need to ship this system without TT Commons / Champ Black for
license reasons, the closest free Google substitutes are
**Bricolage Grotesque** (for Champ Black) and **Inter Tight** (for TT
Commons) — they're what the production codebase used as stand-ins before
the licensed faces were available. Swap the `@font-face` block at the
top of `colors_and_type.css` for `@import url("…fonts.googleapis.com…")`
and update the `--font-display` / `--font-sans` family names.

---

## File index (manifest)

| Path | What |
| --- | --- |
| `README.md` | This file — brand context, content + visual fundamentals, iconography |
| `SKILL.md` | Skill manifest so this folder can be loaded as an Agent Skill |
| `colors_and_type.css` | All design tokens — colors, type, radii, semantic vars + utility classes (`.wordmark`, `.grain`, `.t-eyebrow`, …) |
| `fonts/` | Vendored brand fonts — TT Commons full family + Champ Black |
| `assets/` | Brand marks (PNG/WEBP): wordmark lockup, wordmark-only, four seal variants, favicon |
| `preview/` | Design-system specimen cards (registered in the Design System tab) |
| `ui_kits/public/` | Public catalog click-through prototype (`index.html`, `components.jsx`, `icons.jsx`, `data.js`, `styles.css`) — `<TopBar>`, `<Hero>`, `<CategoryMosaic>`, `<BrandRow>`, `<EquipmentCard>`, `<Footer>`, `<CartDrawer>` |
| `ui_kits/admin/` | Back-office click-through prototype — `<Sidebar>`, `<Toolbar>`, `<EquiposTable>`, `<BulkBar>`, `<KPIStrip>` |
| `uploads/RAMBLA branding.pdf` | The Rambla brand manual (kept for reference) |

---

## How to use this system

1. **For prototypes / mockups (HTML)** — start by linking
   `colors_and_type.css`, copy the `assets/` you need, and pull JSX
   components out of `ui_kits/*/`. The components are intentionally simple
   and cosmetic — they're not the real production code.
2. **For production code** — read this README + the source repo. The CSS
   variables here are 1:1 with the names in `src/styles.css` of the
   production app, so you can drop tokens straight into a Tailwind v4
   `@theme` block.
3. **Always go to the source.** This system is a high-fidelity snapshot
   from one point in time. The repo (`tixenre/rental`) keeps moving —
   `MANIFIESTO.md` is the live source of truth.
