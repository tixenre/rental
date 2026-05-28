# Rambla Rental Design Kit — INSTALL

Drop-in design system para proyectos **Tailwind v4 + React 19**. Es lo mismo que usa `tixenre/rental` en producción, empaquetado para reusar.

---

## ✦ Para Claude Code — instrucciones en una línea

> "Copiá la carpeta `kit/` de este proyecto a `src/kit/` del proyecto destino, agregá los 3 imports en `src/styles.css`, e instalá `clsx tailwind-merge class-variance-authority @radix-ui/react-slot lucide-react`."

Eso solo. Lo de abajo es el detalle.

---

## ✦ Pre-requisitos

El proyecto destino tiene que tener:

- **Tailwind v4** (`tailwindcss@^4.0.0` + `@tailwindcss/vite` o `@tailwindcss/postcss`)
- **React 19** (o 18, sirve igual)
- Un punto de entrada CSS que ya importe Tailwind (`@import "tailwindcss";`)

Si arrancás de cero con Vite:
```bash
npm create vite@latest mi-app -- --template react-ts
cd mi-app
npm install
npm install -D tailwindcss@^4 @tailwindcss/vite
```

Y en `vite.config.ts`:
```ts
import tailwindcss from "@tailwindcss/vite";
// ...
plugins: [react(), tailwindcss()],
```

---

## ✦ Paso 1 — Copiar el kit

Pegá toda la carpeta `kit/` dentro de `src/`:

```
src/
├── kit/
│   ├── fonts/                  ← TT Commons + Champ Black (.otf/.ttf)
│   ├── fonts.css
│   ├── tokens.css
│   ├── recipes.css
│   ├── index.css               ← (opcional) atajo que importa los 3
│   └── components/
│       ├── lib/cn.ts
│       ├── button.tsx
│       ├── addon-pills.tsx
│       ├── estado-badge.tsx
│       ├── equipment-card.tsx
│       ├── stat-card.tsx
│       └── topbar.tsx
└── styles.css                  ← tu CSS principal
```

---

## ✦ Paso 2 — Wirear los imports CSS

Al principio de `src/styles.css`:

```css
@import "tailwindcss";

@import "./kit/fonts.css";
@import "./kit/tokens.css";
@import "./kit/recipes.css";

/* Tu CSS de la app va acá abajo */
```

> O si querés todo en uno: `@import "./kit/index.css";` reemplaza a los tres.

JetBrains Mono se carga desde Google Fonts — agregalo en `index.html`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap"
  rel="stylesheet"
/>
```

---

## ✦ Paso 3 — Instalar dependencias

```bash
npm install clsx tailwind-merge class-variance-authority \
            @radix-ui/react-slot lucide-react
```

| Paquete | Quién lo usa |
| --- | --- |
| `clsx` + `tailwind-merge` | `cn()` en `kit/components/lib/cn.ts` |
| `class-variance-authority` | `Button` (variants) |
| `@radix-ui/react-slot` | `Button asChild` prop |
| `lucide-react` | iconos en `AddonPills`, `EquipmentCard`, `TopBar` |

---

## ✦ Paso 4 — Usalo

```tsx
import { Button } from "@/kit/components/button";
import { EquipmentCard } from "@/kit/components/equipment-card";
import { EstadoBadge } from "@/kit/components/estado-badge";

export default function Demo() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="t-display-2">conocé el estudio</h1>
      <p className="t-body text-muted-foreground">
        Cámaras, ópticas, luces y audio en Mar del Plata.
      </p>

      <div className="mt-6 flex gap-2">
        <Button>Reservar</Button>
        <Button variant="secondary" shape="pill">Ver carrito</Button>
        <EstadoBadge estado="confirmado" />
      </div>
    </main>
  );
}
```

---

## ✦ Qué hay en el kit

### Tokens (CSS)
- `tokens.css` — el `@theme inline {}` con colores, radii, type stacks. Genera utilities Tailwind: `bg-amber`, `text-ink`, `border-hairline`, `rounded-xl`, `font-display`, …
- `fonts.css` — `@font-face` para TT Commons + Champ Black.
- `recipes.css` — utilities compuestas: `.t-display-1`, `.t-h1`, `.t-eyebrow`, `.wordmark`, `.grain`, `.bg-amber-tape`, `.tabular`, `.hairline`, `.safe-t/-b/-x`.

### Componentes (React + TS)
- **`Button`** — la jugada signature de marca: hover invierte ink ⇄ amber.
  - variants: `primary` · `secondary` · `ghost` · `destructive` · `amber`
  - sizes: `sm` · `md` · `lg` · `icon`
  - shapes: `rounded` · `pill`
- **`AddonPills`** — listado horizontal "incluye" sobre rows de equipo.
- **`EstadoBadge`** — chips del ciclo de vida del pedido (`borrador` → `cancelado`).
- **`EquipmentCard`** — card 4:5 del catálogo, presentational.
- **`StatCard`** — bloque número-grande del dashboard admin.
- **`TopBar`** — header sticky con el efecto amber-scroll del mobile.

---

## ✦ Convenciones del sistema (TL;DR)

- **Color discipline** — Outside del status palette (rosa/azul/naranja/verde), la página es bone + ink + amber. Si dudás, sin gradients.
- **Type** — Champ Black SOLO en hero/openers (`t-display-1`, `t-display-2`). Headings, nombres, body, botones → TT Commons.
- **Casing** — Headlines en hero: lowercase, multi-línea con punto final. Body + botones en sentence case. Eyebrows en MONO uppercase tracked.
- **Lenguaje** — Español rioplatense, voseo. *"Reservá"*, *"Elegí fechas"*, *"Te lo dejamos listo"*. Nunca tú/usted.
- **Iconos** — Lucide React. Stroke 2. Tamaños 16px inline / 20px standalone.
- **Borders** — Una sola hairline, `border-hairline` en todos los lugares. Excepciones: date-pill (`border-2 border-ink`) y studio-CTA (2px ink sobre amber).
- **Sombras** — Cards flat. CTA primary tiene `shadow-sm`. No glassmorphism. No inner-shadow.

---

## ✦ Personalizar

¿Necesitás cambiar un color o un radio? **No edites `tokens.css` directamente** — agregá overrides en tu CSS:

```css
@import "./kit/tokens.css";

:root {
  --radius: 0.5rem;        /* radii más cuadrados */
  --rosa: #FF6B9C;         /* tu propio rosa */
}
```

Las utilities Tailwind se actualizan automáticamente.

---

## ✦ Versionado

Esta versión del kit refleja el estado de `tixenre/rental@main` al **27 de mayo de 2026**. Para sincronizar con cambios upstream:

1. Comparar `kit/tokens.css` con `src/styles.css` del repo.
2. Comparar cada `kit/components/*.tsx` con `src/components/rental/*.tsx`.
3. Re-correr `INSTALL.md` paso 2 si cambió la estructura de imports.

---

*"un lugar donde pasan cosas." — Rambla Rental · Mar del Plata*
