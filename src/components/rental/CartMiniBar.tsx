import { ShoppingBag } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { getAvailability } from "@/lib/availability";

export function CartMiniBar() {
  const items = useCart((s) => s.items);
  const startDate = useCart((s) => s.startDate);
  const endDate = useCart((s) => s.endDate);
  const days = useCart((s) => s.days)();
  const setDrawerOpen = useCart((s) => s.setDrawerOpen);

  const entries = Object.entries(items);
  const count = entries.reduce((a, [, q]) => a + q, 0);

  // Subtotal por día respetando disponibilidad (mismas reglas del drawer)
  const perDay = entries.reduce((acc, [id, qty]) => {
    const item = equipment.find((e) => e.id === id);
    if (!item) return acc;
    const av = getAvailability(item, startDate, endDate);
    if (!av.available || qty > av.stock) return acc;
    return acc + item.pricePerDay * qty;
  }, 0);
  const total = perDay * days;
  const isEmpty = count === 0;

  return (
    <div className="sticky bottom-0 z-30 border-t hairline bg-background/95 backdrop-blur-xl">
      <div className="flex items-center gap-3 px-4 py-3 lg:px-12">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-foreground text-background">
            <ShoppingBag className="h-4 w-4" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold tabular">
              {count} {count === 1 ? "ítem" : "ítems"}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              {days} {days === 1 ? "jornada" : "jornadas"}
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
          onClick={() => setDrawerOpen(true)}
          className="rounded-full bg-amber px-4 py-2.5 text-sm font-semibold text-ink transition hover:bg-amber/90"
        >
          Ver carrito
        </button>
      </div>
    </div>
  );
}
