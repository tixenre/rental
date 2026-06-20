# Design System — Rambla Rental

> **Esta es la referencia canónica del design system del repo.** Lo que
> está acá vale para cualquier código en `src/`. Si una pantalla nueva
> tiene que decidir un color, un tamaño tipográfico, un radio, una
> animación o un texto — empezás acá.
>
> La fuente canónica del design system es este doc + `src/styles/` (tokens/tipografía/utilities/
> fuentes; entry `src/ds-styles.css`) + `src/components/` (primitivos y piezas).

---

## Stack real

- **Frontend:** Vite + React 19 + TanStack Router + Tailwind v4 +
  shadcn/Radix UI + lucide-react. **NO Next.js.**
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

| Token                 | Valor                   | Uso                                    |
| --------------------- | ----------------------- | -------------------------------------- |
| `--amber`             | `#FAB428`               | Brand accent, hero bg, hover highlight |
| `--amber-soft`        | `amber @ 18%`           | Tinted bg, focus ring fill             |
| `--amber-hot`         | `#FFCC55`               | Paso claro para amber-tape pattern     |
| `--ink`               | `oklch(0.14 0.01 60)`   | Primary text, buttons, body            |
| `--ink-pure`          | `#000000`               | Hero display text, print               |
| `--background` (bone) | `oklch(0.985 0.005 90)` | Page background                        |
| `--surface`           | `oklch(0.97 0.008 85)`  | Cards, panels                          |
| `--surface-elevated`  | `oklch(1 0 0)`          | Elevated cards, inputs, modales        |
| `--hairline`          | `ink @ 12%`             | Borders, dividers                      |
| `--muted-foreground`  | `oklch(0.42 0.01 70)`   | Secondary text, eyebrows               |
| `--rosa`              | `#ED7BAD`               | Status palette                         |
| `--azul`              | `#1097DB`               | Status palette (Presupuesto)           |
| `--verde`             | `#009971`               | Status palette (Confirmado)            |
| `--naranja`           | `#E9552F`               | Status palette (Warning)               |
| `--destructive`       | `oklch(0.62 0.22 27)`   | Errors, delete, Cancelado              |

**Regla del color (single-accent discipline):** la página es \*\*bone + ink

- amber**. La paleta secundaria (rosa/azul/verde/naranja) **sólo\*\* para
  status de pedido y gráficos — nunca en superficies de marketing.

**Orden de gráficos** (siempre): amber → azul → naranja → verde → rosa.

Las utilities Tailwind correspondientes (`bg-amber`, `text-ink`,
`border-hairline`, `bg-rosa/10`, etc.) las genera Tailwind v4 directo de
estos tokens vía el bloque `@theme inline` al inicio de `src/styles.css`.

#### Tiers de color (de dónde puede salir un color)

Todo color en `src/` tiene que venir de uno de estos cuatro tiers. Nada de
Tailwind genérico (`bg-slate-100`, `text-blue-700`, …) ni hex crudo
ad-hoc por pantalla — esa es la deuda que se barrió en
[#584](https://github.com/tixenre/rental/issues/584). **El guardrail de
ESLint ya está activo** (`no-restricted-syntax` en `eslint.config.js`):
una clase de escala genérica (`text-green-700`, `bg-blue-500`, …) en
`className` **rompe el lint** (bloqueante en CI).

| Tier                         | Para qué                                                        | De dónde sale                                                                                                                                                                                                                                        |
| ---------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Marca**                 | Identidad                                                       | `amber`, `amber-soft`, `amber-hot`, `ink`, `ink-pure`, `background`, `surface`, `muted`, `hairline`, … (tokens)                                                                                                                                      |
| **2. Status**                | Estados semánticos (pedido, pago, éxito/error/info, delta +/−)  | `azul`, `verde`, `rosa`, `naranja`, `destructive` (tokens). Mapeo: éxito/positivo → `verde`; error/negativo → `destructive`; info → `azul`; aviso → `amber`/`naranja`                                                                                |
| **3. Categórico**            | Distinguir N ítems de una taxonomía donde 4 colores no alcanzan | **Paletas centralizadas y nombradas**, no inline. Ej.: `AVATAR_COLORS` (avatares de cliente), `kindFor` en `/admin/novedades` (tipos de changelog). Pueden usar hues fuera de la paleta de marca porque su función es la distinción, no la identidad |
| **4. Excepción de terceros** | Affordances reconocibles de marcas externas                     | Verde WhatsApp (`#25D366`), colores del logo de Google (`#EA4335/#4285F4/#FBBC05/#34A853`). Documentadas acá, allow-listed en el guardrail                                                                                                           |

**Regla:** colores genéricos/hex sólo se permiten en tiers 3 y 4, y ahí
viven en constantes centralizadas y documentadas — nunca sueltos en una
pantalla. Cualquier otro color sale de un token (tiers 1-2).

**Cómo exceptuar (tiers 3 y 4):** envolvé la constante con
`/* eslint-disable no-restricted-syntax */` … `/* eslint-enable */` (o
`// eslint-disable-next-line no-restricted-syntax` en una línea) **con un
comentario que diga qué tier es y por qué**. Para un archivo que es entero
una marca de terceros (ej. `WhatsAppButton.tsx`) hay un override por archivo
en `eslint.config.js`. El hex de terceros (WhatsApp `#25D366`, logo de
Google) no lo agarra la regla — pero igual va documentado acá.

La escala genérica `amber-NNN` de Tailwind (`text-amber-700`, etc.) **también está prohibida** por el guardrail — `amber` fue sumado a `GENERIC_COLOR_RE` en el PR #590 junto al barrido completo de usos. Usar `text-amber`, `bg-amber/10`, `border-amber/30` (tokens de marca), o `text-ink` cuando el texto va sobre fondo amber.

### Tipografía

```css
--font-display: "Champ Black", "TT Commons", ui-sans-serif, ...;
--font-sans: "TT Commons", ui-sans-serif, -apple-system, ...;
--font-mono: "JetBrains Mono", ui-monospace, monospace;
```

**Reglas:**

- **Champ Black** = SÓLO para hero taglines (`.t-display-1`/`.t-display-2`)
  y el `.wordmark` del logo. Headings de UI, body, labels → TT Commons.
- **Display text siempre `lowercase`**. _"un lugar donde pasan cosas."_
- **Headings de UI** en Title Case normal con TT Commons.
- **Eyebrows / chrome / numbers** → JetBrains Mono, uppercase, tracking
  ancho. _`CATÁLOGO · 187 EQUIPOS · MAR DEL PLATA`_.
- **Numbers** tabulares siempre que aparezcan (precios, fechas, counts,
  IDs). Tailwind: `tabular-nums` o nuestra utility `.tabular`.

### Radii

```css
--radius: 0.75rem /* base = 12px */ --radius-sm: 8px /* inputs, chips chicos */ --radius-md: 10px
  /* buttons, icon containers */ --radius-lg: 12px /* cards (default) */ --radius-xl: 16px
  /* feature blocks */ --radius-2xl: 20px /* studio CTA hero */ --radius-3xl: 24px /* — */
  --radius-4xl: 28px /* — */ /* + rounded-full = 9999px para pills, filter chips, CTAs */;
```

### Z-index (project-specific, NO el genérico del kit)

```css
--z-topbar: 50 /* TopBar sticky */ --z-topbar-amber: 49 /* Variante amber-on-scroll del topbar */
  --z-scrim: 60 /* Overlays (cart drawer, modal scrim) */ --z-drawer: 61
  /* Drawer/sheet contents sobre el scrim */ --z-cart-strip: 45 /* Cart mini bar bottom-fixed */
  --z-cat-bar: 40 /* Category bar sticky */ --z-sub-toolbar: 30
  /* Sub-toolbar (search + filters bajo el topbar) */;
```

> **No usamos** el ladder genérico del kit (`--z-raised/dropdown/sticky/modal/toast/tooltip`).
> Si una pantalla nueva necesita un z-index, primero mirá si hace match
> con alguno de los siete arriba — `--z-scrim` y `--z-drawer` son los más
> reusables.

### Shadows — opt-in al brand tint

Cuatro tokens nuevos para sombras tintadas con `oklch` del ink (en vez
del negro puro de las shadow defaults de Tailwind, que choca con el
bone+ink cálido del sistema). Las utilities `shadow-sm`/`shadow-md`/
etc. de Tailwind siguen funcionando con sus defaults; el tint es opt-in
vía `var()`:

```tsx
className = "shadow-sm"; // Tailwind default (sin cambios)
className = "shadow-[var(--shadow-md)]"; // brand-tinted opt-in
```

```css
--shadow-sm: 0 1px 2px oklch(0.18 0.01 60 / 6%);
--shadow-md: 0 4px 12px oklch(0.18 0.01 60 / 8%), 0 1px 3px oklch(0.18 0.01 60 / 5%);
--shadow-lg: 0 12px 32px oklch(0.18 0.01 60 / 10%), 0 2px 8px oklch(0.18 0.01 60 / 6%);
--shadow-xl: 0 24px 56px oklch(0.18 0.01 60 / 12%), 0 6px 16px oklch(0.18 0.01 60 / 8%);
```

Mapeo: `sm` → cards en reposo · `md` → dropdowns + hover lift · `lg` →
toasts + FABs · `xl` → modales + dialogs.

**Sombras signature siguen siendo inline** (no son tokens — son únicas
de un componente):

- `shadow-[0_-8px_32px_-8px_rgba(0,0,0,0.15)]` → CartMiniBar (sube)
- `shadow-[0_-12px_24px_-8px_rgba(0,0,0,0.08)]` → CartMiniBar preview hover

### Motion — duraciones + easings canónicos

```css
--duration-fast: 120ms; /* press states, button bumps */
--duration-base: 200ms; /* hover transitions, color changes */
--duration-slow: 350ms; /* entry animations, slide-up */
--duration-xslow: 550ms; /* fly-to-cart, hero reveals */

--ease-default: cubic-bezier(0.32, 0.72, 0, 1); /* snappy settle, drawer */
--ease-out: cubic-bezier(0, 0, 0.2, 1); /* standard decel */
--ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1); /* overshoot, badge pop */
```

`--duration-xslow` matchea exactamente la `duration: 0.55` del
FlyToCartLayer. `--ease-default` es el del CartDrawer Framer Motion.
`--ease-bounce` es la signature del badge pop al sumar al carrito.

Uso opt-in:

```tsx
className = "transition duration-[var(--duration-fast)] ease-[var(--ease-default)]";
```

Tailwind defaults (`duration-150`, `ease-out`) siguen funcionando para
el resto.

### Spacing — Tailwind ya cubre

**NO se crean tokens `--space-*`.** Tailwind v4 ya provee `p-1`…`p-96`
sobre base 4px, e introducir `--space-*` sería redundante y rompería la
intuición de devs que conocen Tailwind. Referencia rápida:

| Tailwind        | px  | Uso típico                 |
| --------------- | --- | -------------------------- |
| `p-1` `gap-1`   | 4   | Stepper button gap         |
| `p-2` `gap-2`   | 8   | Chip rail gap, inline pill |
| `p-3` `gap-3`   | 12  | Card body, button gap      |
| `p-4` `gap-4`   | 16  | Drawer item                |
| `p-6` `gap-6`   | 24  | Section, card padding      |
| `p-8` `gap-8`   | 32  | Hero mobile                |
| `p-12` `gap-12` | 48  | Hero desktop, container    |

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

| Categoría                                          | Dónde vive                | Notas                                                                                                                                  |
| -------------------------------------------------- | ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Primitivas UI** (Button, Input, Card, Dialog, …) | `src/components/ui/*`     | shadcn/Radix base + variants de marca (`primary`, `amber`). Naming shadcn: `default` no se renombra (ver Button abajo).                |
| **Componentes de aplicación (`rental/`)**          | `src/components/rental/*` | EquipmentCard, TopBar, Footer, CartMiniBar integrados con queries + estado.                                                            |
| **Componentes admin**                              | `src/components/admin/*`  | Tablas, modales, sidebar del back-office.                                                                                              |
| **Kit portátil ports**                             | `src/components/kit/*`    | Versiones presentacionales del kit, con paleta de marca. Adoptadas piecewise (issue #575). EstadoBadge ya es la única fuente del repo. |

### Button (`src/components/ui/button.tsx`)

```tsx
import { Button } from "@/components/ui/button";

// variants: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link" | "primary" | "amber"
// sizes:    "default" (h-9) | "sm" (h-8) | "lg" (h-10) | "icon" (h-9 w-9)
// shape:    "rounded" (default) | "pill"
// "amber" y el axis "shape" fueron agregados por PR #577. "primary" (ink→amber
// al hover, CTA signature) por el Master Handoff — distinto de "amber".

<Button variant="default">Reservar</Button>
<Button variant="primary" shape="pill">Solicitar rental</Button>
<Button variant="amber" shape="pill" asChild><a href="/estudio">→</a></Button>
```

> **No renombrar `default` a `primary`** — eso rompería decenas de
> `<Button variant="default">` que existen hoy. Las variantes de marca
> (`primary` = fondo ink que invierte a amber en hover; `amber` = siempre amber,
> sin inversión; + el axis `shape`) entran como **adición**, no como reemplazo.

### EstadoBadge

**Fuente única**: `src/components/kit/EstadoBadge.tsx`, con la paleta
secundaria oficial de marca (`bg-azul/10`, `bg-verde/10`, …).

Usado por `/cliente/portal` (PR E1) **y por el admin** (`/admin/pedidos`
list + `/admin/pedidos/$id` detalle, PR E2). El admin pasa el prop opcional
`label` para preservar su alias visible "presupuesto → Solicitado": el texto
se overridea, pero el color sale del map por `estado` (presupuesto → azul,
paleta de marca documentada). Los mappings inline viejos (`ESTADO_CLASS`,
`ESTADO_PILL`) con Tailwind genéricos quedaron eliminados.

Pendiente (follow-up, issue #575): el helper compartido `pedidoEstadoVariant`
(`clientes.lazy`, `CalendarioWidget`) todavía mapea a variants de shadcn
`Badge` — consolidar con `EstadoBadge` es una decisión visual aparte
(rows de historial / leyenda de calendario, contextos distintos a los chips
de pedido).

### PagoBadge

**Fuente única**: `src/components/kit/PagoBadge.tsx`. Hermano de `EstadoBadge`:
mientras ese muestra el **estado del pedido**, este muestra la **cobranza con el
monto** — `Pagado` (verde) · `Debe $X` (rojo si urgente = retirado/entregado,
ámbar si no) · `Seña $X` (cotización con seña). Idea tomada de cómo Booqable hace
visible el "Estado del pago". Props: `pagado`, `total`, `estado`. Devuelve `null`
cuando no aplica (cotización sin seña, o pedido sin monto) — el caller no necesita
placeholder. Pensado para **cualquier superficie que liste pedidos** (admin list,
portal cliente, dashboards): no reimplementar el cálculo "sin seña/debe/pagado"
inline, usar este chip.

### ClienteAvatar

**Fuente única**: `src/components/kit/ClienteAvatar.tsx`. Círculo con iniciales y
color **determinístico por nombre** (hash sobre paleta acotada de tokens, todos
con buen contraste) → el mismo nombre siempre cae en el mismo color, para
reconocimiento visual rápido en listas/headers (idea de Booqable). Tamaño/typo por
`className`. Reusable en admin y portal. No crear avatares ad-hoc con `bg-ink`
inline.

### Otros componentes del kit (`src/components/kit/`)

Versiones presentacionales del kit ya disponibles para adopción
piecewise (PR #577 las trajo a producción):

- `AddonPills` — items "incluye" sobre rows de equipo.
- `EmptyState` — pattern "nada para mostrar".
- `PriceBlock` — precio + tarifa display.
- `ViewToggle` — segmented control con pill deslizante.
- `StatCard` — número grande para dashboards.
- `Input` + `SearchInput` + `FieldLabel` — variantes branded de inputs.

> **Patrón de lista de pedidos (Booqable-inspired, 2026-06):** una fila se lee de
> un vistazo con **avatar (`ClienteAvatar`) + nombre + `EstadoBadge` + `PagoBadge`
> + monto**, alto contraste y jerarquía clara. Es el patrón a reproducir en el
> resto de la web cuando se listan entidades con estado + plata.

La ruta pública `/kit-preview` (sin login, `noindex`) los muestra todos
para QA visual antes de adoptarlos en una pantalla concreta.

---

## Mobile — reglas críticas

```html
<!-- 1. viewport-fit=cover siempre -->
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
```

```css
/* 2. Safe areas — usar env(safe-area-inset-*) */
.topbar {
  padding-top: env(safe-area-inset-top);
}
.bottom-bar {
  padding-bottom: calc(0.75rem + env(safe-area-inset-bottom));
}
.cart-drawer {
  max-height: 85dvh;
  padding-bottom: env(safe-area-inset-bottom);
}

/* 3. Tap highlight transparente — usar el del :active propio */
* {
  -webkit-tap-highlight-color: transparent;
}

/* 4. Anti-zoom de iOS — inputs ≥ 16px */
input,
textarea,
select {
  font-size: max(16px, 1em);
}

/* 5. Drawer overscroll — no propagar el scroll del body */
.cart-drawer,
.bottom-sheet {
  overscroll-behavior: contain;
}

/* 6. Full-height usar dvh, no vh */
.modal,
.full-screen {
  height: 100dvh;
}
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
input:focus-visible,
textarea:focus-visible {
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
fondo y texto en hover. _"Pasa el mouse y se prende."_

**Cart count bump:** cuando se agrega un equipo al carrito, el badge del
contador hace `scale [1, 1.25, 0.95, 1]` (ease bounce, ~200ms). Spec
real en `src/components/rental/CartMiniBar.tsx`.

**+1 fly to cart:** específico de Rambla. Componente
implementado: `src/components/rental/FlyToCartLayer.tsx`. Curva canónica
`cubic-bezier(0.22, 1, 0.36, 1)`, duración 550ms.

**TopBar amber-on-scroll:** específico de Rambla.
Mecánica: CSS variable `--amber-pct` calculada por la página, el header
hace `color-mix(in oklch, amber X%, background 92% alpha)`. Snap a 65%
del progreso del hero invierte logo + date pill + user button.

---

## Voz y tono (copy rules)

- **Siempre "vos"** (voseo rioplatense). _Reservá, elegí, confirmá._
  Nunca _usted_, nunca _tú_.
- **Minúsculas en wordmark, taglines y heroes.** Title Case normal en
  headings de UI.
- **Punto final en taglines y titulares de hero.** No `!`, no `…`.
  _"un lugar donde pasan cosas."_
- **Precios:** `$ 24.500` ($ con espacio, punto como separador de
  miles). Siempre vía `formatARS()`.
- **Fechas:** `lun 2 jun.` (formato corto), `lun 2 → jue 5 jun.` (rangos).
- **Jornadas:** `3 J` (compact en cards), `3 jornadas` (full).
- **Errores:** específicos y en primera persona del usuario.
  _"Ingresá un correo válido."_ (no _"Error: email inválido"_).
- **Empty states:** accionables. _"No hay equipos para estas fechas."_
  (no _"No se encontraron resultados"_).
- **Sin emoji** en UI de producción. Excepciones (como glifos, no como
  emoji): `✨` via `<Sparkles />` de lucide en el badge addon; `★` literal
  en "destacado".

---

## Skeleton / loading

```css
.skeleton {
  background: linear-gradient(
    90deg,
    var(--surface) 25%,
    var(--surface-elevated) 50%,
    var(--surface) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.4s ease infinite;
  border-radius: var(--radius-sm);
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
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
  .nav,
  .topbar,
  .sidebar,
  [data-no-print] {
    display: none !important;
  }
  body {
    background: white;
    color: #000000;
    font-size: 11pt;
  }
  .wordmark {
    color: #fab428;
  }
  @page {
    margin: 20mm;
    size: A4;
  }
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

En cada PR de UI: si tocás algo en (1) o (2), tocá también (3) si
corresponde. El supervisor cuida que no quede drift silencioso.

---

## Cómo leer este doc

- **Sos un dev que va a tocar UI**: leé "Tokens", "Componentes", la
  sección del componente que vas a tocar, y "Patterns que nunca se
  rompen" antes de empezar.
- **Sos PM/diseñador iterando en Claude Design**: leé "Voz y tono",
  "Mobile rules", y revisá `/kit-preview` para ver los componentes en vivo.
- **Sos sesión de Claude Code arrancando**: leé "Stack real", "Tokens",
  "Patterns que nunca se rompen", y `docs/MEMORIA.md` para criterio.

Si dudás cómo aplicar algo, leé el código real en `src/components/*` —
casi siempre hay un ejemplo vivo.
