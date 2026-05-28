import { type ReactNode } from "react";
import { cn } from "./lib/cn";

/**
 * EmptyState — pattern de "nada para mostrar".
 *
 * Estructura:
 *   ┌─────────────────────────┐
 *   │       ⊙  ← icon         │  círculo amber-soft 56px
 *   │   Sin resultados        │  display font, chunky
 *   │   Probá otra categoría  │  sans muted, max 320px
 *   │   [chip] [chip] [chip]  │  children (acción opcional)
 *   └─────────────────────────┘
 *
 * Variantes típicas:
 *   - Search empty → chips de sugerencias como `children`
 *   - Cart vacío   → CTA pill prominente como `children`
 *   - Sin pedidos  → ilustración + link como `children`
 *
 * @example
 *   <EmptyState
 *     icon={<Search className="h-6 w-6" />}
 *     title="Sin resultados"
 *     sub="Probá con otra categoría, marca o término."
 *   >
 *     <div className="flex gap-1.5 flex-wrap justify-center mt-2">
 *       {categorias.map((c) => <Chip key={c}>{c}</Chip>)}
 *     </div>
 *   </EmptyState>
 *
 * @example
 *   <EmptyState
 *     icon={<ShoppingBag className="h-6 w-6" />}
 *     title="Tu pedido está vacío"
 *     sub="Sumá equipos desde el catálogo."
 *   >
 *     <Button shape="pill">Explorar catálogo →</Button>
 *   </EmptyState>
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
  /** Borde discontinuo. true por default. Pasá false para usarlo dentro
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
        <p className="max-w-xs font-sans text-sm leading-relaxed text-muted-foreground">
          {sub}
        </p>
      )}
      {children && <div className="mt-2">{children}</div>}
    </div>
  );
}
