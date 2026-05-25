import { Package } from "lucide-react";
import { equipment, type Equipment } from "@/data/equipment";
import { EmptyImage } from "./EmptyImage";

/**
 * KitSection — solo los kit components (cards con foto + cantidad).
 *
 * Diseñado para aparecer arriba del todo en la página de detalle del
 * equipo: el cliente ve de una qué viene en el alquiler antes de leer
 * descripción o specs. Solo se renderea cuando `item.includes` tiene al
 * menos un item — el caller decide si llamarlo.
 *
 * Distinto de IncludedList: ese mezcla keywords + specs highlights +
 * includes para el bloque "extra info" más abajo en la página. Acá solo
 * mostramos las cards con fotos y badges de cantidad.
 */
export function KitSection({ item }: { item: Equipment }) {
  const includes = item.includes ?? [];
  if (includes.length === 0) return null;

  return (
    <section className="space-y-2">
      <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.25em] text-ink">
        <Package className="h-3 w-3" /> Incluye
        <span className="ml-1 text-muted-foreground">({includes.length})</span>
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
              {/* Badge de cantidad: siempre visible en mobile (incluso ×1)
               *  para que el cliente vea claramente cuántos vienen.
               *  En desktop solo cuando >1 (menos ruido en grid 2-col). */}
              <span
                className={`shrink-0 grid h-9 min-w-9 place-items-center rounded-md px-1.5 font-mono text-xs tabular ${
                  qty > 1 ? "bg-ink text-amber font-bold" : "bg-muted text-ink/70 sm:hidden"
                }`}
                aria-label={`Cantidad: ${qty}`}
              >
                ×{qty}
              </span>
              <div className="relative aspect-square w-12 sm:w-10 shrink-0 overflow-hidden rounded bg-muted/40">
                {inc.fotoUrl ? (
                  <img
                    src={inc.fotoUrl}
                    alt={inc.name}
                    className="h-full w-full object-cover"
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.opacity = "0";
                    }}
                  />
                ) : ref ? (
                  <EmptyImage category={ref.category} brand={ref.brand} />
                ) : (
                  <div className="grid h-full w-full place-items-center">
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
                <div className="text-sm leading-snug text-ink">{inc.name}</div>
                {inc.note && <div className="text-[11px] text-muted-foreground">{inc.note}</div>}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
