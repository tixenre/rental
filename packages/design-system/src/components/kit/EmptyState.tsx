import { type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * EmptyState — pattern "nada para mostrar".
 *
 * Source: `docs/design-kit/kit/components/empty-state.tsx`. Card con
 * icono amber-soft + título display + subtítulo + acción opcional.
 *
 * Variantes típicas:
 *   - Search empty → chips de sugerencias como `children`
 *   - Cart vacío   → CTA pill prominente como `children`
 *   - Sin pedidos  → ilustración + link como `children`
 */
export function EmptyState({
  icon,
  title,
  sub,
  children,
  className,
  dashed = true,
}: {
  icon: ReactNode;
  title: string;
  sub?: string;
  children?: ReactNode;
  className?: string;
  /** Borde discontinuo (true por default). Pasá false para usarlo dentro
   *  de una card que ya tiene su propio borde. */
  dashed?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2.5 rounded-lg py-12 px-6 text-center",
        dashed && "border border-dashed border-hairline",
        className,
      )}
    >
      <div className="mb-1 grid h-14 w-14 place-items-center rounded-full bg-amber/15 text-amber">
        {icon}
      </div>
      <div className="font-display text-xl font-black text-ink">{title}</div>
      {sub && (
        <p className="max-w-xs font-sans text-sm leading-relaxed text-muted-foreground">{sub}</p>
      )}
      {children && <div className="mt-2">{children}</div>}
    </div>
  );
}
