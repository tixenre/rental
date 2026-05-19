import { useState, type MouseEvent } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "@tanstack/react-router";
import { Check, Plus, Minus, Sparkles } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { useFlyToCart } from "@/lib/fly-to-cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { useClienteSession, aplicaIva } from "@/lib/iva";
import { priceBreakdown } from "@/lib/pricing";
import { buildEquipoSlug } from "@/lib/equipo-slug";
import { EmptyImage } from "./EmptyImage";
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
  const triggerFly = useFlyToCart((s) => s.triggerFly);
  const [imgFailed, setImgFailed] = useState(false);
  const remove = useCart((s) => s.remove);

  const handleAdd = (e: MouseEvent<HTMLButtonElement>) => {
    if (sinStock || reachedMax) return;
    const rect = e.currentTarget.getBoundingClientRect();
    triggerFly({
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    });
    add(item.id);
  };
  const jornadas = useCart((s) => s.days());
  const hasDateRange = useCart((s) => !!s.startDate && !!s.endDate);
  const selected = qty > 0;
  const { data: clienteSession } = useClienteSession();
  const conIva = aplicaIva(clienteSession?.perfil_impuestos);
  // Cuando hay fechas y > 1 jornada, mostramos el total del período además
  // del precio por jornada. TODO #73: cuando haya descuentos, priceBreakdown
  // ya entrega effectivePerDay para mostrar el valor real por jornada.
  const price = priceBreakdown(item.pricePerDay, jornadas, 1);
  const showPeriodTotal = hasDateRange && jornadas > 1;
  const navigate = useNavigate();
  const openDetail = () =>
    navigate({ to: "/equipo/$slug", params: { slug: buildEquipoSlug(item) } });
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
        // Card 4:5 estilo IG: foto cuadrada arriba, info en el 20% restante.
        "aspect-[4/5]",
        selected
          ? "border-amber/60 shadow-[0_0_0_1px_var(--amber)]"
          : sinStock
          ? "hairline opacity-50"
          : "hairline hover:border-foreground/20",
      )}
    >
      <button
        type="button"
        onClick={openDetail}
        aria-label={`Ver detalle de ${item.name}`}
        className="relative block aspect-square w-full shrink-0 overflow-hidden text-left bg-white"
      >
        {item.fotoUrl && !imgFailed ? (
          <img
            src={item.fotoUrl}
            alt={item.name}
            loading={index < 4 ? "eager" : "lazy"}
            decoding="async"
            fetchPriority={index < 4 ? "high" : "low"}
            onError={() => setImgFailed(true)}
            className="h-full w-full object-contain p-3 transition group-hover:scale-[1.02]"
          />
        ) : (
          <EmptyImage category={item.category} brand={item.brand} />
        )}
        {item.isNew && (
          <div className="absolute left-2 top-2 flex items-center gap-1 rounded-full bg-ink px-2 py-0.5 font-mono text-[9px] uppercase tracking-widest text-amber">
            <Sparkles className="h-2.5 w-2.5" /> nuevo
          </div>
        )}
        {/* Destacado: convive con isNew en otra esquina */}
        {item.destacado && (
          <div className="absolute right-2 top-2 rounded-full bg-amber/90 px-2 py-0.5 font-mono text-[9px] uppercase tracking-widest text-ink shadow-sm">
            ★ destacado
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

      {/* Info compacta — ocupa el 20% restante (ratio 4:5 - 4:4 = 4:1) */}
      <div className="flex min-h-0 flex-1 items-center gap-2 px-2.5 py-1.5">
        {/* Columna izquierda: brand + name (truncado) */}
        <button
          type="button"
          onClick={openDetail}
          className="flex min-w-0 flex-1 flex-col text-left"
        >
          <div className="truncate font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground">
            {item.brand}
          </div>
          <div className="truncate font-display text-sm leading-tight tracking-tight text-ink hover:underline">
            {item.name}
          </div>
          <div className="flex items-baseline gap-1.5 leading-none">
            <span className="font-display text-sm tabular text-ink">
              {formatARS(item.pricePerDay)}
            </span>
            <span className="font-mono text-[8px] uppercase tracking-widest text-muted-foreground">
              /jornada{conIva ? " +IVA" : ""}
            </span>
            {disponible !== undefined && (
              <span
                className={cn(
                  "ml-auto font-mono text-[9px] uppercase tracking-widest tabular",
                  sinStock
                    ? "text-destructive"
                    : stockBajo
                    ? "text-amber-600"
                    : "text-muted-foreground",
                )}
              >
                {sinStock ? "—" : `${disponible} disp.`}
              </span>
            )}
          </div>
          {showPeriodTotal && (
            <div className="flex items-baseline gap-1 mt-0.5 leading-none">
              <span className="font-display text-xs tabular text-amber">
                {formatARS(price.total)}
              </span>
              <span className="font-mono text-[8px] uppercase tracking-widest text-muted-foreground">
                · {price.jornadas} jornadas
              </span>
            </div>
          )}
        </button>

        {/* Columna derecha: agregar / cantidad */}
        {qty === 0 ? (
          <button
            onClick={handleAdd}
            disabled={sinStock}
            aria-label="Agregar al carrito"
            className="grid h-10 w-10 sm:h-9 sm:w-9 shrink-0 place-items-center rounded-md border hairline transition hover:border-amber hover:bg-amber hover:text-ink active:bg-amber active:border-amber active:text-ink active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Plus className="h-4 w-4" />
          </button>
        ) : (
          <div className="flex shrink-0 items-center gap-0.5 rounded-md border border-amber/40 bg-amber-soft p-0.5">
            <button
              onClick={() => remove(item.id)}
              className="grid h-9 w-9 place-items-center rounded text-amber hover:bg-amber/20 active:bg-amber/30"
              aria-label="Quitar uno"
            >
              <Minus className="h-4 w-4" />
            </button>
            <span className="w-5 text-center text-sm tabular">{qty}</span>
            <button
              onClick={handleAdd}
              disabled={reachedMax}
              className="grid h-9 w-9 place-items-center rounded text-amber hover:bg-amber/20 active:bg-amber/30 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Sumar uno"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </motion.article>
  );
}
