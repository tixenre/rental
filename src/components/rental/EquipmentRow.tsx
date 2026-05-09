import { Link } from "@tanstack/react-router";
import { Plus, Minus, Check } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { formatPrice, type Equipment } from "@/data/equipment";
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
        "group grid grid-cols-[80px_1fr_auto_auto] items-center gap-4 rounded-lg border bg-surface p-3 transition",
        selected ? "border-amber/60" : "hairline hover:border-foreground/20",
      )}
    >
      <Link
        to="/equipo/$slug"
        params={{ slug: item.slug }}
        className="relative block aspect-[4/3] w-20 overflow-hidden rounded"
      >
        <EmptyImage category={item.category} brand={item.brand} />
      </Link>

      <div className="min-w-0">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          {item.brand} · {item.category}
        </div>
        <Link
          to="/equipo/$slug"
          params={{ slug: item.slug }}
          className="block font-display text-base leading-tight hover:text-amber"
        >
          {item.name}
        </Link>
      </div>

      <div className="text-right">
        <div className="font-display text-base tabular text-amber">
          ${formatPrice(item.pricePerDay)}
        </div>
        <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
          / jornada
        </div>
      </div>

      {qty === 0 ? (
        <button
          onClick={() => add(item.id)}
          className="flex items-center gap-1.5 rounded-md border hairline px-3 py-1.5 text-xs uppercase tracking-wider hover:border-amber hover:bg-amber hover:text-primary-foreground"
        >
          <Plus className="h-3 w-3" /> Agregar
        </button>
      ) : (
        <div className="flex items-center gap-1 rounded-md border border-amber/40 bg-amber-soft p-0.5">
          <button onClick={() => remove(item.id)} className="grid h-7 w-7 place-items-center text-amber hover:bg-amber/20 rounded">
            <Minus className="h-3 w-3" />
          </button>
          <span className="w-6 text-center text-sm tabular flex items-center justify-center">
            {selected && <Check className="hidden" />}
            {qty}
          </span>
          <button onClick={() => add(item.id)} className="grid h-7 w-7 place-items-center text-amber hover:bg-amber/20 rounded">
            <Plus className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
}
