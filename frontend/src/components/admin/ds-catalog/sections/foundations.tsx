/**
 * Sección Fundamentos — los tokens: colores, tipografía, radii, sombras, motion,
 * hit-area. Lo único que NO es un componente. Fuente: design-system/styles/.
 */
import { type CatalogSection } from "../types";
import { Caption, Row, Sample } from "../catalog-kit";

const BRAND_COLORS = [
  { cls: "bg-amber", label: "amarillo rambla", token: "--color-amber" },
  { cls: "bg-estudio", label: "naranja estudio", token: "--color-estudio" },
  { cls: "bg-rosa", label: "rosa escuela", token: "--color-rosa" },
  { cls: "bg-ink", label: "ink · texto/UI", token: "--color-ink" },
];

const STATUS_COLORS = [
  { cls: "bg-verde", label: "verde · éxito", token: "--color-verde" },
  { cls: "bg-azul", label: "azul · info", token: "--color-azul" },
  { cls: "bg-naranja", label: "naranja · aviso", token: "--color-naranja" },
  { cls: "bg-destructive", label: "destructive", token: "--color-destructive" },
];

const SURFACE_COLORS = [
  { cls: "bg-background", label: "background · bone", token: "--color-background" },
  { cls: "bg-surface", label: "surface", token: "--color-surface" },
  { cls: "bg-surface-elevated", label: "surface-elevated", token: "--color-surface-elevated" },
  { cls: "bg-muted", label: "muted", token: "--color-muted" },
];

function Swatch({ cls, label, token }: { cls: string; label: string; token: string }) {
  return (
    <div className="space-y-1.5">
      <div className={`h-12 w-full rounded-md border hairline ${cls}`} />
      <div className="text-xs text-ink">{label}</div>
      <Caption>{token}</Caption>
    </div>
  );
}

function SwatchGrid({ items }: { items: { cls: string; label: string; token: string }[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map((c) => (
        <Swatch key={c.token} {...c} />
      ))}
    </div>
  );
}

const RADII = [
  { cls: "rounded-sm", v: "8px" },
  { cls: "rounded-md", v: "10px" },
  { cls: "rounded-lg", v: "12px" },
  { cls: "rounded-xl", v: "16px" },
  { cls: "rounded-2xl", v: "20px" },
  { cls: "rounded-3xl", v: "24px" },
];

const SHADOWS = [
  { v: "var(--shadow-sm)", label: "sm · cards" },
  { v: "var(--shadow-md)", label: "md · dropdowns" },
  { v: "var(--shadow-lg)", label: "lg · toasts/FAB" },
  { v: "var(--shadow-xl)", label: "xl · modales" },
];

const MOTION = [
  { token: "--duration-fast", v: "120ms", use: "press" },
  { token: "--duration-base", v: "200ms", use: "hover" },
  { token: "--duration-slow", v: "350ms", use: "entradas" },
  { token: "--duration-xslow", v: "550ms", use: "hero / fly-to-cart" },
  { token: "ease-out-brand", v: "cubic-bezier(0,0,.2,1)", use: "salidas" },
  { token: "ease-bounce", v: "cubic-bezier(.34,1.56,.64,1)", use: "badge pop" },
];

export const foundationsSection: CatalogSection = {
  id: "fundamentos",
  title: "Fundamentos",
  hint: "Los tokens de marca. El futuro editor de temas cambia estos valores. Fuente: design-system/styles/.",
  specimens: [
    {
      name: "Colores",
      files: ["design-system/styles/tokens/colors.css"],
      blurb:
        "Marca (amber/estudio/rosa/ink), status (verde/azul/naranja/destructive — SOLO estados y charts) y superficies. El accent de marketing de área sale de var(--area-accent) por cascade [data-area].",
      render: () => (
        <div className="space-y-5">
          <div className="space-y-2">
            <Caption>Marca</Caption>
            <SwatchGrid items={BRAND_COLORS} />
          </div>
          <div className="space-y-2">
            <Caption>Status (solo estados y charts)</Caption>
            <SwatchGrid items={STATUS_COLORS} />
          </div>
          <div className="space-y-2">
            <Caption>Superficies</Caption>
            <SwatchGrid items={SURFACE_COLORS} />
          </div>
        </div>
      ),
    },
    {
      name: "Tipografía",
      files: ["design-system/styles/utilities.css"],
      blurb: "Recipes tipográficas (.t-*). Usalas en vez de clases sueltas de tamaño/peso.",
      render: () => (
        <div className="space-y-2">
          <div className="t-display-1 text-ink">Display 1</div>
          <div className="t-h1 text-ink">Heading 1 · .t-h1</div>
          <div className="t-h2 text-ink">Heading 2 · .t-h2</div>
          <div className="t-h3 text-ink">Heading 3 · .t-h3</div>
          <p className="t-body text-ink">Body — texto de párrafo · .t-body</p>
          <p className="t-small text-muted-foreground">Small · .t-small</p>
          <div className="t-mono text-ink">Mono · .t-mono · 1234</div>
          <div className="t-eyebrow">Eyebrow · .t-eyebrow</div>
        </div>
      ),
    },
    {
      name: "Radii",
      files: ["design-system/styles/tokens/typography.css"],
      blurb: "Radios de esquina (--radius-sm…4xl).",
      render: () => (
        <Row className="gap-4">
          {RADII.map((r) => (
            <Sample key={r.cls} label={`${r.cls} · ${r.v}`}>
              <div className={`h-14 w-14 border hairline bg-surface-elevated ${r.cls}`} />
            </Sample>
          ))}
        </Row>
      ),
    },
    {
      name: "Sombras",
      files: ["design-system/styles/tokens/shadows.css"],
      blurb: "Brand-tinted (oklch del ink, no negro puro). Opt-in: shadow-[var(--shadow-md)].",
      render: () => (
        <Row className="gap-6 py-2">
          {SHADOWS.map((s) => (
            <Sample key={s.label} label={s.label}>
              <div
                className="h-14 w-20 rounded-lg bg-surface-elevated"
                style={{ boxShadow: s.v }}
              />
            </Sample>
          ))}
        </Row>
      ),
    },
    {
      name: "Motion",
      files: ["design-system/styles/tokens/motion.css"],
      blurb: "Duraciones y easings canónicos (Tailwind genera duration-*/ease-*).",
      render: () => (
        <div className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
          {MOTION.map((m) => (
            <div key={m.token} className="flex items-baseline justify-between gap-3 text-sm">
              <code className="t-mono text-2xs text-ink">{m.token}</code>
              <span className="text-muted-foreground">
                {m.v} · {m.use}
              </span>
            </div>
          ))}
        </div>
      ),
    },
    {
      name: "Hit-area (HIG ≥44px)",
      files: ["design-system/styles/utilities.css"],
      blurb: "Tap target mínimo 44×44px (h-11 w-11). Regla táctil de Apple HIG, enforced.",
      render: () => (
        <Row className="gap-6">
          <Sample label="44×44 · ok">
            <div className="grid h-11 w-11 place-items-center rounded-md border border-verde/40 bg-verde/10 text-verde-ink">
              ✓
            </div>
          </Sample>
          <Sample label="32×32 · chico">
            <div className="grid h-8 w-8 place-items-center rounded-md border border-destructive/40 bg-destructive/10 text-destructive">
              ✕
            </div>
          </Sample>
        </Row>
      ),
    },
  ],
};
