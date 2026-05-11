import { useNavigate } from "@tanstack/react-router";
import { Plus, Minus, Sparkles, ChevronRight } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { priceBreakdown } from "@/lib/pricing";
import { EmptyImage } from "./EmptyImage";
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
  const jornadas = useCart((s) => s.days());
  const hasDateRange = useCart((s) => !!s.startDate && !!s.endDate);
  const selected = qty > 0;
  const navigate = useNavigate();
  const openDetail = () => navigate({ to: "/equipo/$id", params: { id: item.id } });
  const cap = disponible ?? item.cantidad ?? Infinity;
  const noStock = cap <= 0;

  const sinStock = noStock;
  const stockBajo = !noStock && cap > 0 && cap <= 2;

  // TODO #73: cuando se implementen descuentos por jornada / cliente,
  // este breakdown ya devolverá total con descuentos aplicados.
  const price = priceBreakdown(item.pricePerDay, jornadas, 1);
  const showPeriodTotal = hasDateRange && jornadas > 1;

  return (
    <div
      id={`eq-${item.id}`}
      className={cn(
        "rounded-lg border bg-surface transition-all",
        selected
          ? "border-amber/60 bg-amber-soft/30"
          : sinStock
          ? "hairline opacity-50"
          : "hairline hover:border-foreground/20",
      )}
    >
      <div className="group flex items-center gap-3 p-2.5 sm:gap-4 sm:px-3">
        {/* Click area: thumb + info → navega a la ficha del equipo */}
        <button
          type="button"
          onClick={openDetail}
          aria-label={`Ver ficha de ${item.name}`}
          className="flex min-w-0 flex-1 items-center gap-3 text-left sm:gap-4"
        >
          {/* Thumb */}
          <div className="relative aspect-square w-14 shrink-0 overflow-hidden rounded-md sm:aspect-[4/3] sm:w-16 bg-white">
            {item.fotoUrl ? (
              <img src={item.fotoUrl} alt={item.name} className="h-full w-full object-contain p-1.5" />
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
              <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition group-hover:text-ink" />
            </div>
            {/* Precio inline en mobile */}
            <div className="mt-0.5 flex items-baseline gap-1 sm:hidden">
              <span className="font-display text-sm tabular text-ink">
                {formatARS(item.pricePerDay)}
              </span>
              <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                /jornada
              </span>
              {showPeriodTotal && (
                <span className="ml-1 font-display text-xs tabular text-amber">
                  · {formatARS(price.total)} total
                </span>
              )}
            </div>
          </div>
        </button>

        {/* Precio en desktop */}
        <div className="hidden text-right sm:block">
          <div className="font-display text-base tabular text-ink">
            {formatARS(item.pricePerDay)}
          </div>
          <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
            / jornada
          </div>
          {showPeriodTotal && (
            <div className="mt-1 font-display text-sm tabular text-amber">
              {formatARS(price.total)}
              <span className="ml-1 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                · {price.jornadas} j
              </span>
            </div>
          )}
          {disponible !== undefined && (
            <div
              className={cn(
                "mt-0.5 font-mono text-[9px] uppercase tracking-widest tabular",
                disponible <= 0
                  ? "text-destructive"
                  : disponible === 1
                    ? "text-amber-600"
                    : "text-muted-foreground",
              )}
            >
              {disponible <= 0 ? "sin stock" : `${disponible} disp.`}
            </div>
          )}
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
              <Plus className="h-3 w-3" /> {noStock ? "Sin stock" : "Agregar"}
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
    </div>
  );
}
