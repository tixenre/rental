# feat(design-system): adoptar @rambla/design-system como fuente de verdad

## Qué hace este PR

Invierte la dirección del design system. Hasta ahora los tokens, fuentes, assets
y componentes vivían sueltos en `src/` y el DS externo los **espejaba**. A partir
de este PR el paquete **`@rambla/design-system`** es la fuente de verdad y la app
lo **consume**. Una sola fuente, cero drift.

```
app (tixenre/rental)  ──importa──▶  @rambla/design-system  ◀── se edita acá
```

## Por qué

- **Drift:** mantener tokens en dos lados garantizaba que se desincronizaran.
- **Fix real de tokens:** el espejo viejo usaba variables planas (`--amber`); el
  paquete usa el namespace correcto de Tailwind v4 (`--color-amber`) para que las
  utilities `bg-amber` / `text-ink` / `border-hairline` se generen de verdad. Los
  **valores son idénticos** — sólo cambia el nombre de la variable.
- **Modularidad:** cada capa de token es un archivo (`tokens/colors.css`,
  `typography.css`, `shadows.css`, `motion.css`, `z-index.css`); Tailwind v4
  mergea los `@theme`. Cambiar un color = tocar un solo archivo.

## Qué cambió

**Nuevo paquete** (`packages/design-system/` ó overlay sobre `src/`):

- `src/styles.css` — entry canónico (reemplaza al `src/styles.css` del repo).
- `src/styles/tokens/*` — tokens por capa (`@theme` + `:root`).
  - `typography.css` → font stacks **+ radii** (`--radius-sm…4xl`).
  - `colors.css`, `shadows.css`, `motion.css`, `z-index.css`.
- `src/styles/fonts.css` — `@font-face` (TT Commons + Champ Black).
- `src/styles/utilities.css` — recetas `.t-*`, `.wordmark`, `.bg-amber-tape`,
  `.grain`, safe-area, `::selection`, fix de zoom iOS, modifiers de calendario
  (`.rdp-nostock/.rdp-closed`), animaciones de topbar y keyframes
  (`expand-in`, `slide-up`, `slide-in-right`).
- `src/lib/` — `utils.ts` (`cn`), `format.ts` (`formatARS`, `formatShortDate`,
  `formatRentalRange`, `jornadaLabel`, `priceBreakdown`).
- `src/assets/` — fuentes vendoreadas + brand (`wordmark.svg` e `isologo.svg`
  ahora **themables** vía `currentColor`) + `brand/index.ts` (manifest).
- `src/components/` — `ui/` · `kit/` · `rental/` (19 componentes, los verificados)
  con barrels. Se reconstruyó `kit/types.ts` (`EstadoPedido`, `AddonItem`).
- `tokens.json` — tokens machine-readable (Style Dictionary / tooling).
- `styleguide/` — styleguide vivo navegable (58 specimens) para QA visual.

**App:**

- Entry CSS: `import "@rambla/design-system/styles.css"`.
- Imports repointeados al paquete (ver script abajo).
- Eliminados los duplicados del repo (`src/styles.css`, `lib/format.ts`,
  `components/{ui,kit,rental}`, `assets/{fonts,brand}`).

## Cómo migrar (reproducible)

```bash
# 1. dry-run — muestra qué imports se reescriben, no toca nada
node packages/design-system/scripts/migrate-imports.mjs --app src

# 2. aplicar
node packages/design-system/scripts/migrate-imports.mjs --app src --apply

# 3. swap del entry CSS (manual) en src/main.tsx:
#    - import "./styles.css"
#    + import "@rambla/design-system/styles.css"

# 4. Tailwind v4 debe escanear el paquete (en el CSS de la app):
#    @source "../packages/design-system/src";

# 5. borrar duplicados (los lista el script) y correr build + lint
```

> El script deja `@/lib/utils` sin tocar a propósito: el `utils.ts` del repo puede
> tener helpers además de `cn()`. Repointealo a mano sólo si es únicamente `cn`.

## Cómo testear

- [ ] `pnpm build` y `pnpm dev` levantan sin errores de resolución.
- [ ] `bg-amber` / `text-ink` / `border-hairline` / `shadow-md` / `rounded-lg` rinden.
- [ ] Dark mode: `.dark` en `<html>` switchea surfaces; amber permanece.
- [ ] `<Button variant="primary">` invierte ink↔amber en hover.
- [ ] `StepperPill`, `EstadoBadge`, `PriceBlock` idénticos a antes.
- [ ] `formatARS(24500)` → `"$ 24.500"` · `formatARS(145500,{iva:true})` → `"$ 145.500 + IVA"`.
- [ ] Wordmark SVG toma color por `currentColor` (probar `text-amber` y topbar amber).
- [ ] Lint de tokens pasa (sin hex crudo ni Tailwind genérico).
- [ ] No quedó ningún `styles.css` / `components/*` duplicado en el repo.

## Riesgo / rollback

- **Riesgo bajo:** los valores de token no cambian, sólo su origen y nombre.
- **A revisar antes de mergear:** la unión `EstadoPedido` en `kit/types.ts` se
  reconstruyó — reconciliar con los estados reales de la API; si hay uno extra,
  gana la API y se actualiza `types.ts` + el `ESTADO_MAP` de `EstadoBadge`.
- **A revisar:** los valores de `.topbar-seal/.topbar-snap` y `.rdp-nostock/.rdp-closed`
  en `utilities.css` se implementaron con defaults sensatos — confirmá contra el
  comportamiento esperado.
- **Rollback:** revertir el PR restaura `src/` tal cual; el paquete no tiene side-effects
  más allá del CSS entry.

## Optimización opcional (no bloqueante)

Fuentes vendoreadas como `.otf/.ttf`. Para web conviene `.woff2` subseteado —
comando `pyftsubset` en `packages/design-system/README.md`.
