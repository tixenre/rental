import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  Calendar,
  MessageCircle,
  Search,
  ShoppingBag,
  LayoutGrid,
  List,
  Inbox,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { AddonPills } from "@/components/kit/AddonPills";
import { EstadoBadge } from "@/components/kit/EstadoBadge";
import { EmptyState } from "@/components/kit/EmptyState";
import { PriceBlock } from "@/components/kit/PriceBlock";
import { ViewToggle } from "@/components/kit/ViewToggle";
import { StatCard } from "@/components/kit/StatCard";
import { Input, SearchInput, FieldLabel } from "@/components/kit/Input";

/**
 * /kit-preview — galería de los componentes del kit usados desde el repo
 * real.
 *
 * No es navegable desde el sitio (no aparece en menúes) y trae `noindex`
 * en meta para que no se indexe. Sirve para verificar visualmente que las
 * variants del kit se ven igual cuando se usan vía `src/components/*` que
 * en el showcase de Claude Design (`docs/design-kit/index.html`).
 */
export const Route = createFileRoute("/kit-preview")({
  head: () => ({
    meta: [
      { title: "Kit preview — Rambla Rental" },
      { name: "robots", content: "noindex,nofollow" },
    ],
  }),
  component: KitPreviewPage,
});

function KitPreviewPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b hairline px-6 py-6 max-w-5xl mx-auto">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          INTERNAL · QA · branch button-rambla-variants
        </div>
        <h1 className="font-display text-3xl text-ink mt-1">Kit preview</h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-xl">
          Galería de los componentes del{" "}
          <code className="font-mono text-xs bg-muted px-1 rounded">docs/design-kit/</code> usados
          desde el repo real (`src/components/kit/*`). Compará con{" "}
          <a
            href="/docs/design-kit/index.html"
            className="underline hover:text-amber"
            target="_blank"
            rel="noopener noreferrer"
          >
            el showcase
          </a>{" "}
          para confirmar que se ven igual.
        </p>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-12">
        <ButtonSection />
        <AddonPillsSection />
        <EstadoBadgeSection />
        <StatCardSection />
        <PriceBlockSection />
        <ViewToggleSection />
        <InputSection />
        <EmptyStateSection />
      </main>

      <footer className="border-t hairline px-6 py-8 mt-12">
        <div className="max-w-5xl mx-auto font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Generado · {new Date().toISOString().slice(0, 10)}
        </div>
      </footer>
    </div>
  );
}

/* ───────────────────────────────────────── BUTTON ────────────────────────── */

function ButtonSection() {
  return (
    <Section
      title="Button"
      subtitle="6 variants existentes + amber nueva. Eje shape nuevo (rounded/pill). 4 sizes."
    >
      <Row label="Variants existentes (sin cambios)">
        <Button>Default</Button>
        <Button variant="destructive">Destructive</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="link">Link</Button>
      </Row>
      <Row label="Variant nueva: amber (siempre amarillo brand)">
        <Button variant="amber">Reservar</Button>
        <Button variant="amber" size="lg">
          <Calendar /> Conocé el Estudio
        </Button>
        <Button variant="amber" size="icon" aria-label="WhatsApp">
          <MessageCircle />
        </Button>
      </Row>
      <Row label='Shape "pill" (compatible con cualquier variant)'>
        <Button shape="pill">Reservar</Button>
        <Button variant="secondary" shape="pill">
          Ver carrito
        </Button>
        <Button variant="amber" shape="pill">
          Conocé el Estudio →
        </Button>
      </Row>
      <Row label="Sizes con variant amber">
        <Button variant="amber" size="sm">
          Small
        </Button>
        <Button variant="amber">Default</Button>
        <Button variant="amber" size="lg">
          Large
        </Button>
        <Button variant="amber" size="icon" aria-label="Search">
          <Search />
        </Button>
      </Row>
    </Section>
  );
}

/* ──────────────────────────────────────── ADDON PILLS ────────────────────── */

function AddonPillsSection() {
  return (
    <Section
      title="AddonPills"
      subtitle='Items "incluye" sobre la row de un equipo. Soporta qty, overflow y empty state.'
    >
      <Row label="Default — 3 items inline">
        <AddonPills
          items={[
            { id: "1", name: "Cuerpo" },
            { id: "2", name: "Batería NP-FZ100", qty: 2 },
            { id: "3", name: "Cargador dual" },
          ]}
        />
      </Row>
      <Row label="Overflow (6 items, max=3)">
        <AddonPills
          max={3}
          items={[
            { id: "1", name: "Cuerpo" },
            { id: "2", name: "Batería" },
            { id: "3", name: "Cargador" },
            { id: "4", name: "Memoria CFexpress" },
            { id: "5", name: "Lector USB-C" },
            { id: "6", name: "Estuche Pelican" },
          ]}
        />
      </Row>
      <Row label="Empty (sin addons)">
        <AddonPills items={[]} />
      </Row>
    </Section>
  );
}

/* ──────────────────────────────────────── ESTADO BADGE ───────────────────── */

function EstadoBadgeSection() {
  const estados = [
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
  return (
    <Section
      title="EstadoBadge"
      subtitle="Ciclo de vida del pedido — 9 estados con paleta secundaria de marca."
    >
      <Row label="Todos los estados">
        {estados.map((e) => (
          <EstadoBadge key={e} estado={e} />
        ))}
      </Row>
    </Section>
  );
}

/* ──────────────────────────────────────── STAT CARD ──────────────────────── */

function StatCardSection() {
  return (
    <Section title="StatCard" subtitle="Bloque número grande del dashboard admin. Tabular nums.">
      <Row label="Grid típico">
        <StatCard label="Pedidos · mayo" value="42" meta="+8 vs. abril" />
        <StatCard label="Ingresos" value="$ 2.840.500" meta="ARS · mayo" />
        <StatCard
          label="Sin stock"
          value="3"
          valueClassName="text-destructive"
          meta="Equipos críticos"
        />
        <StatCard label="Equipos activos" value="187" />
      </Row>
    </Section>
  );
}

/* ──────────────────────────────────────── PRICE BLOCK ────────────────────── */

function PriceBlockSection() {
  return (
    <Section title="PriceBlock" subtitle="Precio + tarifa. Mono meta abajo, display chunky arriba.">
      <Row label="1 jornada → por día">
        <div className="rounded-lg border hairline bg-surface-elevated p-3">
          <PriceBlock pricePerDay={24500} />
        </div>
        <div className="rounded-lg border hairline bg-surface-elevated p-3">
          <PriceBlock pricePerDay={97500} />
        </div>
      </Row>
      <Row label="N jornadas → total + tarifa por jornada">
        <div className="rounded-lg border hairline bg-surface-elevated p-3">
          <PriceBlock pricePerDay={24500} jornadas={3} />
        </div>
        <div className="rounded-lg border hairline bg-surface-elevated p-3">
          <PriceBlock pricePerDay={97500} jornadas={5} />
        </div>
      </Row>
      <Row label="Con sufijo opcional">
        <div className="rounded-lg border hairline bg-surface-elevated p-3">
          <PriceBlock pricePerDay={24500} suffix=" + IVA" />
        </div>
      </Row>
    </Section>
  );
}

/* ──────────────────────────────────────── VIEW TOGGLE ────────────────────── */

function ViewToggleSection() {
  const [view, setView] = useState<"grid" | "list">("grid");
  const [estado, setEstado] = useState<"draft" | "published">("draft");
  return (
    <Section
      title="ViewToggle"
      subtitle="Segmented control con pill deslizante. Hacé click para ver la animación."
    >
      <Row label="Grid / Lista (catálogo)">
        <ViewToggle
          value={view}
          onChange={setView}
          options={[
            { value: "grid", label: "Grid", icon: <LayoutGrid className="h-4 w-4" /> },
            { value: "list", label: "Lista", icon: <List className="h-4 w-4" /> },
          ]}
        />
        <span className="font-mono text-xs text-muted-foreground">activo: {view}</span>
      </Row>
      <Row label="Borrador / Publicado (admin)">
        <ViewToggle
          value={estado}
          onChange={setEstado}
          options={[
            { value: "draft", label: "Borrador" },
            { value: "published", label: "Publicado" },
          ]}
        />
        <span className="font-mono text-xs text-muted-foreground">activo: {estado}</span>
      </Row>
    </Section>
  );
}

/* ──────────────────────────────────────── INPUT ──────────────────────────── */

function InputSection() {
  return (
    <Section
      title="Input · SearchInput · FieldLabel"
      subtitle="Campo texto branded, search pill con icono, y el eyebrow mono que va arriba de cada campo."
    >
      <Row label="Input standard con FieldLabel">
        <div className="space-y-1.5 w-64">
          <FieldLabel htmlFor="kit-email">Email</FieldLabel>
          <Input id="kit-email" type="email" placeholder="hola@productora.com" />
        </div>
        <div className="space-y-1.5 w-64">
          <FieldLabel htmlFor="kit-cuit">CUIT</FieldLabel>
          <Input id="kit-cuit" placeholder="30-12345678-9" />
        </div>
      </Row>
      <Row label="SearchInput (pill con icono)">
        <div className="w-80">
          <SearchInput placeholder="Buscar equipo, marca, pack…" />
        </div>
      </Row>
      <Row label="Estados (disabled)">
        <div className="w-64">
          <Input placeholder="Disabled" disabled />
        </div>
      </Row>
    </Section>
  );
}

/* ──────────────────────────────────────── EMPTY STATE ────────────────────── */

function EmptyStateSection() {
  return (
    <Section
      title="EmptyState"
      subtitle='"Nada para mostrar" — icono amber-soft + título display + acción opcional.'
    >
      <Row label="Search empty (chips de sugerencias)">
        <div className="w-full max-w-md">
          <EmptyState
            icon={<Search className="h-6 w-6" />}
            title="Sin resultados"
            sub="Probá con otra categoría, marca o término de búsqueda."
          >
            <div className="flex gap-1.5 flex-wrap justify-center">
              {["Cámaras", "Lentes", "Audio", "Iluminación"].map((c) => (
                <button
                  key={c}
                  type="button"
                  className="px-2.5 py-1 rounded-full border hairline bg-surface-elevated text-xs hover:border-ink hover:bg-muted"
                >
                  {c}
                </button>
              ))}
            </div>
          </EmptyState>
        </div>
      </Row>
      <Row label="Carrito vacío (con CTA)">
        <div className="w-full max-w-md">
          <EmptyState
            icon={<ShoppingBag className="h-6 w-6" />}
            title="Tu pedido está vacío"
            sub="Sumá equipos desde el catálogo para armar tu reserva."
          >
            <Button variant="amber" shape="pill">
              Explorar catálogo →
            </Button>
          </EmptyState>
        </div>
      </Row>
      <Row label="Sin pedidos (portal cliente)">
        <div className="w-full max-w-md">
          <EmptyState
            icon={<Inbox className="h-6 w-6" />}
            title="Todavía no tenés pedidos"
            sub="Cuando hagas tu primera reserva, va a aparecer acá."
            dashed={false}
            className="bg-surface border border-hairline"
          />
        </div>
      </Row>
      <Row label='Producto destacado ("estrella")'>
        <div className="w-full max-w-md">
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title="Producto estrella"
            sub="Variante decorativa — no es un empty state real, sólo demuestra el patrón."
          />
        </div>
      </Row>
    </Section>
  );
}

/* ──────────────────────────────────────── LAYOUT HELPERS ─────────────────── */

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          {title.split(" · ")[0]}
        </div>
        <h2 className="font-display text-xl text-ink">{title}</h2>
        {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border hairline bg-surface p-4">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-3">
        {label}
      </div>
      <div className="flex flex-wrap gap-3 items-center">{children}</div>
    </div>
  );
}
