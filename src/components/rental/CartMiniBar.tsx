import { useEffect, useState } from "react";
import { motion, useAnimationControls } from "framer-motion";
import { ShoppingBag } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { useFlyToCart } from "@/lib/fly-to-cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";

export function CartMiniBar({ allEquipos }: { allEquipos: Equipment[] }) {
  const items = useCart((s) => s.items);
  const days = useCart((s) => s.days)();
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

  const perDay = entries.reduce((acc, [id, qty]) => {
    const item = allEquipos.find((e) => e.id === id);
    if (!item) return acc;
    return acc + item.pricePerDay * qty;
  }, 0);
  const total = perDay * days;
  const isEmpty = count === 0;

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t-2 border-amber/60 bg-background/98 shadow-[0_-8px_32px_-8px_rgba(0,0,0,0.15)] backdrop-blur-xl">
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
              {isEmpty
                ? "Sumá equipos"
                : `${days} ${days === 1 ? "jornada" : "jornadas"}`}
            </div>
          </div>
        </div>

        <div className="ml-auto text-right leading-tight">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Total
          </div>
          <div className="text-base font-semibold tabular sm:text-lg">
            {formatARS(total)}
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
