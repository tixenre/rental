import { motion } from "framer-motion";
import { Check, Plus, Minus, Sparkles } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { EmptyImage } from "./EmptyImage";
import { useEquipmentDetail } from "@/lib/equipment-detail-context";
import { cn } from "@/lib/utils";

export function EquipmentCard({
  item,
  index,
  width,
  disponible,
}: {
  item: Equipment;
  index: number;
  /** Ancho fijo en px para uso dentro de carrusel; si no, ocupa la celda. */
  width?: number;
  /** Unidades disponibles en las fechas seleccionadas (undefined = no hay fechas) */
  disponible?: number;
}) {
  const qty = useCart((s) => s.items[item.id] ?? 0);
  const add = useCart((s) => s.add);
  const remove = useCart((s) => s.remove);
  const selected = qty > 0;
  const { setOpenId } = useEquipmentDetail();
  const setOpen = (v: boolean) => setOpenId(v ? item.id : null);
  // Tope efectivo: disponibilidad real (con fechas) o stock total del equipo
  const cap = disponible ?? item.cantidad ?? Infinity;
  const noStock = cap <= 0;
  const reachedMax = qty >= cap;

  const sinStock = noStock;
  const stockBajo = !noStock && cap > 0 && cap <= 2;

  return (
    <motion.article
      id={`eq-${item.id}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.012, 0.25) }}
      style={width ? { width } : undefined}
      className={cn(
        "group relative flex shrink-0 flex-col overflow-hidden rounded-lg border bg-surface transition-all snap-start",
        selected
          ? "border-amber/60 shadow-[0_0_0_1px_var(--amber)]"
          : sinStock
          ? "hairline opacity-50"
          : "hairline hover:border-foreground/20",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`Ver detalle de ${item.name}`}
        className="relative block aspect-[4/3] overflow-hidden text-left"
      >
        {item.fotoUrl ? (
          <img
            src={item.fotoUrl}
            alt={item.name}
            className="h-full w-full object-cover transition group-hover:scale-[1.02]"
          />
        ) : (
          <EmptyImage category={item.category} brand={item.brand} />
        )}
        {item.isNew && (
          <div className="absolute left-2 top-2 flex items-center gap-1 rounded-full bg-ink px-2 py-0.5 font-mono text-[9px] uppercase tracking-widest text-amber">
            <Sparkles className="h-2.5 w-2.5" /> nuevo
          </div>
        )}
        {item.isCombo && !item.isNew && (
          <div className="absolute left-2 top-2 rounded-full bg-amber px-2 py-0.5 font-mono text-[9px] uppercase tracking-widest text-ink">
            combo
          </div>
        )}
        {selected && (
          <div className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-amber text-ink">
            <Check className="h-3.5 w-3.5" strokeWidth={3} />
          </div>
        )}
        {sinStock && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/70">
            <span className="rounded-full border hairline bg-background px-3 py-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Sin stock
            </span>
          </div>
        )}
      </button>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <button type="button" onClick={() => setOpen(true)} className="text-left">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            {item.brand}
          </div>
          <div className="mt-1 line-clamp-2 font-display text-base leading-tight tracking-tight text-ink hover:underline">
            {item.name}
          </div>
        </button>

        {/* Disponibilidad */}
        {disponible !== undefined && (
          <div className={cn(
            "font-mono text-[10px] uppercase tracking-widest",
            sinStock ? "text-destructive/70" : stockBajo ? "text-amber" : "text-muted-foreground"
          )}>
            {sinStock ? "Sin stock" : `${disponible} disponible${disponible !== 1 ? "s" : ""}`}
          </div>
        )}

        <div className="mt-auto flex items-end justify-between gap-2">
          <div>
            <div className="font-display text-lg tabular text-ink">
              {formatARS(item.pricePerDay)}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              / 1 jornada
            </div>
            {disponible !== undefined && (
              <div
                className={cn(
                  "mt-1 font-mono text-[9px] uppercase tracking-widest tabular",
                  disponible <= 0
                    ? "text-destructive"
                    : disponible === 1
                      ? "text-amber-600"
                      : "text-muted-foreground",
                )}
              >
                {disponible <= 0
                  ? "Sin stock"
                  : `${disponible} disp${disponible === 1 ? "." : "."}`}
              </div>
            )}
          </div>

          {qty === 0 ? (
            <button
              onClick={() => !sinStock && add(item.id)}
              disabled={sinStock}
              className="flex items-center gap-1.5 rounded-md border hairline px-3 py-1.5 text-xs font-medium uppercase tracking-wider transition hover:border-amber hover:bg-amber hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Plus className="h-3 w-3" />
              {noStock ? "Sin stock" : "Agregar"}
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
                onClick={() => {
                  if (disponible === undefined || qty < disponible) {
                    add(item.id);
                  }
                }}
                disabled={disponible !== undefined && qty >= disponible}
                className="grid h-7 w-7 place-items-center rounded text-amber hover:bg-amber/20 disabled:opacity-40 disabled:cursor-not-allowed"
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
