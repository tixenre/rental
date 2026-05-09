import { AnimatePresence, motion } from "framer-motion";
import { Plus, Minus, Sparkles, ChevronDown } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { EmptyImage } from "./EmptyImage";
import { IncludedList } from "./IncludedList";
import { useEquipmentDetail } from "@/lib/equipment-detail-context";
import { cn } from "@/lib/utils";

export function EquipmentRow({
  item,
  disponible,
}: {
  item: Equipment;
  disponible?: number;
}) {
  const qty = useCart((s) => s.items[item.id] ?? 0);
  const add = useCart((s) => s.add);
  const remove = useCart((s) => s.remove);
  const selected = qty > 0;
  const { openId, setOpenId } = useEquipmentDetail();
  const expanded = openId === item.id;

  const sinStock = disponible !== undefined && disponible <= 0;
  const stockBajo = disponible !== undefined && disponible > 0 && disponible <= 2;

  return (
    <div
      id={`eq-${item.id}`}
      className={cn(
        "rounded-lg border bg-surface transition-all",
        expanded
          ? "border-ink/40 bg-accent/30 shadow-sm ring-1 ring-ink/10"
          : selected
            ? "border-amber/60 bg-amber-soft/30"
            : sinStock
            ? "hairline opacity-50"
            : "hairline hover:border-foreground/20",
      )}
    >
      <div className="group flex items-center gap-3 p-2.5 sm:gap-4 sm:px-3">
        {/* Toggle area: thumb + info */}
        <button
          type="button"
          onClick={() => setOpenId(expanded ? null : item.id)}
          aria-expanded={expanded}
          className="flex min-w-0 flex-1 items-center gap-3 text-left sm:gap-4"
        >
          {/* Thumb */}
          <div className="relative aspect-square w-14 shrink-0 overflow-hidden rounded-md sm:aspect-[4/3] sm:w-16">
            {item.fotoUrl ? (
              <img src={item.fotoUrl} alt={item.name} className="h-full w-full object-cover" />
            ) : (
              <EmptyImage category={item.category} brand={item.brand} />
            )}
          </div>

          {/* Info */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground sm:text-[10px]">
              <span className="truncate">{item.brand}</span>
              <span className="hidden sm:inline">·</span>
              <span className="hidden truncate sm:inline">{item.category}</span>
              {item.isNew && (
                <span className="flex shrink-0 items-center gap-0.5 rounded-full bg-ink px-1.5 py-0.5 text-amber">
                  <Sparkles className="h-2.5 w-2.5" /> nuevo
                </span>
              )}
              {item.isCombo && (
                <span className="shrink-0 rounded-full bg-amber px-1.5 py-0.5 text-ink">combo</span>
              )}
              {disponible !== undefined && (
                <span className={cn(
                  "shrink-0 hidden sm:inline",
                  sinStock ? "text-destructive/70" : stockBajo ? "text-amber" : "",
                )}>
                  · {sinStock ? "sin stock" : `${disponible} disp.`}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              <div className="truncate font-display text-[15px] leading-tight text-ink sm:text-base">
                {item.name}
              </div>
              <ChevronDown
                className={cn(
                  "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
                  expanded && "rotate-180",
                )}
              />
            </div>
            {/* Precio inline en mobile */}
            <div className="mt-0.5 flex items-baseline gap-1 sm:hidden">
              <span className="font-display text-sm tabular text-ink">
                {formatARS(item.pricePerDay)}
              </span>
              <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                /día
              </span>
            </div>
          </div>
        </button>

        {/* Precio en desktop */}
        <div className="hidden text-right sm:block">
          <div className="font-display text-base tabular text-ink">
            {formatARS(item.pricePerDay)}
          </div>
          <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
            / 1 jornada
          </div>
        </div>

        {/* CTA */}
        {qty === 0 ? (
          <button
            onClick={() => !sinStock && add(item.id)}
            disabled={sinStock}
            aria-label={`Agregar ${item.name}`}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full border hairline hover:border-amber hover:bg-amber hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 sm:h-auto sm:w-auto sm:rounded-md sm:px-3 sm:py-1.5"
          >
            <Plus className="h-4 w-4 sm:hidden" />
            <span className="hidden items-center gap-1.5 text-xs uppercase tracking-wider sm:flex">
              <Plus className="h-3 w-3" /> Agregar
            </span>
          </button>
        ) : (
          <div className="flex shrink-0 items-center gap-0.5 rounded-full border border-amber/50 bg-amber-soft p-0.5 sm:rounded-md sm:gap-1">
            <button
              onClick={() => remove(item.id)}
              aria-label="Quitar uno"
              className="grid h-7 w-7 place-items-center rounded-full text-amber hover:bg-amber/20 sm:rounded"
            >
              <Minus className="h-3 w-3" />
            </button>
            <span className="w-5 text-center text-sm font-semibold tabular text-ink sm:w-6">
              {qty}
            </span>
            <button
              onClick={() => {
                if (disponible === undefined || qty < disponible) {
                  add(item.id);
                }
              }}
              disabled={disponible !== undefined && qty >= disponible}
              aria-label="Agregar uno"
              className="grid h-7 w-7 place-items-center rounded-full text-amber hover:bg-amber/20 disabled:opacity-40 disabled:cursor-not-allowed sm:rounded"
            >
              <Plus className="h-3 w-3" />
            </button>
          </div>
        )}
      </div>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="border-t hairline px-3 py-3 sm:px-4 sm:py-4">
              <IncludedList item={item} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
