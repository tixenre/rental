import { X, ShoppingBag, Trash2, Minus, Plus } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { formatARS } from "@/lib/format";
import { PriceBlock } from "@/components/kit/PriceBlock";

/**
 * CartDrawer — sheet lateral con el contenido del carrito.
 *
 * Slide-in desde la derecha. Animación: x 100% → 0, ease [0.32,0.72,0,1] 350ms.
 * Scrim: bg-ink/40 backdrop-blur-sm, z-scrim (60). Drawer: z-drawer (61).
 *
 * Comportamiento:
 *   - Click en scrim → onClose.
 *   - Swipe right (mobile) → onClose (implementado externamente con framer useDrag).
 *   - overscroll-contain en la lista para evitar propagación al body.
 *   - Sin fechas seleccionadas: muestra banner "Seleccioná fechas para ver el total".
 *
 * Checkout CTA: primary pill ink→amber. Disabled si el carrito está vacío.
 *
 * Source visual: `preview/components-cart-drawer.html`
 * Source tokens: Motion → --ease-default 350ms, z-index → --z-drawer/--z-scrim
 */

export interface CartDrawerItem {
  id: string;
  name: string;
  brand: string;
  pricePerDay: number;
  qty: number;
  photoUrl?: string;
}

export interface CartDrawerProps {
  open: boolean;
  onClose: () => void;
  items: CartDrawerItem[];
  jornadas?: number;
  dateLabel?: string;
  onIncrement: (id: string) => void;
  onDecrement: (id: string) => void;
  onRemove: (id: string) => void;
  onCheckout: () => void;
}

export function CartDrawer({
  open,
  onClose,
  items,
  jornadas,
  dateLabel,
  onIncrement,
  onDecrement,
  onRemove,
  onCheckout,
}: CartDrawerProps) {
  const subtotal = items.reduce((sum, i) => sum + i.pricePerDay * i.qty * (jornadas ?? 1), 0);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* ── Scrim ── */}
          <motion.div
            key="cart-scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            aria-hidden
            className="fixed inset-0 z-[var(--z-scrim)] bg-ink/40 backdrop-blur-sm"
          />

          {/* ── Drawer ── */}
          <motion.aside
            key="cart-drawer"
            role="dialog"
            aria-label="Carrito de rental"
            aria-modal="true"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ ease: [0.32, 0.72, 0, 1], duration: 0.35 }}
            className={cn(
              "fixed bottom-0 right-0 top-0",
              "z-[var(--z-drawer)] flex w-full max-w-sm flex-col",
              "bg-surface-elevated shadow-[var(--shadow-xl)]",
              "overscroll-contain",
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-hairline px-5 py-4 flex-shrink-0">
              <div className="flex items-center gap-2.5">
                <ShoppingBag className="h-4 w-4 text-ink" />
                <h2 className="text-base font-bold text-ink">Tu rental</h2>
                {dateLabel && (
                  <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                    {dateLabel}
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Cerrar carrito"
                className="grid h-8 w-8 place-items-center rounded-full border border-hairline text-muted-foreground transition-colors hover:text-ink"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Sin fechas banner */}
            {!jornadas && items.length > 0 && (
              <div className="mx-4 mt-4 rounded-lg border border-amber/40 bg-amber/10 px-4 py-3">
                <p className="text-xs font-medium text-ink">
                  Seleccioná fechas para ver el total del rental.
                </p>
              </div>
            )}

            {/* Items list */}
            <div className="flex-1 overflow-y-auto overscroll-contain">
              {items.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-3 px-8 py-12 text-center">
                  <ShoppingBag className="h-10 w-10 text-muted-foreground/20" />
                  <p className="text-sm text-muted-foreground">Todavía no agregaste equipos.</p>
                </div>
              ) : (
                <ul className="divide-y divide-hairline">
                  {items.map((item) => (
                    <li key={item.id} className="flex gap-3 p-4">
                      {/* Thumbnail */}
                      <div className="h-14 w-14 flex-shrink-0 overflow-hidden rounded-md bg-surface">
                        {item.photoUrl ? (
                          <img
                            src={item.photoUrl}
                            alt={item.name}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          /* TODO: placeholder thumbnail */
                          <div className="h-full w-full" />
                        )}
                      </div>

                      {/* Info + controles */}
                      <div className="flex flex-1 min-w-0 flex-col gap-1.5">
                        <div>
                          <p className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground">
                            {item.brand}
                          </p>
                          <p className="text-sm font-semibold leading-tight text-ink truncate">
                            {item.name}
                          </p>
                        </div>

                        <div className="flex items-center justify-between gap-2">
                          {/* Stepper inline mini */}
                          <div className="inline-flex items-center gap-0.5 rounded-full border border-hairline bg-surface px-0.5 py-0.5">
                            <button
                              type="button"
                              aria-label="Restar uno"
                              onClick={() => onDecrement(item.id)}
                              className="grid h-5 w-5 place-items-center rounded-full transition-colors hover:bg-ink hover:text-background"
                            >
                              <Minus className="h-2.5 w-2.5" />
                            </button>
                            <span className="min-w-[18px] text-center font-mono text-xs tabular-nums text-ink">
                              {item.qty}
                            </span>
                            <button
                              type="button"
                              aria-label="Sumar uno"
                              onClick={() => onIncrement(item.id)}
                              className="grid h-5 w-5 place-items-center rounded-full transition-colors hover:bg-ink hover:text-background"
                            >
                              <Plus className="h-2.5 w-2.5" />
                            </button>
                          </div>

                          <PriceBlock
                            pricePerDay={item.pricePerDay}
                            jornadas={jornadas}
                            align="right"
                            className="flex-1"
                          />
                        </div>
                      </div>

                      {/* Eliminar */}
                      <button
                        type="button"
                        aria-label={`Eliminar ${item.name}`}
                        onClick={() => onRemove(item.id)}
                        className="mt-0.5 flex-shrink-0 self-start text-muted-foreground/50 transition-colors hover:text-destructive"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Footer */}
            {items.length > 0 && (
              <div className="border-t border-hairline p-5 flex-shrink-0 space-y-3">
                {jornadas ? (
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs uppercase tracking-[0.1em] text-muted-foreground">
                      Total · {jornadas} J
                    </span>
                    <span className="font-mono text-lg font-semibold tabular-nums text-ink">
                      {formatARS(subtotal)}
                    </span>
                  </div>
                ) : null}
                <p className="font-mono text-[10px] text-muted-foreground">
                  + IVA · Precio sujeto a confirmación.
                </p>
                <button
                  type="button"
                  onClick={onCheckout}
                  className={cn(
                    "w-full rounded-full py-3",
                    "font-sans text-sm font-bold",
                    "bg-ink text-background",
                    "transition-all duration-[var(--duration-base)]",
                    "hover:bg-amber hover:text-ink",
                    "active:scale-[0.98]",
                  )}
                >
                  Reservar
                </button>
              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
