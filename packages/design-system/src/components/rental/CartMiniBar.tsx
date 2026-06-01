import { ShoppingBag } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatARS } from "@/lib/format";

/**
 * CartMiniBar — barra flotante bottom-fixed que resume el carrito.
 *
 * Visible solo cuando hay ítems en el carrito (count > 0).
 * Al hacer click abre el CartDrawer (onOpen).
 *
 * Desktop: hover sobre la barra muestra un preview ligero del contenido
 * (implementado como Tooltip/Popover externo — no incluido acá).
 *
 * Animación de badge: cuando count cambia, la badge del ícono ejecuta
 * scale [1 → 1.25 → 0.95 → 1] ease-bounce ~200ms.
 * El trigger está en el componente padre via framer-motion layout animations.
 *
 * z-index: --z-cart-strip (45) — por encima del CatBar (40) pero bajo scrim (60).
 *
 * Safe area: padding-bottom env(safe-area-inset-bottom) para notch/home indicator.
 *
 * Source visual: `preview/components-cart-mini-bar.html`
 */
export interface CartMiniBarProps {
  count: number;
  total: number;
  jornadas?: number;
  dateLabel?: string;
  onOpen: () => void;
  className?: string;
}

export function CartMiniBar({
  count,
  total,
  jornadas,
  dateLabel,
  onOpen,
  className,
}: CartMiniBarProps) {
  if (count === 0) return null;

  return (
    <div
      className={cn(
        "fixed bottom-0 left-0 right-0 z-[var(--z-cart-strip)]",
        "pb-[env(safe-area-inset-bottom)]",
        className,
      )}
    >
      <button
        type="button"
        onClick={onOpen}
        aria-label={`Abrir carrito — ${count} ítems, ${formatARS(total)}`}
        className={cn(
          "mx-auto flex w-full max-w-lg items-center gap-3",
          "rounded-t-2xl bg-ink px-5 py-3.5",
          "shadow-[var(--shadow-lg)]",
          "transition-transform duration-[var(--duration-fast)] active:scale-[0.99]",
        )}
      >
        {/* Ícono con badge */}
        <div className="relative flex-shrink-0">
          <ShoppingBag className="h-5 w-5 text-background" />
          <span
            aria-hidden
            className={cn(
              "absolute -right-1.5 -top-1.5",
              "flex h-5 min-w-[20px] items-center justify-center",
              "rounded-full bg-amber px-1",
              "font-mono text-[10px] font-bold text-ink",
            )}
          >
            {count}
          </span>
        </div>

        {/* Info central */}
        <div className="flex-1 text-left">
          <p className="font-sans text-sm font-semibold text-background leading-tight">
            {count} {count === 1 ? "ítem" : "ítems"}
            {dateLabel && (
              <span className="ml-2 font-normal text-background/60 text-xs">
                {dateLabel}
              </span>
            )}
          </p>
          {jornadas != null && (
            <p className="font-mono text-[10px] text-background/60">
              {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}
            </p>
          )}
        </div>

        {/* Total */}
        <div className="text-right flex-shrink-0">
          <p className="font-mono text-sm font-semibold tabular-nums text-amber">
            {formatARS(total)}
          </p>
          <p className="font-mono text-[9px] uppercase tracking-wider text-background/50">
            + IVA
          </p>
        </div>
      </button>
    </div>
  );
}
