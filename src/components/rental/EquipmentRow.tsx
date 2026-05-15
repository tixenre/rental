import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { Plus, Minus, Sparkles, ChevronDown, ArrowRight } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { priceBreakdown } from "@/lib/pricing";
import { buildEquipoSlug } from "@/lib/equipo-slug";
import { EmptyImage } from "./EmptyImage";
import { IncludedList } from "./IncludedList";
import { KitSection } from "./KitSection";
import { cn } from "@/lib/utils";

/**
 * Row del catálogo (mobile default + desktop opcional).
 *
 * Comportamiento:
 * - Click en thumb/info → **expande inline** una mini-ficha (kit + specs
 *   clave). Permite hojear el catálogo rápido sin perder scroll position.
 * - Dentro del expanded, botón "Ver ficha completa →" navega a la página
 *   dedicada (/equipo/<slug>) para SEO y compartir links.
 *
 * Por qué no abrir directo la página: en mobile el flujo "click → page →
 * back → re-scroll" es lento y pierde fluidez. El expand inline mantiene
 * al usuario hojeando.
 */
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
  const openDetail = () =>
    navigate({ to: "/equipo/$slug", params: { slug: buildEquipoSlug(item) } });

  const [expanded, setExpanded] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);
  const cap = disponible ?? item.cantidad ?? Infinity;
  const noStock = cap <= 0;
  const sinStock = noStock;
  const stockBajo = !noStock && cap > 0 && cap <= 2;
  const price = priceBreakdown(item.pricePerDay, jornadas, 1);
  const showPeriodTotal = hasDateRange && jornadas > 1;

  // Specs clave para mostrar en la mini-ficha. Usa las specs_destacados del
  // template si las hay; de lo contrario cae al conjunto fijo legacy.
  const quickFacts = (
    item.specsDestacados && item.specsDestacados.length > 0
      ? item.specsDestacados
      : [
          item.montura && { label: "Montura", value: item.montura },
          item.formato && { label: "Formato", value: item.formato },
          item.resolucion && { label: "Resolución", value: item.resolucion },
          item.peso && { label: "Peso", value: item.peso },
          item.alimentacion && { label: "Alimentación", value: item.alimentacion },
        ].filter((x): x is { label: string; value: string } => !!x)
  ).slice(0, 3);

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
        {/* Click area: thumb + info → expande inline (NO navega) */}
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          aria-label={`${expanded ? "Cerrar" : "Ver"} info de ${item.name}`}
          className="flex min-w-0 flex-1 items-center gap-3 text-left sm:gap-4"
        >
          {/* Thumb */}
          <div className="relative aspect-square w-14 shrink-0 overflow-hidden rounded-md sm:aspect-[4/3] sm:w-16 bg-white">
            {item.fotoUrl && !imgFailed ? (
              <img
                src={item.fotoUrl}
                alt={item.name}
                className="h-full w-full object-contain p-1.5"
                loading="lazy"
                onError={() => setImgFailed(true)}
              />
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
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full border hairline hover:border-amber hover:bg-amber hover:text-ink active:border-amber active:bg-amber active:text-ink disabled:cursor-not-allowed disabled:opacity-40 sm:h-auto sm:w-auto sm:rounded-md sm:px-3 sm:py-1.5"
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
              className="grid h-9 w-9 place-items-center rounded-full text-amber hover:bg-amber/20 active:bg-amber/30 sm:h-7 sm:w-7 sm:rounded"
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
              className="grid h-9 w-9 place-items-center rounded-full text-amber hover:bg-amber/20 active:bg-amber/30 disabled:opacity-40 disabled:cursor-not-allowed sm:h-7 sm:w-7 sm:rounded"
            >
              <Plus className="h-3 w-3" />
            </button>
          </div>
        )}
      </div>

      {/* Mini-ficha expandida inline */}
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
            <div className="border-t hairline px-3 py-3 sm:px-4 sm:py-4 space-y-3">
              {/* Quick facts fundamentales (montura, formato, resolución...).
               * TODO #116: hacer configurables desde admin por categoría —
               * hoy son los primeros 3 con valor entre un set fijo.
               * Ocultos en mobile (#144) — se solapan visualmente con los
               * specs highlights de IncludedList y la info está en la ficha
               * completa via QuickFactsRow. */}
              {quickFacts.length > 0 && (
                <div className="hidden flex-wrap gap-1.5 sm:flex">
                  {quickFacts.map((f) => {
                    // value vacío = badge solo-label (bool destacadas que son Sí).
                    const hasValue = !!f.value?.trim();
                    return (
                      <span
                        key={f.label}
                        className="inline-flex items-center gap-1.5 rounded-full border hairline bg-background px-2 py-0.5 text-[11px]"
                      >
                        <span className="font-mono uppercase tracking-wider text-muted-foreground">
                          {f.label}
                        </span>
                        {hasValue && (
                          <span className="font-medium text-ink">{f.value}</span>
                        )}
                      </span>
                    );
                  })}
                </div>
              )}

              {/* Componentes del kit (si tiene). Es lo más útil para decidir
               * rápido si el equipo viene con lo necesario. */}
              <KitSection item={item} />
              <IncludedList item={item} />

              {/* CTA: ver ficha completa */}
              <button
                type="button"
                onClick={openDetail}
                className="inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-widest text-ink hover:text-amber transition mt-1"
              >
                Ver ficha completa
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
