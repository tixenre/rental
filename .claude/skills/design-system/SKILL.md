---
name: design-system
description: Trabajar con el design system de Rambla — el paquete del workspace @rambla/design-system (packages/design-system/). Cubre las dos mitades del ciclo. (1) MANTENER la librería: actualizarla desde un export nuevo, agregar/editar tokens o piezas del kit, mantenerla modular y verificable. (2) CONSUMIRLA desde la app (reuse-first): tomar tokens/primitivos/piezas del paquete en vez de recrearlos. Úsalo cuando toques packages/design-system/, actualices el DS desde un ZIP/export, agregues o edites tokens/primitivos/kit, cableés una pantalla para que consuma el DS, o cuando dudes si un botón/badge/precio/stepper/estado ya existe en la librería. NO es para diseñar pantallas nuevas (eso es importar-diseno).
---

# design-system — la librería @rambla/design-system

El design system de Rambla vive como **paquete del workspace** en `packages/design-system/`
(npm workspaces) y la app lo **consume** como librería. Es la fuente única de tokens, tipografía,
primitivos y piezas reusables. Iniciativa de adopción: GitHub **#662**. Decisiones de fondo:
MEMORIA *2026-05-29* (módulos compartidos = fuente única) y *2026-05-30* (modularidad).

> **Regla de oro:** el **paquete es la fuente de verdad** del diseño. Un token/utility/pieza se
> edita **en `packages/design-system/src/`**, nunca se duplica en `src/` de la app. El supervisor
> marca como hallazgo cualquier token/pieza ad-hoc que duplique algo del paquete.

## Arquitectura en capas (construir y pensar **de abajo hacia arriba**)

| Capa | Qué | Dónde | Quién la consume |
|---|---|---|---|
| **0 · Tokens** | colores, tipografía, sombras, motion, z-index, fuentes | `src/styles/tokens/*` + `fonts.css` | toda la app, vía CSS |
| **1 · Primitivos** | `button`, `badge`, `card`, `input` (shadcn + marca) | `src/components/ui/`, `src/components/kit/Input` | piezas y pantallas |
| **2 · Kit (piezas)** | `PriceBlock`, `StepperPill`, `FavButton`, `EstadoBadge`, `StatCard`, `AddonPills`, `EmptyState`, `ViewToggle` | `src/components/{kit,rental}/` | pantallas |
| **3 · Pantallas** | carrito, topbar, ficha equipo… (**cableadas** a estado/negocio) | **en la app** (`src/`), NO en el paquete | usuarios |

**Las capas 0-2 son design system (van al paquete). La capa 3 NO** — ver "Qué NO va al paquete".

## Estructura del paquete (modular a propósito)

```
packages/design-system/
├─ package.json        # exports: ./styles.css, ./components/{ui,kit,rental}, ./lib/*, ./brand
├─ src/
│  ├─ styles.css        # ENTRY: @import "tailwindcss" source(none) + @source "." + tokens + utilities
│  ├─ styles/
│  │  ├─ fonts.css      # @font-face (familia TT Commons completa + Champ)
│  │  ├─ tokens/*.css   # @theme (colors, typography, shadows, motion) + :root (z-index, shadows)
│  │  └─ utilities.css  # recetas .t-*, calendario, topbar, keyframes
│  ├─ components/{ui,kit,rental}/  # cada carpeta con su index.ts (barrel)
│  ├─ lib/{utils,format}.ts        # cn() + formatARS()
│  ├─ assets/{brand,fonts}/        # logos + fuentes vendoreadas
│  └─ env.d.ts          # declaraciones ambientales de assets (*.svg/.png/.webp) → typecheck autónomo
└─ styleguide/          # showcase HTML estático (referencia visual; NO usa el styles.css del paquete)
```

---

## A) MANTENER la librería

### Verificar (hacelo siempre tras tocar el paquete)
- **`npm run typecheck:ds`** → la librería type-checkea **sola** (gate de CI, job `typecheck`). Si
  agregás un import de un tipo de archivo nuevo (ej. `.json`, `.woff2` por TS), declaralo en `env.d.ts`.
- **`npm run build`** → el CSS de salida no debe crecer de golpe (sin bloat) y debe traer los tokens.

### Actualizar el DS desde un export/ZIP nuevo
1. Reemplazá el contenido de `packages/design-system/src/` con el nuevo (o aplicá los diffs).
2. **Reconciliá hacia producción si el objetivo es no cambiar la vista:** si una pieza del export
   difiere de lo que está vivo en la app y NO querés cambio visual, dejá la del paquete igual a la de
   la app (la app es lo testeado). Si SÍ querés el rediseño, es un cambio visible → plan de prueba +
   el dueño lo aprueba en staging. (Mismo criterio que el "CSS flip" no-op de #736.)
3. **Bump de versión** en `packages/design-system/package.json` (semver).
4. `npm install` (revincula el workspace), `npm run typecheck:ds`, `npm run build`.
5. PR a `dev` con plan de prueba. El supervisor revisa.

### Reglas del CSS (capa 0)
- El entry del paquete usa **`@import "tailwindcss" source(none)` + `@source "."`** → allowlist de
  escaneo (no escanea el repo entero, evita bloat de `docs/`). Cada consumidor agrega su `@source`.
- Tokens canónicos = **`--color-*`** (en `@theme`). Generan utilities (`bg-amber`, `text-ink`…).
- Sombras en **`:root`** (no `@theme`) → las utilities `shadow-*` quedan default de Tailwind; el tint
  de marca es opt-in con `var(--shadow-md)`.
- `EstadoPedido` en `components/kit/types.ts` debe **matchear** `src/lib/pedido-estados.ts` (API real).

---

## B) CONSUMIR desde la app (reuse-first)

> **Antes de crear un botón / badge / precio / stepper / favorito / estado: chequeá si ya está en el
> paquete.** Si está, importalo. Si falta un primitivo reusable nuevo, **agregalo al paquete**, no inline.

### Tokens (capa 0) — ya se consumen
La app toma el CSS del paquete en `src/styles.css` (entry mínimo):
```css
@import "@rambla/design-system/styles.css";   /* Tailwind + tokens + utilities + fuentes */
@import "tw-animate-css";
@source "../src";
@source "../packages/design-system/src";
:root { --amber-pct: 0%; --cart-strip-h: 0px; /* + shim transicional de alias planos */ }
```
- **No redefinas tokens en la app.** Usá las utilities (`bg-amber`, `text-ink`, `border-hairline`…).
- **Shim de alias planos** (`--amber: var(--color-amber)` …) = **transicional**. El código viejo usa
  nombres planos (`var(--amber)`); el canónico es `--color-*`. **No agregues usos nuevos de nombres
  planos** — usá utilities o `var(--color-*)`. El shim se retira cuando se migren los usos viejos.

### Primitivos y piezas (capas 1-2)
Importá de los **barrels** (el paquete exporta barrels, no rutas profundas):
```ts
import { Button } from "@rambla/design-system/components/ui";
import { PriceBlock, EstadoBadge } from "@rambla/design-system/components/kit";
import { formatARS } from "@rambla/design-system/lib/format";
```
> ⚠️ El script `packages/design-system/scripts/migrate-imports.mjs` **NO sirve tal cual** para migrar
> la app: reescribe por prefijo, pero el paquete exporta solo barrels y es un **subconjunto curado**
> → reescribir `@/components/ui/*` a lo bruto rompe los componentes que no están en el paquete. Migrá
> **consciente de componente** (solo los que existen en el paquete, a su barrel).

### Qué NO va al paquete (capa 3)
Las **pantallas/surfaces cableadas** (CartDrawer, TopBar, RentalDateModal, CartMiniBar, EquipmentCard,
FlyToCartLayer, Footer…) **se quedan en la app**. Dependen de lógica de negocio (`@/lib/cart-store`,
`@/lib/orders`, `@/lib/cotizacion`, `@/hooks/*`) que **no debe vivir en el design system**. Consumen
las piezas del paquete, pero no se mueven a él.
- El paquete trae **maquetas presentacionales** de algunas surfaces (referencia de diseño) — **no se
  adoptan** tal cual; la pantalla real de la app es la que manda (cableada).
- **`FavButton` es presentacional** (props `isFav`/`onToggle`). El hook `useFavoritos()` se cablea
  **del lado de la app** (el padre lo envuelve). No metas el hook en el paquete.

## Reglas de oro
1. El paquete es la **fuente de verdad**; editá ahí, no dupliques en `src/`.
2. **Reuse-first:** chequeá el catálogo del paquete antes de crear una pieza.
3. **Lógica de negocio nunca entra al paquete** (stores, hooks, pricing, orders, cotización).
4. Tras tocar el paquete: **`typecheck:ds` + `build`** verdes.
5. Cambio visible (rediseño) → plan de prueba + el dueño aprueba en staging. Flip no-op → reconciliá
   hacia producción.

## Punteros
| Doc | Para qué |
|---|---|
| `packages/design-system/ADOPT.md` | pasos de adopción (estrategia A workspace) + checklist |
| `packages/design-system/README.md` | qué trae el paquete |
| `docs/DESIGN_SYSTEM.md` | design system canónico (prosa: tokens, voz, patterns) |
| GitHub #662 | iniciativa de adopción (estado de consolidación en los comentarios) |
| `.claude/skills/importar-diseno/` | diseñar/importar **pantallas nuevas** (handoffs) — flujo aparte |
