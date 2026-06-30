import { Package } from "lucide-react";
import type { EstudioPackEquipo } from "@/lib/api";

/**
 * StudioPackKit — muestra el pack del estudio como kit (cards con foto + cantidad),
 * reusando el patrón visual de rental/KitSection. Se alimenta de la disponibilidad
 * de la franja: lo que llega ya está filtrado (best-effort) a lo disponible.
 */
export function StudioPackKit({
  equipos,
  title = "Incluye en esta franja",
  emptyText = "No hay equipos del pack disponibles en esta franja.",
}: {
  equipos: EstudioPackEquipo[];
  title?: string;
  emptyText?: string;
}) {
  if (equipos.length === 0) {
    return <p className="mt-2 text-xs text-muted-foreground">{emptyText}</p>;
  }

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center gap-1.5 font-mono text-2xs uppercase tracking-[0.2em] text-ink">
        <Package className="h-3 w-3" /> {title}
        <span className="ml-1 text-muted-foreground">({equipos.length})</span>
      </div>
      <ul className="grid gap-1.5 sm:grid-cols-2">
        {equipos.map((e) => (
          <li
            key={e.id}
            className="flex items-center gap-2.5 rounded-md border hairline bg-background/60 p-2"
          >
            <span
              className={`shrink-0 grid h-9 min-w-9 place-items-center rounded-md px-1.5 font-mono text-xs tabular ${
                e.cantidad > 1
                  ? "bg-ink text-[var(--area-accent)] font-bold"
                  : "bg-muted text-ink/70 sm:hidden"
              }`}
              aria-label={`Cantidad: ${e.cantidad}`}
            >
              ×{e.cantidad}
            </span>
            <div className="relative aspect-square w-12 sm:w-10 shrink-0 overflow-hidden rounded bg-muted/40">
              {e.foto_url ? (
                <img
                  src={e.foto_url}
                  alt={e.nombre}
                  className="h-full w-full object-cover"
                  loading="lazy"
                  onError={(ev) => {
                    (ev.target as HTMLImageElement).style.opacity = "0";
                  }}
                />
              ) : (
                <div className="grid h-full w-full place-items-center">
                  <Package className="h-4 w-4 text-muted-foreground" />
                </div>
              )}
            </div>
            <div className="min-w-0 flex-1">
              {e.marca && (
                <div className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
                  {e.marca}
                </div>
              )}
              <div className="text-sm leading-snug text-ink">{e.nombre}</div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
