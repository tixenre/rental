import { Check } from "lucide-react";
import type { AddonItem } from "../types/equipment";
import { cn } from "./lib/cn";

export type { AddonItem };

/**
 * AddonPills — listado horizontal de items "incluye" sobre la row de un equipo.
 *
 * Comportamiento:
 *  - 0 addons  → pill italic muted "solo cuerpo".
 *  - ≤ max     → todas como pill amber-soft con ✓ a la izquierda.
 *  - > max     → muestra `max - 1` pills + pill dashed "+N".
 *  - qty > 1   → badge ink/amber "×N" a la derecha de la pill.
 *
 * Layout: flex-nowrap + overflow hidden para no romper la grilla.
 *
 * @example
 *   <AddonPills items={[
 *     { id: "1", name: "Cuerpo" },
 *     { id: "2", name: "Batería NP-FZ100", qty: 2 },
 *     { id: "3", name: "Cargador dual" },
 *   ]} max={3} />
 */
export function AddonPills({
  items,
  max = 3,
  emptyLabel = "solo cuerpo",
  className,
}: {
  items?: AddonItem[];
  max?: number;
  emptyLabel?: string;
  className?: string;
}) {
  const list = items ?? [];

  if (list.length === 0) {
    return (
      <div className={cn("flex items-center", className)}>
        <span className="inline-flex items-center rounded-full border border-hairline px-2 py-0.5 text-[10px] italic text-muted-foreground">
          {emptyLabel}
        </span>
      </div>
    );
  }

  const overflow = list.length > max;
  const visible = overflow ? list.slice(0, max - 1) : list.slice(0, max);
  const extra = list.length - visible.length;

  return (
    <div className={cn("flex flex-nowrap items-center gap-1 overflow-hidden", className)}>
      {visible.map((it, i) => (
        <AddonPill key={`${it.id ?? it.name}-${i}`} item={it} />
      ))}
      {overflow && extra > 0 && (
        <span className="inline-flex shrink-0 items-center rounded-full border border-dashed border-muted-foreground/40 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          +{extra}
        </span>
      )}
    </div>
  );
}

function AddonPill({ item }: { item: AddonItem }) {
  const qty = item.qty && item.qty > 1 ? item.qty : null;
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber/15 py-0.5 pl-1.5 pr-1 text-[10px] text-ink"
      title={item.name + (qty ? ` ×${qty}` : "")}
    >
      <Check className="h-2.5 w-2.5 shrink-0 text-amber" strokeWidth={3} />
      <span className="max-w-[140px] truncate">{item.name}</span>
      {qty && (
        <span className="ml-0.5 rounded-full bg-ink px-1 py-0 font-mono text-[9px] text-amber">
          ×{qty}
        </span>
      )}
    </span>
  );
}
