/**
 * catalog-kit — primitivos de layout DEL CATÁLOGO (no del producto).
 *
 * Son la "tipografía" interna de la vitrina: cómo se dibuja una sección, un
 * specimen, una fila de ejemplos. Viven solo acá; no confundir con el DS real
 * (`design-system/*`), que es lo que la vitrina muestra.
 */
import { type ReactNode } from "react";

import { cn } from "@/lib/utils";
import type { CatalogSection, Specimen } from "./types";

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
 * SectionNav — índice de salto entre las secciones DE UNA capa, sticky. Solo se
 * usa en capas con varias secciones (hoy Primitivos): saltar sin scrollear toda
 * la pestaña. En mobile scrollea horizontal.
 */
export function SectionNav({ sections }: { sections: CatalogSection[] }) {
  return (
    <nav
      aria-label="Secciones de la capa"
      className="sticky top-0 z-10 -mx-1 flex gap-2 overflow-x-auto bg-background/80 px-1 py-2 backdrop-blur supports-[backdrop-filter]:bg-background/60"
    >
      {sections.map((s) => (
        <a
          key={s.id}
          href={`#${s.id}`}
          className="shrink-0 rounded-full border border-hairline px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-ink/30 hover:text-ink"
        >
          {s.title}
        </a>
      ))}
    </nav>
  );
}
