import { Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { Check, Plus, Minus } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { formatPrice, type Equipment } from "@/data/equipment";
import { EmptyImage } from "./EmptyImage";
import { cn } from "@/lib/utils";

export function EquipmentCard({
  item,
  index,
}: {
  item: Equipment;
  index: number;
}) {
  const qty = useCart((s) => s.items[item.id] ?? 0);
  const add = useCart((s) => s.add);
  const remove = useCart((s) => s.remove);
  const selected = qty > 0;

  return (
    <motion.article
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: Math.min(index * 0.015, 0.3) }}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-lg border bg-surface transition-all",
        selected
          ? "border-amber/60 shadow-[0_0_0_1px_var(--amber)]"
          : "hairline hover:border-foreground/20",
      )}
    >
      <Link
        to="/equipo/$slug"
        params={{ slug: item.slug }}
        className="relative block aspect-[4/3] overflow-hidden"
      >
        <EmptyImage category={item.category} brand={item.brand} />
        {selected && (
          <div className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-amber text-primary-foreground">
            <Check className="h-3.5 w-3.5" strokeWidth={3} />
          </div>
        )}
      </Link>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            {item.brand}
          </div>
          <Link
            to="/equipo/$slug"
            params={{ slug: item.slug }}
            className="mt-1 block font-display text-lg leading-tight tracking-tight hover:text-amber transition"
          >
            {item.name}
          </Link>
        </div>

        <div className="mt-auto flex items-end justify-between gap-2">
          <div>
            <div className="font-display text-xl tabular text-amber">
              ${formatPrice(item.pricePerDay)}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              por jornada
            </div>
          </div>

          {qty === 0 ? (
            <button
              onClick={() => add(item.id)}
              className="flex items-center gap-1.5 rounded-md border hairline px-3 py-1.5 text-xs font-medium uppercase tracking-wider transition hover:border-amber hover:bg-amber hover:text-primary-foreground"
            >
              <Plus className="h-3 w-3" />
              Agregar
            </button>
          ) : (
            <div className="flex items-center gap-1 rounded-md border border-amber/40 bg-amber-soft p-0.5">
              <button
                onClick={() => remove(item.id)}
                className="grid h-7 w-7 place-items-center rounded text-amber hover:bg-amber/20"
              >
                <Minus className="h-3 w-3" />
              </button>
              <span className="w-6 text-center text-sm tabular">{qty}</span>
              <button
                onClick={() => add(item.id)}
                className="grid h-7 w-7 place-items-center rounded text-amber hover:bg-amber/20"
              >
                <Plus className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>
      </div>
    </motion.article>
  );
}
