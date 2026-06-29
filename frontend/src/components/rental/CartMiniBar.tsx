import { useCart } from "@/lib/cart-store";
import { useFlyToCart } from "@/lib/fly-to-cart-store";
import { type Equipment } from "@/data/equipment";
import { toLocalISO } from "@/lib/rental-dates";
import { useCotizacion, lineaPorEquipo } from "@/lib/cotizacion";
import { CartMiniBarView, type CartPreviewItem } from "./CartMiniBarView";

/**
 * CartMiniBar — container del mini-bar del carrito (mobile).
 *
 * Lee el store (`useCart`), el pop del fly-to-cart y la cotización del backend, y
 * se lo pasa al shell presentacional `CartMiniBarView` (la fuente única del diseño,
 * que también muestra la vitrina del DS con estado mock). Acá vive solo el cableado;
 * el markup vive en la View.
 */
export function CartMiniBar({ allEquipos }: { allEquipos: Equipment[] }) {
  const items = useCart((s) => s.items);
  const days = useCart((s) => s.days)();
  const startDate = useCart((s) => s.startDate);
  const endDate = useCart((s) => s.endDate);
  const startTime = useCart((s) => s.startTime);
  const endTime = useCart((s) => s.endTime);
  const setDrawerOpen = useCart((s) => s.setDrawerOpen);
  const popKey = useFlyToCart((s) => s.popKey);

  const entries = Object.entries(items);
  const count = entries.reduce((a, [, q]) => a + q, 0);
  const isEmpty = count === 0;

  // Pre-computar para el preview hover. Filtramos items que ya no estén
  // en el catálogo (edge case por estado stale del cart).
  const previewItems: CartPreviewItem[] = entries
    .map(([id, qty]) => {
      const equipo = allEquipos.find((e) => e.id === id);
      return equipo ? { equipo, qty } : null;
    })
    .filter((x): x is CartPreviewItem => x !== null);

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

  return (
    <CartMiniBarView
      count={count}
      days={days}
      isEmpty={isEmpty}
      previewItems={previewItems}
      totalNeto={totales.totalNeto}
      conIva={totales.conIva}
      hayFechas={hayFechas}
      popKey={popKey}
      onOpen={() => setDrawerOpen(true, "bottom")}
    />
  );
}
