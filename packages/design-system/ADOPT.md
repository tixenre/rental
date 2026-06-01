# Adopción — cómo el repo `tixenre/rental` consume este DS

Objetivo: **invertir la fuente de verdad**. Hoy `src/styles.css` y `src/components/*` viven en el repo. Después de esto, viven en `@rambla/design-system` y el repo los importa. Cero duplicación, cero drift.

Elegí **una** de las dos estrategias.

---

## Estrategia A — Workspace package (recomendada, limpia)

Trata al DS como paquete versionable. Ideal si el repo es (o puede ser) un monorepo pnpm/npm workspaces.

1. **Colocá el paquete** en el repo:
   ```
   tixenre/rental/
   ├─ packages/design-system/   ← copiá acá el contenido de rambla-design-system/
   └─ app/  (o la raíz actual)
   ```

2. **Declaralo como workspace** (`package.json` raíz):
   ```jsonc
   { "workspaces": ["packages/*", "app"] }
   ```

3. **Dependé de él** desde la app:
   ```bash
   pnpm add @rambla/design-system@workspace:*   # o npm/yarn equivalente
   ```

4. **Reemplazá el CSS entry** — en `src/main.tsx` borrá el `import "./styles.css"` y poné:
   ```ts
   import "@rambla/design-system/styles.css";
   ```
   Después borrá el viejo `src/styles.css` del repo (su contenido ya vive en el paquete).

5. **Apuntá los imports de componentes** al paquete y borrá los duplicados del repo
   (`src/components/ui|kit|rental`, `src/lib/utils.ts`, `src/lib/format.ts`,
   `src/assets/fonts`, `src/assets/brand`). Buscá y reemplazá:
   ```
   @/components/ui      → @rambla/design-system/components/ui
   @/components/kit     → @rambla/design-system/components/kit
   @/components/rental  → @rambla/design-system/components/rental
   @/lib/format         → @rambla/design-system/lib/format
   @/assets/brand       → @rambla/design-system/brand
   ```

6. **Tailwind v4 debe escanear el paquete** para no purgar sus clases. En el CSS
   de la app (o el entry), agregá:
   ```css
   @source "../packages/design-system/src";
   ```

---

## Estrategia B — Overlay in-place (rápida, sin tocar el build)

Si no querés mover a workspaces todavía: el paquete espeja `src/`, así que se
copia encima.

1. Copiá `rambla-design-system/src/**` sobre el `src/**` del repo
   (reemplaza `styles.css`, `lib/utils.ts`, `lib/format.ts`, `assets/fonts`,
   `assets/brand`, y `components/ui|kit|rental`).
2. Los imports `@/...` siguen funcionando sin tocar nada (el alias del repo ya
   resuelve `@/* → src/*`).
3. `tokens.json`, `README.md` y `ADOPT.md` van a `docs/design-system/` (referencia).

> Trade-off: B es un copy-paste y listo, pero el DS deja de estar “versionado”
> aparte. A es la forma correcta a mediano plazo.

---

## Peer dependencies

El paquete asume que el repo ya tiene (todas son del stack actual):

```
react ≥18 · react-dom ≥18 · tailwindcss ^4 · lucide-react
class-variance-authority · @radix-ui/react-slot · clsx · tailwind-merge
date-fns · framer-motion · react-day-picker
```

No agrega ninguna dependencia nueva.

---

## Diferencias vs. el mirror anterior (revisar en el PR)

El mirror viejo (`colors_and_type.css`) usaba variables **planas** (`--amber`,
`--ink`). Este paquete usa el namespace **correcto de Tailwind v4** para que las
utilities se generen de verdad:

| Mirror viejo | Canónico (este paquete) | Genera |
|---|---|---|
| `--amber` | `--color-amber` | `bg-amber`, `text-amber`, `border-amber` |
| `--ink` | `--color-ink` | `bg-ink`, `text-ink` |
| `--hairline` | `--color-hairline` | `border-hairline` |
| `--surface-elevated` | `--color-surface-elevated` | `bg-surface-elevated` |

Si tu `src/styles.css` actual ya definía `--color-*` (porque las utilities ya
funcionaban), los **valores** son idénticos — solo confirmá que no quede una
copia paralela de tokens.

---

## Componentes canónicos — nota de migración

Los 19 componentes son **los verificados** y pasan a ser la fuente de verdad.
Al portarlos se reconstruyó **`src/components/kit/types.ts`** (`EstadoPedido`,
`AddonItem`) que en el repo vivía aparte. **Reconciliá esa unión** con los tipos
reales de la API de pedidos antes de mergear — si el repo tiene un estado extra
(o uno con otro nombre), ganá el de la API y actualizá `types.ts` + el `ESTADO_MAP`
de `EstadoBadge`.

Sin dependencias colgando: todo lo que importan resuelve dentro del paquete
(`@/lib/*`, `@/components/kit/*`) o son peer deps del stack (`lucide-react`,
`framer-motion`, `react-day-picker`, `date-fns`, `@radix-ui/react-slot`, `cva`).
`FavButton` es presentacional (controlado por props) — el hook `useFavoritos()`
queda del lado de la app, no del DS.

## Checklist de verificación post-merge

- [ ] `import "@rambla/design-system/styles.css"` carga fuentes y tokens (probar `font-display`, `bg-amber`).
- [ ] `bg-amber` / `text-ink` / `border-hairline` / `shadow-md` / `rounded-lg` rinden.
- [ ] Dark mode: `.dark` en `<html>` switchea surfaces; amber permanece.
- [ ] `<Button variant="primary">` invierte ink↔amber en hover.
- [ ] `StepperPill`, `EstadoBadge`, `PriceBlock` renderizan igual que antes.
- [ ] `formatARS(24500)` → `"$ 24.500"`; `formatARS(145500,{iva:true})` → `"$ 145.500 + IVA"`.
- [ ] Wordmark SVG toma color vía `currentColor` (probá `text-amber` y en topbar amber).
- [ ] Tailwind no purga clases del paquete (`@source` agregado en estrategia A).
- [ ] No quedó NINGÚN `src/styles.css` ni `components/*` duplicado en el repo.
- [ ] CI/linter de tokens pasa (sin hex crudo ni Tailwind genérico).
