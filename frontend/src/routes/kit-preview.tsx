import { createFileRoute } from "@tanstack/react-router";

import { EstadoBadge } from "@/design-system/kit/EstadoBadge";
import { PagoBadge } from "@/design-system/kit/PagoBadge";
import { Pill } from "@/design-system/kit/Pill";
import { Button } from "@/design-system/ui/button";
import { Spinner } from "@/design-system/ui/spinner";

export const Route = createFileRoute("/kit-preview")({
  head: () => ({
    meta: [
      { title: "Kit preview — Rambla Rental DS" },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
  component: KitPreviewPage,
});

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-10">
      <h2 className="mb-4 border-b border-hairline pb-2 text-sm font-semibold uppercase tracking-widest text-muted-foreground">
        {title}
      </h2>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </section>
  );
}

function KitPreviewPage() {
  return (
    <div className="min-h-screen bg-background px-6 py-10">
      <div className="mx-auto max-w-3xl">
        <h1 className="mb-1 text-2xl font-bold">Kit Preview</h1>
        <p className="mb-10 text-sm text-muted-foreground">
          Galería de componentes del Design System. Solo visible en staging (no indexada).
        </p>

        <Section title="Pill — tonos semánticos">
          <Pill tone="success">Confirmado</Pill>
          <Pill tone="warning">Pendiente</Pill>
          <Pill tone="danger">Cancelado</Pill>
          <Pill tone="info">Presupuesto</Pill>
          <Pill tone="neutral">Borrador</Pill>
        </Section>

        <Section title="EstadoBadge">
          <EstadoBadge estado="presupuesto" />
          <EstadoBadge estado="confirmado" />
          <EstadoBadge estado="entregado" />
          <EstadoBadge estado="devuelto" />
          <EstadoBadge estado="cancelado" />
        </Section>

        <Section title="PagoBadge">
          <PagoBadge pagado={0} total={5000} estado="confirmado" />
          <PagoBadge pagado={2500} total={5000} estado="confirmado" />
          <PagoBadge pagado={5000} total={5000} estado="devuelto" />
          <PagoBadge pagado={0} total={5000} estado="presupuesto" />
        </Section>

        <Section title="Spinner — tamaños">
          <Spinner size="xs" />
          <Spinner size="sm" />
          <Spinner size="md" />
          <Spinner size="lg" />
        </Section>

        <Section title="Button — variantes">
          <Button variant="primary">Primary</Button>
          <Button variant="amber">Amber</Button>
          <Button variant="default">Default</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Destructive</Button>
        </Section>

        <Section title="Button — loading">
          <Button variant="primary" loading>
            Guardando…
          </Button>
          <Button variant="amber" loading>
            Procesando…
          </Button>
          <Button variant="outline" loading>
            Cargando…
          </Button>
        </Section>

        <Section title="Button — shapes">
          <Button variant="primary" shape="rounded">
            Redondeado
          </Button>
          <Button variant="primary" shape="pill">
            Pill
          </Button>
        </Section>

        <Section title="Button — sizes">
          <Button variant="primary" size="sm">
            Small
          </Button>
          <Button variant="primary" size="default">
            Default
          </Button>
          <Button variant="primary" size="lg">
            Large
          </Button>
        </Section>
      </div>
    </div>
  );
}
