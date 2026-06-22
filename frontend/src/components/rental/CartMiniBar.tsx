import { useEffect, useState } from "react";
import { motion, useAnimationControls } from "framer-motion";
import { ShoppingBag } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { useFlyToCart } from "@/lib/fly-to-cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { EmptyImage } from "./EmptyImage";
import { toLocalISO } from "@/lib/rental-dates";
import { useCotizacion } from "@/lib/cotizacion";

export function CartMiniBar({ allEquipos }: { allEquipos: Equipment[] }) {
  const items = useCart((s) => s.items);
  const days = useCart((s) => s.days)();
  const startDate = useCart((s) => s.startDate);
  const endDate = useCart((s) => s.endDate);
  const startTime = useCart((s) => s.startTime);
  const endTime = useCart((s) => s.endTime);
  const setDrawerOpen = useCart((s) => s.setDrawerOpen);
  const popKey = useFlyToCart((s) => s.popKey);
  const controls = useAnimationControls();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (!mounted) {
      setMounted(true);
      return;
    }
    controls.start({
      scale: [1, 1.25, 0.95, 1],
      transition: { duration: 0.45, ease: "easeOut" },
    });
  }, [popKey, mounted, controls]);

  const entries = Object.entries(items);
  const count = entries.reduce((a, [, q]) => a + q, 0);
  const isEmpty = count === 0;

  // Pre-computar para el preview hover. Filtramos items que ya no estén
  // en el catálogo (edge case por estado stale del cart).
  const previewItems = entries
    .map(([id, qty]) => {
      const equipo = allEquipos.find((e) => e.id === id);
      return equipo ? { equipo, qty } : null;
    })
    .filter((x): x is { equipo: Equipment; qty: number } => x !== null);

  // Total calculado por el BACKEND (fuente única, /api/cotizar) — mismo número
  // que el drawer/sheet. Sin fechas → estimado de una jornada sin IVA. #617.
  const hayFechas = !!(startDate && endDate);
  const { data: totales } = useCotizacion({
    items: previewItems.map(({ equipo, qty }) => ({
      equipoId: equipo._backendId ?? Number(equipo.id),
      cantidad: qty,
    })),
    fechaDesde: hayFechas ? toLocalISO(startDate!, startTime) : null,
    fechaHasta: hayFechas ? toLocalISO(endDate!, endTime) : null,
  });
  const totalNeto = totales.totalNeto;
  const conIva = totales.conIva;

  return (
    <div className="group/cart fixed inset-x-0 bottom-0 z-40 border-t-2 border-amber/60 bg-background/98 shadow-[0_-8px_32px_-8px_rgba(0,0,0,0.15)] backdrop-blur-xl">
      {/* Preview hover — solo desktop con puntero fino. Slide-up al hover.
       * Diseño: bottom 100%, max-h 240px scrolleable. Hidden por default
       * (opacity 0, translateY 8). Hover → slide y fade-in. */}
      {!isEmpty && previewItems.length > 0 && (
        <div
          className="pointer-events-none absolute inset-x-0 bottom-full z-10 hidden translate-y-2 border-t hairline border-b-2 border-b-amber bg-card opacity-0 shadow-[0_-12px_24px_-8px_rgba(0,0,0,0.08)] transition-[opacity,transform] duration-150 lg:[@media(hover:hover)]:block lg:group-hover/cart:pointer-events-auto lg:group-hover/cart:translate-y-0 lg:group-hover/cart:opacity-100"
          aria-hidden="true"
        >
          <div className="mx-auto max-w-7xl px-4 py-2 lg:px-12">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
              En tu rental ({count} {count === 1 ? "ítem" : "ítems"})
            </div>
            <div className="max-h-[240px] overflow-y-auto">
              {previewItems.map(({ equipo, qty }) => (
                <CartPreviewRow key={equipo.id} equipo={equipo} qty={qty} days={days} />
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] lg:px-12">
        <div className="flex items-center gap-2.5">
          <motion.div
            data-cart-icon
            animate={controls}
            className="relative flex h-10 w-10 items-center justify-center rounded-full bg-foreground text-background"
          >
            <ShoppingBag className="h-4 w-4" />
            {!isEmpty && (
              <span className="absolute -right-1 -top-1 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-amber px-1 text-[10px] font-bold tabular text-ink">
                {count}
              </span>
            )}
          </motion.div>
          <div className="leading-tight">
            <div className="text-sm font-semibold">
              {isEmpty ? "Carrito vacío" : `${count} ${count === 1 ? "ítem" : "ítems"}`}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              {isEmpty ? "Sumá equipos" : `${days} ${days === 1 ? "jornada" : "jornadas"}`}
            </div>
          </div>
        </div>

        <div className="ml-auto text-right leading-tight">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            {hayFechas ? "Total" : "/ jornada"}
          </div>
          <div className="text-base font-semibold tabular sm:text-lg">
            {formatARS(totalNeto)}
            {conIva && <span className="text-xs font-normal text-muted-foreground"> + IVA</span>}
          </div>
        </div>

        <button
          onClick={() => setDrawerOpen(true, "bottom")}
          disabled={isEmpty}
          className="rounded-full bg-amber px-4 py-2.5 text-sm font-semibold text-ink transition hover:bg-amber/90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Ver carrito
        </button>
      </div>
    </div>
  );
}

function CartPreviewRow({ equipo, qty, days }: { equipo: Equipment; qty: number; days: number }) {
  const periodTotal = equipo.pricePerDay * qty * Math.max(days, 1);
  return (
    <div className="flex items-center gap-2.5 py-1">
      <div className="relative h-8 w-8 shrink-0 overflow-hidden rounded bg-white">
        {equipo.fotoUrl ? (
          <img
            src={equipo.fotoUrl}
            alt={equipo.name}
            className="h-full w-full object-contain p-0.5"
            loading="lazy"
            decoding="async"
          />
        ) : (
          <EmptyImage category={equipo.category} brand={equipo.brand} />
        )}
        {qty > 1 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-ink px-1 font-mono text-[9px] text-amber">
            ×{qty}
          </span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          {equipo.brand}
        </div>
        <div className="truncate text-[13px] leading-tight text-ink">{equipo.name}</div>
      </div>
      <div className="shrink-0 text-right">
        <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          {days > 1 ? `${days} j · total` : "/ jornada"}
        </div>
        <div className="font-mono text-[12px] tabular text-ink">{formatARS(periodTotal)}</div>
      </div>
    </div>
  );
}
