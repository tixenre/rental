import { type Equipment } from "@/data/equipment";
import { KeywordChips } from "./KeywordChips";

/**
 * IncludedList — keywords + specs highlights de la ficha del equipo.
 *
 * NOTA: los kit components (item.includes) NO se rendean acá; viven en
 * `KitSection` que se mounta arriba del todo en la página de detalle.
 */
export function IncludedList({ item }: { item: Equipment }) {
  const specs = item.specs ?? [];
  const hasSpecs = specs.length > 0;
  const keywords = item.keywords ?? [];
  const hasKeywords = keywords.length > 0;

  if (!hasSpecs && !hasKeywords) {
    return null;
  }

  const highlights = item.specsDestacados ?? [];
  const highlightLabels = new Set(highlights.map((s) => s.label));
  const rest = specs.filter((s) => !highlightLabels.has(s.label));
  const moreSpecs = rest.length;

  return (
    <div className="space-y-3">
      {hasKeywords && <KeywordChips keywords={keywords} />}
      {hasSpecs && (
        <div>
          {/* Mobile (#144): grilla 2-columnas label-arriba / valor-abajo, más
           * denso y alineado que los chips. */}
          <dl className="grid grid-cols-2 gap-x-3 gap-y-2 sm:hidden">
            {highlights.map((s, i) => (
              <div key={`m-${s.label}-${i}`} className="min-w-0 leading-tight">
                <dt className="font-mono text-2xs uppercase tracking-[0.18em] text-muted-foreground">
                  {s.label}
                </dt>
                <dd className="truncate text-sm font-medium text-ink">{s.value}</dd>
              </div>
            ))}
            {moreSpecs > 0 && (
              <div className="col-span-2">
                <span className="inline-flex items-center rounded-full border hairline border-dashed px-2 py-0.5 font-mono text-2xs uppercase tracking-widest text-muted-foreground">
                  +{moreSpecs} más
                </span>
              </div>
            )}
          </dl>

          {/* Desktop: chips redondeados (sin cambios respecto al original) */}
          <ul className="hidden flex-wrap gap-1.5 sm:flex">
            {highlights.map((s, i) => (
              <li
                key={`d-${s.label}-${i}`}
                className="inline-flex items-baseline gap-1.5 rounded-full border hairline bg-background/70 px-2.5 py-1"
              >
                <span className="font-mono text-2xs uppercase tracking-[0.18em] text-muted-foreground">
                  {s.label}
                </span>
                <span className="text-xs font-medium text-ink">{s.value}</span>
              </li>
            ))}
            {moreSpecs > 0 && (
              <li className="inline-flex items-center rounded-full border hairline border-dashed px-2.5 py-1 font-mono text-2xs uppercase tracking-widest text-muted-foreground">
                +{moreSpecs} más
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
