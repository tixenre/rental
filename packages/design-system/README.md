# @rambla/design-system

> **Fuente de verdad** del look & feel de Rambla Rental. Tokens, tipografía, brand assets, helpers de formato y la librería de componentes — en un solo paquete modular que la app `tixenre/rental` **consume** (ya no espeja).

Plataforma de alquiler de equipos audiovisuales · Mar del Plata, AR · React 19 + Vite + Tailwind v4 + shadcn/Radix.

---

## Por qué este paquete

Antes este design system era un *mirror* downstream del repo (“si difieren, el repo manda”). **Ahora se invirtió la dirección:** los tokens, fuentes, assets y helpers viven acá y la app los importa. Una sola fuente, cero drift.

```
app (tixenre/rental)  ──importa──►  @rambla/design-system  ◄── editás acá
```

---

## Estructura

```
rambla-design-system/
├─ package.json                 # name, exports map, peerDependencies
├─ tokens.json                  # tokens machine-readable (Style Dictionary / tooling)
├─ README.md                    # este archivo
├─ ADOPT.md                     # pasos exactos para que el repo lo consuma
├─ styleguide/                  # styleguide vivo navegable (58 specimens + tokens)
│  ├─ index.html               # shell branded: sidebar + buscador + visor iframe
│  └─ preview/                 # specimens HTML verificados
└─ src/
   ├─ styles.css                # ★ ENTRY — reemplaza al src/styles.css del repo
   ├─ styles/
   │  ├─ fonts.css              # @font-face (TT Commons, Champ Black)
   │  ├─ utilities.css          # recetas .t-* + amber-tape, grain, focus, safe-*
   │  └─ tokens/                # ← editá un token en SU archivo, no en el entry
   │     ├─ colors.css          # @theme --color-*  → bg-amber, text-ink, border-hairline
   │     ├─ typography.css      # @theme --font-*   → font-display/sans/mono
   │     ├─ radii.css           # @theme --radius-* → rounded-sm…4xl
   │     ├─ shadows.css         # @theme --shadow-* → shadow-sm…xl (brand-tinted)
   │     ├─ motion.css          # @theme --ease-*  + :root --duration-*
   │     └─ z-index.css         # :root --z-* (topbar→scrim→drawer)
   ├─ assets/
   │  ├─ fonts/                 # TT Commons (.otf) + Champ Black (.ttf)
   │  └─ brand/                 # wordmark + isologo (SVG themable) + raster + manifest
   │     └─ index.ts            # import { wordmark, isologo, brand } from "@/assets/brand"
   ├─ lib/
   │  ├─ utils.ts               # cn()
   │  └─ format.ts              # formatARS, formatShortDate, formatRentalRange, jornadaLabel
   └─ components/
      ├─ ui/    (button, badge, card)              + index.ts
      ├─ kit/   (EstadoBadge, PriceBlock, StatCard, ViewToggle, AddonPills, EmptyState, Input) + index.ts
      └─ rental/(TopBar, CartDrawer, CartMiniBar, EquipmentCard, FavButton, FlyToCartLayer,
                 Footer, RentalDateModal, StepperPill) + index.ts
```

**Modularidad:** cada capa de token es un archivo propio con su `@theme`. Tailwind v4 mergea todos los `@theme` que se importan desde el entry. Cambiás un color → tocás `tokens/colors.css`, nada más.

---

## Uso

**1 · Estilos (una vez, en el entry de la app):**

```ts
// src/main.tsx
import "@rambla/design-system/styles.css";
```

Eso trae Tailwind + fonts + todos los tokens + utilities. A partir de ahí las utilities de marca existen: `bg-amber`, `text-ink`, `border-hairline`, `shadow-md`, `rounded-lg`, `font-display`, `ease-bounce`, etc.

**2 · Componentes:**

```tsx
import { Button, StepperPill, EstadoBadge, PriceBlock } from "@rambla/design-system";
// o granular:
import { TopBar } from "@rambla/design-system/components/rental";

<Button variant="primary" shape="pill">Reservá</Button>
```

**3 · Helpers y assets:**

```tsx
import { formatARS, formatRentalRange } from "@rambla/design-system/lib/format";
import { wordmark, isologo } from "@rambla/design-system/brand";

formatARS(145500, { iva: true })   // "$ 145.500 + IVA"
<img src={wordmark} alt="rambla" className="text-amber" />   // SVG themable vía currentColor
```

---

## Reglas innegociables (las hereda el linter del repo)

1. **Tokens only.** `bg-amber`, `text-ink`, `border-hairline`. Nunca hex crudo ni `bg-blue-500` (rompe CI).
2. **Champ Black SOLO display/wordmark.** Nunca UI, labels, precios, headings funcionales.
3. **Precios** → `formatARS()`. **Fechas** → helpers de `lib/format` con locale `es`.
4. **Iconos** lucide, import individual. Sin emoji en UI de producción.
5. **dvh no vh**, touch targets ≥ 44px, voz “vos” (reservá, elegí, confirmá).
6. **Single-accent:** la página es bone + ink + amber. Status palette (rosa/azul/verde/naranja) SOLO para estados de pedido y charts.

---

## Styleguide vivo

`styleguide/index.html` es un sitio estático navegable: sidebar agrupado
(Type / Colors / Spacing / Components / Brand), buscador, control de viewport
(390 / 768 / full) y deep-links por hash (`#components-buttons`). Renderiza los
58 specimens verificados en un visor iframe — **cero build, abrís el HTML**.

Es self-contained: trae su propio `colors_and_type.css` (viewer-only, variables
planas — los specimens se escribieron contra esos nombres) y `assets/`, y tira
las fuentes desde `../src/assets/fonts/`. Pensado como referencia de diseño /
QA visual, no como runtime de la app.

```bash
# servir local (cualquier static server)
npx serve rambla-design-system/styleguide
```

---

## Optimización de fuentes (paso opcional, recomendado)

Las fuentes van vendoreadas como `.otf/.ttf` (consistente con el repo actual). Para web conviene `.woff2` subseteado — corré una vez y actualizá `fonts.css`:

```bash
# pip install fonttools brotli
pyftsubset src/assets/fonts/TT_Commons_Regular_0.otf \
  --unicodes="U+0000-00FF,U+0100-017F,U+2010-2027" \
  --flavor=woff2 --output-file=src/assets/fonts/tt-commons-400.woff2
```

JetBrains Mono se sirve desde Google Fonts en producción (no se vendorea).

---

## Adopción

Ver **[ADOPT.md](./ADOPT.md)** para los pasos exactos de migración del repo (flip de `src/styles.css`, alias, peer deps, checklist de verificación).
