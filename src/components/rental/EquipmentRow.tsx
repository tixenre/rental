import { Plus, Minus, Sparkles } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { EmptyImage } from "./EmptyImage";
import { cn } from "@/lib/utils";

export function EquipmentRow({ item }: { item: Equipment }) {
  const qty = useCart((s) => s.items[item.id] ?? 0);
  const add = useCart((s) => s.add);
  const remove = useCart((s) => s.remove);
  const selected = qty > 0;

  return (
    <div
      className={cn(
        "group grid grid-cols-[56px_1fr_auto_auto] items-center gap-4 rounded-md border bg-surface px-3 py-2 transition",
        selected ? "border-amber/60" : "hairline hover:border-foreground/20",
      )}
    >
      <div className="relative aspect-[4/3] w-14 overflow-hidden rounded">
        <EmptyImage category={item.category} brand={item.brand} />
      </div>

      <div className="min-w-0">
        <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          <span>{item.brand}</span>
          <span>·</span>
          <span>{item.category}</span>
          {item.isNew && (
            <span className="flex items-center gap-1 rounded-full bg-ink px-1.5 py-0.5 text-amber">
              <Sparkles className="h-2.5 w-2.5" /> nuevo
            </span>
          )}
          {item.isCombo && (
            <span className="rounded-full bg-amber px-1.5 py-0.5 text-ink">combo</span>
          )}
        </div>
        <div className="block truncate font-display text-base leading-tight text-ink">
          {item.name}
        </div>
      </div>

      <div className="text-right">
        <div className="font-display text-base tabular text-ink">
          {formatARS(item.pricePerDay)}
        </div>
        <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
          / 1 jornada
        </div>
      </div>

      {qty === 0 ? (
        <button
          onClick={() => add(item.id)}
          className="flex items-center gap-1.5 rounded-md border hairline px-3 py-1.5 text-xs uppercase tracking-wider hover:border-amber hover:bg-amber hover:text-ink"
        >
          <Plus className="h-3 w-3" /> Agregar
        </button>
      ) : (
        <div className="flex items-center gap-1 rounded-md border border-amber/40 bg-amber-soft p-0.5">
          <button onClick={() => remove(item.id)} className="grid h-7 w-7 place-items-center text-amber hover:bg-amber/20 rounded">
            <Minus className="h-3 w-3" />
          </button>
          <span className="w-6 text-center text-sm tabular">{qty}</span>
          <button onClick={() => add(item.id)} className="grid h-7 w-7 place-items-center text-amber hover:bg-amber/20 rounded">
            <Plus className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
}
