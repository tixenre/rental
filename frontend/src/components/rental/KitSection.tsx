import { Package } from "lucide-react";
import { equipment, type Equipment } from "@/data/equipment";
import { EmptyImage } from "./EmptyImage";

/**
 * BoxItemsSection — base visual compartida para listas de ítems con
 * cantidad + foto. Reusada por KitSection (componentes del kit) y por
 * ContenidoIncluidoSection (contenido de la caja, B1 #635).
 */
export type BoxItem = {
  name: string;
  qty: number;
  fotoUrl?: string | null;
  /** Si está, se usa como fallback EmptyImage con contexto de equipo. */
  equipoCategory?: string;
  equipoBrand?: string;
};

export function BoxItemsSection({ title, items }: { title: string; items: BoxItem[] }) {
  if (items.length === 0) return null;
  return (
    <section className="space-y-2">
      <div className="flex items-center gap-1.5 font-mono text-2xs uppercase tracking-[0.2em] text-ink">
        <Package className="h-3 w-3" /> {title}
        <span className="ml-1 text-muted-foreground">({items.length})</span>
      </div>
      <ul className="grid gap-1.5 sm:grid-cols-2">
        {items.map((it, i) => {
          const qty = it.qty;
          return (
            <li
              key={i}
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
                {it.fotoUrl ? (
                  <img
                    src={it.fotoUrl}
                    alt={it.name}
                    className="h-full w-full object-cover"
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.opacity = "0";
                    }}
                  />
                ) : it.equipoCategory ? (
                  <EmptyImage category={it.equipoCategory} brand={it.equipoBrand ?? ""} />
                ) : (
                  <div className="grid h-full w-full place-items-center">
                    <Package className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm leading-snug text-ink">{it.name}</div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/**
 * KitSection — kit components (cards con foto + cantidad).
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

  const items: BoxItem[] = includes.map((inc) => {
    const ref: Equipment | undefined = inc.id
      ? equipment.find((eq) => eq.id === inc.id)
      : undefined;
    return {
      name: inc.name,
      qty: inc.qty ?? 1,
      fotoUrl: inc.fotoUrl,
      equipoCategory: ref?.category,
      equipoBrand: ref?.brand,
    };
  });

  return <BoxItemsSection title="Incluye" items={items} />;
}
