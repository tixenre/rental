import { Skeleton } from "@/design-system/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * Presets de skeleton para el back-office — espejan el layout real mientras carga,
 * evitando el "Cargando…" pelado y el CLS de la tabla que aparece de golpe.
 * Construidos sobre el primitivo `Skeleton`. Una sola forma del loading por shape.
 */

/** Filas de tabla/lista. `cols` controla el ancho de las celdas simuladas. */
export function TableSkeleton({
  rows = 6,
  cols = 4,
  className,
}: {
  rows?: number;
  cols?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)} aria-hidden>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-3 py-1">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton
              key={c}
              className={cn(
                "h-5",
                c === 0 ? "w-1/3" : "flex-1",
                c === cols - 1 && "w-16 flex-none",
              )}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Lista de filas con avatar + dos líneas (clientes, pedidos, movimientos). */
export function ListSkeleton({ rows = 6, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-3", className)} aria-hidden>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 shrink-0 rounded-full" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/4" />
          </div>
          <Skeleton className="h-5 w-16 shrink-0" />
        </div>
      ))}
    </div>
  );
}

/** Grilla de cards (dashboard, KPIs, catálogo admin). */
export function CardGridSkeleton({ count = 6, className }: { count?: number; className?: string }) {
  return (
    <div className={cn("grid grid-cols-2 gap-3 md:grid-cols-3", className)} aria-hidden>
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-24 w-full rounded-lg" />
      ))}
    </div>
  );
}
