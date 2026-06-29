/**
 * DsCatalog — galería en vivo del Design System (la fuente de verdad, visible).
 *
 * Muestra los componentes y tokens del DS de Rambla: lo que hay que REUSAR (no
 * recrear). Read-only por ahora; es la puerta de entrada al futuro editor de
 * temas (los tokens de color de acá son los que ese editor va a poder cambiar).
 * Se renderiza como solapa dentro de "Assets y diseño".
 */
import { Inbox, Sparkles } from "lucide-react";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Textarea } from "@/design-system/ui/textarea";
import { Checkbox } from "@/design-system/ui/checkbox";
import { Switch } from "@/design-system/ui/switch";
import { Badge } from "@/design-system/ui/badge";
import { Pill } from "@/design-system/kit/Pill";
import { EstadoBadge } from "@/design-system/kit/EstadoBadge";
import { Field } from "@/design-system/kit/Field";
import { Monto, PrecioUnidad } from "@/components/admin/Monto";
import { unidadLabel } from "@/lib/format";
import { EmptyState } from "@/components/rental/EmptyState";
import { ErrorState } from "@/components/admin/ErrorState";
import { TableSkeleton } from "@/components/admin/skeletons";

const COLOR_TOKENS: { name: string; cls: string; label: string }[] = [
  { name: "--color-amber", cls: "bg-amber", label: "amber (rental)" },
  { name: "--color-estudio", cls: "bg-estudio", label: "estudio" },
  { name: "--color-rosa", cls: "bg-rosa", label: "rosa (workshops)" },
  { name: "--color-azul", cls: "bg-azul", label: "azul (info)" },
  { name: "--color-verde", cls: "bg-verde", label: "verde (éxito)" },
  { name: "--color-naranja", cls: "bg-naranja", label: "naranja (aviso)" },
  { name: "--color-destructive", cls: "bg-destructive", label: "destructive" },
  { name: "--color-ink", cls: "bg-ink", label: "ink (texto/UI)" },
  { name: "--color-background", cls: "bg-background", label: "background (bone)" },
  { name: "--color-surface", cls: "bg-surface", label: "surface" },
  { name: "--color-surface-elevated", cls: "bg-surface-elevated", label: "surface-elevated" },
  { name: "--color-muted", cls: "bg-muted", label: "muted" },
];

const ESTADOS = [
  "borrador",
  "presupuesto",
  "solicitado",
  "confirmado",
  "retirado",
  "entregado",
  "devuelto",
  "finalizado",
  "cancelado",
] as const;

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">{title}</h2>
        {hint && <p className="text-sm text-muted-foreground">{hint}</p>}
      </div>
      <div className="rounded-xl border hairline bg-surface-elevated p-5">{children}</div>
    </section>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center gap-3">{children}</div>;
}

export function DsCatalog() {
  return (
    <div className="space-y-8">
      {/* ── Colores (tokens) ─────────────────────────────────────────── */}
      <Section
        title="Colores (tokens)"
        hint="Las variables CSS de marca y estado. El futuro editor de temas cambia estos valores."
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {COLOR_TOKENS.map((t) => (
            <div key={t.name} className="space-y-1.5">
              <div className={`h-12 w-full rounded-md border hairline ${t.cls}`} />
              <div className="text-xs text-ink">{t.label}</div>
              <div className="t-eyebrow normal-case">{t.name}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* ── Tipografía ───────────────────────────────────────────────── */}
      <Section
        title="Tipografía"
        hint="Recipes tipográficas (utilities.css). Usalas en vez de clases sueltas."
      >
        <div className="space-y-2">
          <div className="t-display-1 text-ink">Display 1</div>
          <div className="t-h1 text-ink">Heading 1 (.t-h1)</div>
          <div className="t-h2 text-ink">Heading 2 (.t-h2)</div>
          <div className="t-h3 text-ink">Heading 3 (.t-h3)</div>
          <p className="t-body text-ink">Body — texto de párrafo (.t-body).</p>
          <div className="t-eyebrow">Eyebrow (.t-eyebrow)</div>
        </div>
      </Section>

      {/* ── Botones ──────────────────────────────────────────────────── */}
      <Section
        title="Botones"
        hint="<Button variant size>. Una sola fuente — no escribir <button> a mano."
      >
        <div className="space-y-4">
          <Row>
            <Button variant="primary">Primary</Button>
            <Button variant="amber">Amber</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
            <Button variant="link">Link</Button>
          </Row>
          <Row>
            <Button size="sm">sm</Button>
            <Button size="default">default</Button>
            <Button size="lg">lg</Button>
            <Button shape="pill" variant="primary">
              pill
            </Button>
            <Button loading>loading</Button>
            <Button disabled>disabled</Button>
          </Row>
        </div>
      </Section>

      {/* ── Badges / Pills ───────────────────────────────────────────── */}
      <Section
        title="Badges y Pills"
        hint="<Pill tone> y <EstadoBadge>. Para chips de estado — no <span> a mano."
      >
        <div className="space-y-4">
          <Row>
            <Pill tone="success">success</Pill>
            <Pill tone="warning">warning</Pill>
            <Pill tone="danger">danger</Pill>
            <Pill tone="info">info</Pill>
            <Pill tone="neutral">neutral</Pill>
          </Row>
          <Row>
            {ESTADOS.map((e) => (
              <EstadoBadge key={e} estado={e} />
            ))}
          </Row>
          <Row>
            <Badge>Badge</Badge>
            <Badge variant="secondary">secondary</Badge>
            <Badge variant="outline">outline</Badge>
            <Badge variant="destructive">destructive</Badge>
          </Row>
        </div>
      </Section>

      {/* ── Campos ───────────────────────────────────────────────────── */}
      <Section
        title="Campos de formulario"
        hint="<Input>/<Textarea>/<Field>/<Checkbox>/<Switch>. No <input> a mano."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Input" hint="texto, número, fecha…">
            <Input placeholder="Escribí algo" />
          </Field>
          <Field label="Con error" error="Este campo es obligatorio">
            <Input placeholder="Monto" />
          </Field>
          <Field label="Textarea">
            <Textarea placeholder="Una descripción más larga…" />
          </Field>
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm text-ink">
              <Checkbox defaultChecked /> Checkbox
            </label>
            <label className="flex items-center gap-2 text-sm text-ink">
              <Switch defaultChecked /> Switch
            </label>
          </div>
        </div>
      </Section>

      {/* ── Plata ────────────────────────────────────────────────────── */}
      <Section
        title="Plata"
        hint="Un componente por tipo de plata: <Monto> (montos, con tono y moneda) y <PrecioUnidad> (precio de alquiler)."
      >
        <div className="space-y-3">
          <Row>
            <Monto value={97500} />
            <span className="text-muted-foreground">·</span>
            <Monto value={0} />
            <span className="text-muted-foreground">·</span>
            <Monto value={45000} tone="debt" />
            <span className="text-muted-foreground">·</span>
            <Monto value={250000} tone="strong" />
            <span className="text-muted-foreground">·</span>
            <Monto value={1200} moneda="USD" />
          </Row>
          <Row>
            <PrecioUnidad value={12000} />
            <span className="text-muted-foreground">·</span>
            <PrecioUnidad value={8000} unidad="hora" />
            <span className="text-muted-foreground">·</span>
            <PrecioUnidad value={12000} compact />
            <span className="text-muted-foreground">·</span>
            <PrecioUnidad value={8000} unidad="hora" compact />
          </Row>
          <Row>
            <span className="text-sm text-ink">{unidadLabel(1)}</span>
            <span className="text-muted-foreground">·</span>
            <span className="text-sm text-ink">{unidadLabel(3)}</span>
            <span className="text-muted-foreground">·</span>
            <span className="text-sm text-ink">{unidadLabel(2, "hora")}</span>
          </Row>
        </div>
      </Section>

      {/* ── Estados ──────────────────────────────────────────────────── */}
      <Section
        title="Estados (carga / vacío / error)"
        hint="<QueryState> los cablea; acá los primitivos."
      >
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-md border hairline p-3">
            <TableSkeleton rows={3} cols={3} />
          </div>
          <div className="rounded-md border hairline">
            <EmptyState
              icon={<Inbox className="h-6 w-6" />}
              title="Sin datos"
              sub="No hay nada todavía."
            />
          </div>
          <div className="rounded-md border hairline">
            <ErrorState onRetry={() => {}} />
          </div>
        </div>
      </Section>

      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <Sparkles className="h-3.5 w-3.5" />
        Próximo: editor de temas — cambiar estos tokens desde acá, con preview en vivo.
      </p>
    </div>
  );
}
