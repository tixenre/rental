# Tokens propuestos para `src/styles.css`

Valores recomendados para los 4 sets de tokens que el kit documenta pero que
todavía no están en producción. Calibrados sobre los patterns reales del repo
(CartMiniBar, hover lifts, Framer Motion transitions, etc.) — no genéricos.

> Cuando estos tokens entren al `@theme inline` block de `src/styles.css`,
> `docs/DESIGN_SYSTEM.md` debe actualizarse para sacarlos de la sección
> "Tokens que el kit documenta y NO existen en el repo hoy".

---

## Shadows

```css
--shadow-sm:  0 1px 2px oklch(0.18 0.01 60 / 6%);
--shadow-md:  0 4px 12px oklch(0.18 0.01 60 / 8%),  0 1px 3px oklch(0.18 0.01 60 / 5%);
--shadow-lg:  0 12px 32px oklch(0.18 0.01 60 / 10%), 0 2px 8px oklch(0.18 0.01 60 / 6%);
--shadow-xl:  0 24px 56px oklch(0.18 0.01 60 / 12%), 0 6px 16px oklch(0.18 0.01 60 / 8%);

/* Las sombras signature siguen siendo inline (no son tokens):
   --signature-cart-bar:     shadow-[0_-8px_32px_-8px_rgba(0,0,0,0.15)]
   --signature-cart-preview: shadow-[0_-12px_24px_-8px_rgba(0,0,0,0.08)]
*/
```

**Mapeo a uso real:**
- `shadow-sm` → cards en reposo, EquipmentCard, StatCard
- `shadow-md` → dropdowns, popovers, date picker, card hover lift (~-2px translateY)
- `shadow-lg` → toasts (sonner), FABs
- `shadow-xl` → modales, RentalDateModal, dialogs de confirmación

**Por qué oklch + alpha del ink:** las sombras de Tailwind default (negro puro) chocan con el bone+ink cálido del kit. Tintarlas con `oklch(0.18 0.01 60)` mantiene el tono cálido del sistema.

---

## Motion

```css
--duration-fast:  120ms;   /* press states, button bumps */
--duration-base:  200ms;   /* hover transitions, color changes */
--duration-slow:  350ms;   /* entry animations, slide-up */
--duration-xslow: 550ms;   /* fly-to-cart, hero reveals */

--ease-default: cubic-bezier(0.32, 0.72, 0, 1);   /* snappy settle, drawer */
--ease-out:     cubic-bezier(0, 0, 0.2, 1);        /* standard decel */
--ease-bounce:  cubic-bezier(0.34, 1.56, 0.64, 1); /* overshoot, badge pop */
```

**Por qué estos valores:**
- `--duration-fast 120ms` ya está implícita en `button:active` press state (no es nuevo, solo se nombra)
- `--duration-xslow 550ms` matchea exactamente el `transition: { duration: 0.55 }` del FlyToCartLayer
- `--ease-default [0.32, 0.72, 0, 1]` es el mismo del CartDrawer Framer Motion — "snappy settle" significa arranca rápido pero desacelera mucho al final
- `--ease-bounce` es la signature del badge bump al recibir el +1

**Uso en Tailwind v4** (sin tokens custom, ya funciona):
```tsx
className="transition duration-150 ease-out"     // botones, hovers
className="transition-transform duration-300"   // hero, slow reveals
```

**Uso si se agregan los tokens:**
```tsx
className="transition duration-[var(--duration-fast)] ease-[var(--ease-default)]"
```

---

## Spacing scale

```css
/* No hace falta agregar nada — Tailwind v4 ya provee p-1...p-96 sobre base 4px.
 * NO crear --space-* tokens; sería redundante y rompería intuición de los devs
 * que ya saben Tailwind. */
```

**Referencia rápida (Tailwind defaults):**

| Tailwind | px | Uso típico |
|---|---|---|
| `p-1` `gap-1` | 4 | Stepper button gap |
| `p-2` `gap-2` | 8 | Chip rail gap, inline pill gap |
| `p-3` `gap-3` | 12 | Card body padding, button gap |
| `p-4` `gap-4` | 16 | Drawer item padding |
| `p-6` `gap-6` | 24 | Section padding, card padding |
| `p-8` `gap-8` | 32 | Hero padding mobile |
| `p-12` `gap-12` | 48 | Hero padding desktop, container padding |
| `p-16` | 64 | Hero padding XL |

---

## Z-index — ya están en producción

```css
/* Estos ya viven en :root de src/styles.css. Documentado acá por
 * completitud y para que Claude Code no invente nombres nuevos. */
--z-sub-toolbar:    30;
--z-cat-bar:        40;
--z-cart-strip:     45;
--z-topbar-amber:   49;
--z-topbar:         50;
--z-scrim:          60;
--z-drawer:         61;
```

**Nada que agregar — solo no romper la nomenclatura.**

---

## Resumen para PR

**Archivos a tocar:**
- `src/styles.css` — agregar bloques `--shadow-*` y `--duration-*` + `--ease-*` dentro del `:root`
- `docs/DESIGN_SYSTEM.md` — sacar las advertencias "tokens que no existen"
- `docs/design-kit/CLAUDE.md` — opcional: actualizar el banner para reflejar que ya entraron
- Cuando los tokens estén, las callouts ⚠ "production drift" en `docs/design-kit/extended.html` se pueden remover

**No agregar:**
- `--space-*` tokens (Tailwind ya cubre)
- Z-index nuevos (ya están)

**Verificación post-merge:**
```bash
# Búsqueda de tokens inventados que deberían dejar de aparecer en código nuevo:
rg --type tsx --type css "var\(--shadow-(sm|md|lg|xl)\)" src/
rg --type tsx --type css "var\(--duration-" src/
rg --type tsx --type css "var\(--ease-" src/
```

Después del merge, esos tokens son válidos en `src/`.
