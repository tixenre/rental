import { Check } from "lucide-react";
import type { IncludedItem } from "@/data/equipment";
import { cn } from "@/lib/utils";

/**
 * Pills inline con los addons del kit. Pensado para insertar en la row del
 * catálogo desktop entre la info del equipo y el precio.
 *
 * Comportamiento:
 * - 0 addons → 1 sola pill italic muted "solo cuerpo".
 * - ≤ `max` addons → todas como pill amber-soft con check.
 * - > `max` → muestra `max - 1` pills + 1 pill `dashed` con `+N`.
 * - Si un item tiene `qty > 1` → badge ink/amber ×N al final.
 *
 * Layout: `flex-wrap: nowrap + overflow hidden`, evita romper la row.
 */
export function AddonPills({
  items,
  max = 3,
  className,
}: {
  items?: IncludedItem[];
  max?: number;
  className?: string;
}) {
  const list = items ?? [];

  if (list.length === 0) {
    return (
      <div className={cn("flex items-center", className)}>
        <span className="inline-flex items-center rounded-full border hairline px-2 py-0.5 text-[10px] italic text-muted-foreground">
          solo cuerpo
        </span>
      </div>
    );
  }

  const overflow = list.length > max;
  const visible = overflow ? list.slice(0, max - 1) : list.slice(0, max);
  const extraCount = list.length - visible.length;

  return (
    <div
      className={cn(
        "flex flex-nowrap items-center gap-1 overflow-hidden",
        className,
      )}
    >
      {visible.map((it, i) => (
        <AddonPill key={`${it.id ?? it.name}-${i}`} item={it} />
      ))}
      {overflow && extraCount > 0 && (
        <span className="inline-flex shrink-0 items-center rounded-full border border-dashed border-muted-foreground/40 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
          +{extraCount}
        </span>
      )}
    </div>
  );
}

function AddonPill({ item }: { item: IncludedItem }) {
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
