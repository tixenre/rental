import { Package } from "lucide-react";
import { equipment, type Equipment } from "@/data/equipment";
import { EmptyImage } from "./EmptyImage";

export function IncludedList({ item }: { item: Equipment }) {
  const includes = item.includes ?? [];
  const hasIncludes = includes.length > 0;
  const hasSpecs = item.specs.length > 0;

  if (!hasIncludes && !hasSpecs && !item.description) {
    return (
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        Sin información adicional
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {item.description && (
        <p className="text-sm leading-relaxed text-muted-foreground">{item.description}</p>
      )}

      {hasIncludes && (
        <div>
          <div className="mb-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.25em] text-ink">
            <Package className="h-3 w-3" /> Incluye
          </div>
          <ul className="grid gap-1.5 sm:grid-cols-2">
            {includes.map((inc, i) => {
              const ref: Equipment | undefined = inc.id
                ? equipment.find((eq) => eq.id === inc.id)
                : undefined;
              const qty = inc.qty ?? 1;
              return (
                <li
                  key={`${inc.id ?? inc.name}-${i}`}
                  className="flex items-center gap-2.5 rounded-md border hairline bg-background/60 p-2"
                >
                  <div className="relative aspect-square w-10 shrink-0 overflow-hidden rounded">
                    {ref ? (
                      <EmptyImage category={ref.category} brand={ref.brand} />
                    ) : (
                      <div className="grid h-full w-full place-items-center bg-muted">
                        <Package className="h-4 w-4 text-muted-foreground" />
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    {ref && (
                      <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                        {ref.brand} · {ref.category}
                      </div>
                    )}
                    <div className="truncate text-sm text-ink">{inc.name}</div>
                    {inc.note && (
                      <div className="text-[11px] text-muted-foreground">{inc.note}</div>
                    )}
                  </div>
                  {qty > 1 && (
                    <span className="shrink-0 rounded-full bg-ink px-2 py-0.5 font-mono text-[10px] tabular text-amber">
                      ×{qty}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {hasSpecs && (
        <div>
          <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.25em] text-ink">
            Specs
          </div>
          <dl className="grid gap-1 text-xs sm:grid-cols-2">
            {item.specs.map((s) => (
              <div
                key={s.label}
                className="flex justify-between gap-3 rounded border-b hairline py-1"
              >
                <dt className="text-muted-foreground">{s.label}</dt>
                <dd className="text-right text-ink">{s.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}
