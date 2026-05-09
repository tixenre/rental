import { AnimatePresence, motion } from "framer-motion";
import { X, Trash2, Plus, Minus, AlertTriangle } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { equipment, formatPrice } from "@/data/equipment";
import { getAvailability } from "@/lib/availability";
import { EmptyImage } from "./EmptyImage";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { useMemo } from "react";

export function CartDrawer() {
  const {
    drawerOpen,
    setDrawerOpen,
    drawerPlacement,
    items,
    add,
    remove,
    setQty,
    clear,
    days,
    startDate,
    endDate,
    startTime,
    endTime,
  } = useCart();

  const isBottom = drawerPlacement === "bottom";

  const d = days();

  // Recalcula disponibilidad + precios cada vez que cambian fechas o ítems
  const list = useMemo(() => {
    return Object.entries(items)
      .map(([id, qty]) => {
        const it = equipment.find((e) => e.id === id);
        if (!it) return null;
        const availability = getAvailability(it, startDate, endDate);
        const conflict = !availability.available || qty > availability.stock;
        return { it, qty, availability, conflict };
      })
      .filter(Boolean) as {
      it: (typeof equipment)[number];
      qty: number;
      availability: ReturnType<typeof getAvailability>;
      conflict: boolean;
    }[];
  }, [items, startDate, endDate]);

  const subtotal = list
    .filter((l) => !l.conflict)
    .reduce((s, { it, qty }) => s + it.pricePerDay * qty, 0);
  const total = subtotal * d;
  const conflictCount = list.filter((l) => l.conflict).length;


  return (
    <AnimatePresence>
      {drawerOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setDrawerOpen(false)}
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
          />
          <motion.aside
            initial={isBottom ? { y: "100%" } : { x: "100%" }}
            animate={isBottom ? { y: 0 } : { x: 0 }}
            exit={isBottom ? { y: "100%" } : { x: "100%" }}
            transition={{ type: "tween", duration: 0.3, ease: [0.32, 0.72, 0, 1] }}
            className={
              isBottom
                ? "fixed inset-x-0 bottom-0 z-50 flex max-h-[85vh] w-full flex-col rounded-t-2xl border-t hairline bg-background shadow-2xl"
                : "fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l hairline bg-background"
            }
          >
            {isBottom && (
              <div className="mx-auto mt-2 h-1 w-10 shrink-0 rounded-full bg-foreground/20" />
            )}
            <div className="flex items-center justify-between border-b hairline px-6 py-4">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                  Tu pedido
                </div>
                <h2 className="font-display text-2xl">Cotización</h2>
              </div>
              <button
                onClick={() => setDrawerOpen(false)}
                className="grid h-8 w-8 place-items-center rounded-md hover:bg-surface"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="border-b hairline px-6 py-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    Desde
                  </div>
                  <div className="tabular">
                    {startDate ? format(startDate, "dd MMM yyyy", { locale: es }) : "—"}
                    <span className="text-muted-foreground"> · {startTime}</span>
                  </div>
                </div>
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    Hasta
                  </div>
                  <div className="tabular">
                    {endDate ? format(endDate, "dd MMM yyyy", { locale: es }) : "—"}
                    <span className="text-muted-foreground"> · {endTime}</span>
                  </div>
                </div>
              </div>
              <div className="mt-3 font-mono text-[11px] uppercase tracking-widest text-ink">
                {d} {d === 1 ? "jornada" : "jornadas"}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-4">
              {list.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <div className="font-display text-xl text-muted-foreground">
                    Tu pedido está vacío
                  </div>
                  <p className="mt-2 max-w-xs text-sm text-muted-foreground">
                    Elegí equipos del catálogo y se sumarán acá.
                  </p>
                </div>
              ) : (
                <ul className="space-y-3">
                  {list.map(({ it, qty, availability, conflict }) => (
                    <li
                      key={it.id}
                      className={
                        "flex gap-3 rounded-lg border p-3 transition " +
                        (conflict
                          ? "border-destructive/50 bg-destructive/5"
                          : "hairline bg-surface")
                      }
                    >
                      <div className="h-16 w-20 shrink-0 overflow-hidden rounded">
                        <EmptyImage category={it.category} brand={it.brand} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                          {it.brand}
                        </div>
                        <div className="truncate font-display text-sm leading-tight">
                          {it.name}
                        </div>
                        {conflict ? (
                          <div className="mt-1 flex items-center gap-1 text-[11px] text-destructive">
                            <AlertTriangle className="h-3 w-3" />
                            {availability.reason ??
                              `Solo ${availability.stock} disponible${availability.stock === 1 ? "" : "s"}`}
                          </div>
                        ) : availability.stock <= 1 ? (
                          <div className="mt-1 text-[11px] text-amber-600">
                            Último disponible
                          </div>
                        ) : null}
                        <div className="mt-1 flex items-center justify-between">
                          <div className="flex items-center gap-1 rounded border hairline">
                            <button
                              onClick={() => remove(it.id)}
                              className="grid h-6 w-6 place-items-center hover:text-ink"
                            >
                              <Minus className="h-3 w-3" />
                            </button>
                            <span className="w-5 text-center text-xs tabular">
                              {qty}
                            </span>
                            <button
                              onClick={() => add(it.id)}
                              disabled={qty >= availability.stock}
                              className="grid h-6 w-6 place-items-center hover:text-ink disabled:opacity-30 disabled:cursor-not-allowed"
                            >
                              <Plus className="h-3 w-3" />
                            </button>
                          </div>
                          <div
                            className={
                              "text-xs tabular " +
                              (conflict ? "text-muted-foreground line-through" : "text-ink")
                            }
                          >
                            ${formatPrice(it.pricePerDay * qty)}
                            <span className="text-muted-foreground"> /día</span>
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => setQty(it.id, 0)}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="border-t hairline px-6 py-5 space-y-3">
              {conflictCount > 0 && (
                <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-[11px] text-destructive">
                  <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                  <span>
                    {conflictCount} {conflictCount === 1 ? "ítem no está" : "ítems no están"} disponible{conflictCount === 1 ? "" : "s"} en estas fechas y se excluye{conflictCount === 1 ? "" : "n"} del total.
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Subtotal por jornada</span>
                <span className="tabular">${formatPrice(subtotal)}</span>
              </div>
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>× {d} {d === 1 ? "jornada" : "jornadas"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                  Total estimado
                </span>
                <span className="font-display text-3xl tabular text-ink">
                  ${formatPrice(total)}
                </span>
              </div>
              <button
                disabled={list.length === 0}
                className="w-full rounded-md bg-amber py-3 text-sm font-medium uppercase tracking-widest text-ink transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Solicitar cotización
              </button>
              {list.length > 0 && (
                <button
                  onClick={clear}
                  className="w-full text-xs text-muted-foreground hover:text-destructive"
                >
                  Vaciar pedido
                </button>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
