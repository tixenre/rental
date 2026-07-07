import { useEffect, useState } from "react";
import { motion, useAnimationControls } from "framer-motion";
import { ShoppingBag } from "lucide-react";

import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { type CotizacionLinea } from "@/lib/cotizacion";
import { cn } from "@/lib/utils";
import { Button } from "@/design-system/ui/button";
import { EmptyImage } from "@/components/rental/EmptyImage";

/** Un ítem ya resuelto del preview (equipo del catálogo + cantidad). */
export type CartPreviewItem = { equipo: Equipment; qty: number };

/**
 * CartMiniBarView — el SHELL presentacional del mini-bar del carrito (mobile).
 *
 * Fuente única del diseño del mini-bar: no conoce `useCart` ni el backend. Recibe
 * todo computado por props (count, total, ítems del preview, fechas) y el `popKey`
 * para el bump al agregar. El container (`CartMiniBar`) lee el store + la cotización
 * y se lo pasa; la vitrina del DS le pasa estado mock → se prueba sin tocar el carrito.
 *
 * Por default es `fixed inset-x-0 bottom-0` (barra pegada abajo). Para mostrarlo
 * embebido, envolvelo en un contenedor con `transform` (crea containing block del fixed).
 */
export function CartMiniBarView({
  count,
  days,
  isEmpty,
  previewItems,
  lineas,
  totalNeto,
  conIva,
  hayFechas,
  popKey,
  onOpen,
  className,
}: {
  count: number;
  days: number;
  isEmpty: boolean;
  previewItems: CartPreviewItem[];
  /** Detalle por línea resuelto por el backend — ver mismo campo en CartDrawerView. */
  lineas?: CotizacionLinea[];
  totalNeto: number;
  conIva: boolean;
  hayFechas: boolean;
  /** Cambia → dispara el bump del ícono (fly-to-cart). */
  popKey: number;
  onOpen: () => void;
  className?: string;
}) {
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

  return (
    <div
      className={cn(
        "group/cart fixed inset-x-0 bottom-0 z-40 border-t-2 border-amber/60 bg-background/98 shadow-[0_-8px_32px_-8px_rgba(0,0,0,0.15)] backdrop-blur-xl",
        className,
      )}
    >
      {/* Preview hover — solo desktop con puntero fino. Slide-up al hover.
       * Diseño: bottom 100%, max-h 240px scrolleable. Hidden por default
       * (opacity 0, translateY 8). Hover → slide y fade-in. */}
      {!isEmpty && previewItems.length > 0 && (
        <div
          className="pointer-events-none absolute inset-x-0 bottom-full z-10 hidden translate-y-2 border-t hairline border-b-2 border-b-amber bg-card opacity-0 shadow-[0_-12px_24px_-8px_rgba(0,0,0,0.08)] transition-[opacity,transform] duration-150 lg:[@media(hover:hover)]:block lg:group-hover/cart:pointer-events-auto lg:group-hover/cart:translate-y-0 lg:group-hover/cart:opacity-100"
          aria-hidden="true"
        >
          <div className="mx-auto max-w-7xl px-4 py-2 lg:px-12">
            <div className="mb-1 t-eyebrow">
              En tu rental ({count} {count === 1 ? "ítem" : "ítems"})
            </div>
            <div className="max-h-[240px] overflow-y-auto">
              {previewItems.map(({ equipo, qty }) => (
                <CartPreviewRow
                  key={equipo.id}
                  equipo={equipo}
                  qty={qty}
                  days={days}
                  linea={lineas?.find(
                    (l) => l.equipoId === (equipo._backendId ?? Number(equipo.id)),
                  )}
                />
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
              <span className="absolute -right-1 -top-1 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-amber px-1 text-2xs font-bold tabular text-ink">
                {count}
              </span>
            )}
          </motion.div>
          <div className="leading-tight">
            <div className="text-sm font-semibold">
              {isEmpty ? "Carrito vacío" : `${count} ${count === 1 ? "ítem" : "ítems"}`}
            </div>
            <div className="t-eyebrow">
              {isEmpty ? "Sumá equipos" : `${days} ${days === 1 ? "jornada" : "jornadas"}`}
            </div>
          </div>
        </div>

        <div className="ml-auto text-right leading-tight">
          <div className="t-eyebrow">{hayFechas ? "Total" : "/ jornada"}</div>
          <div className="text-base font-semibold tabular sm:text-lg">
            {formatARS(totalNeto)}
            {conIva && <span className="text-xs font-normal text-muted-foreground"> + IVA</span>}
          </div>
        </div>

        <Button
          variant="amber"
          shape="pill"
          onClick={onOpen}
          disabled={isEmpty}
          className="h-auto px-4 py-2.5 font-semibold disabled:cursor-not-allowed disabled:opacity-40"
        >
          Ver carrito
        </Button>
      </div>
    </div>
  );
}

function CartPreviewRow({
  equipo,
  qty,
  days,
  linea,
}: {
  equipo: Equipment;
  qty: number;
  days: number;
  /** Línea resuelta por el backend — fallback al cálculo local si no llegó aún. */
  linea?: CotizacionLinea;
}) {
  const periodTotal = linea?.bruto ?? equipo.pricePerDay * qty * Math.max(days, 1);
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
          <span className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-ink px-1 font-mono text-3xs text-amber">
            ×{qty}
          </span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-mono text-2xs uppercase tracking-[0.18em] text-muted-foreground">
          {equipo.brand}
        </div>
        <div className="truncate text-sm leading-tight text-ink">{equipo.name}</div>
      </div>
      <div className="shrink-0 text-right">
        <div className="font-mono text-2xs uppercase tracking-wider text-muted-foreground">
          {days > 1 ? `${days} j · total` : "/ jornada"}
        </div>
        <div className="font-mono text-xs tabular text-ink">{formatARS(periodTotal)}</div>
      </div>
    </div>
  );
}
