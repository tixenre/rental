/**
 * catalog-kit — primitivos de layout DEL CATÁLOGO (no del producto).
 *
 * Son la "tipografía" interna de la vitrina: cómo se dibuja una sección, un
 * specimen, una fila de ejemplos. Viven solo acá; no confundir con el DS real
 * (`design-system/*`), que es lo que la vitrina muestra.
 */
import { type ReactNode } from "react";

import { cn } from "@/lib/utils";
import type { CatalogSection, LayerGroup, LayerMeta, Specimen } from "./types";

/** Fila de ejemplos en línea (botones, pills…), con wrap. */
export function Row({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex flex-wrap items-center gap-3", className)}>{children}</div>;
}

/** Columna de ejemplos apilados. */
export function Stack({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex flex-col gap-3", className)}>{children}</div>;
}

/** Etiqueta chiquita debajo de un ejemplo ("hover", "disabled", "/jornada"…). */
export function Caption({ children }: { children: ReactNode }) {
  return <span className="t-eyebrow normal-case text-muted-foreground">{children}</span>;
}

/** Un ejemplo rotulado: el render + su caption abajo. */
export function Sample({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-1.5">
      <div>{children}</div>
      <Caption>{label}</Caption>
    </div>
  );
}

/**
 * SpecimenCard — la tarjeta de un componente: nombre + archivo fuente + blurb +
 * el demo en vivo en su lienzo.
 */
function SpecimenCard({ spec }: { spec: Specimen }) {
  return (
    <article className="space-y-3 rounded-xl border hairline bg-surface-elevated p-5">
      <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 className="font-display text-base text-ink">{spec.name}</h3>
        {spec.files[0] && (
          <code className="t-mono text-2xs text-muted-foreground">{spec.files[0]}</code>
        )}
      </header>
      {spec.blurb && <p className="text-sm text-muted-foreground">{spec.blurb}</p>}
      <div className="rounded-lg border hairline bg-surface p-4">{spec.render()}</div>
    </article>
  );
}

/**
 * LayerHeading — el encabezado de una capa funcional (Fundamentos, Primitivos…).
 * Separa la vitrina en sus capas: de un vistazo se ve en qué nivel está cada cosa.
 */
export function LayerHeading({ layer }: { layer: LayerMeta }) {
  return (
    <div id={`capa-${layer.id}`} className="scroll-mt-24 border-t-2 border-ink/15 pt-6">
      <span className="t-eyebrow text-muted-foreground">Capa</span>
      <h2 className="t-h1 mt-0.5 text-ink">{layer.label}</h2>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{layer.blurb}</p>
    </div>
  );
}

/** Una sección completa: ancla + título + hint + sus specimens apilados. */
export function SectionBlock({ section }: { section: CatalogSection }) {
  return (
    <section id={section.id} className="scroll-mt-24 space-y-4">
      <div>
        <h2 className="t-h2 text-ink">{section.title}</h2>
        {section.hint && <p className="mt-1 text-sm text-muted-foreground">{section.hint}</p>}
      </div>
      <div className="space-y-4">
        {section.specimens.map((spec) => (
          <SpecimenCard key={spec.name} spec={spec} />
        ))}
      </div>
    </section>
  );
}

/**
 * TocNav — índice de salto, sticky. Es el mapa de la librería: de un vistazo se
 * ve TODO lo que el DS cubre, agrupado por capa. En mobile scrollea horizontal.
 */
export function TocNav({ groups }: { groups: LayerGroup[] }) {
  return (
    <nav
      aria-label="Capas y secciones del Design System"
      className="sticky top-0 z-10 -mx-1 mb-2 flex gap-3 overflow-x-auto bg-background/80 px-1 py-2 backdrop-blur supports-[backdrop-filter]:bg-background/60"
    >
      {groups.map((g) => (
        <div key={g.layer.id} className="flex shrink-0 items-center gap-1.5">
          <a
            href={`#capa-${g.layer.id}`}
            className="shrink-0 rounded-full bg-ink/8 px-2.5 py-1 text-2xs font-semibold uppercase tracking-wide text-ink/70 transition-colors hover:bg-ink/15 hover:text-ink"
          >
            {g.layer.label}
          </a>
          {g.sections.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className="shrink-0 rounded-full border border-hairline px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-ink/30 hover:text-ink"
            >
              {s.title}
            </a>
          ))}
        </div>
      ))}
    </nav>
  );
}
