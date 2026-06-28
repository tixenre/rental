import { useCart } from "@/lib/cart-store";

/** Una línea de una composición guardada: qué equipo y cuántas unidades. */
export type ComposicionItem = { equipoId: number; cantidad: number };

/**
 * Rearma el carrito desde una composición guardada — un pedido anterior, una
 * lista personal del cliente o un carrito compartido. Es la primitiva única de
 * esas features: reconstruye el carrito, no mergea.
 *
 * REEMPLAZA el contenido actual del carrito y NO arrastra fechas ni precios. El
 * carrito y el catálogo re-resuelven precio y disponibilidad ACTUALES contra
 * `useEquipos` (la clave del store es `String(equipo_id)`). Esto respeta la
 * decisión "plata/ítems congelados" (MEMORIA 2026-06-06): el snapshot congelado
 * del pedido viejo NO se reusa para cotizar — la nueva reserva se cotiza de cero.
 *
 * El llamador decide la confirmación (si el carrito no estaba vacío) y la
 * navegación al catálogo (`/?openCarrito=1`); esta primitiva solo toca el store.
 *
 * @returns cuántas líneas se cargaron (cantidad > 0). Un equipo borrado del
 *   catálogo igual se carga acá, pero el CartDrawer lo filtra al resolver contra
 *   `allEquipos` — la fuente de verdad de lo reservable sigue siendo el catálogo.
 */
export function rearmarCarrito(composicion: ComposicionItem[]): number {
  const { clear, setQty } = useCart.getState();
  clear();
  let cargados = 0;
  for (const { equipoId, cantidad } of composicion) {
    if (cantidad > 0) {
      setQty(String(equipoId), cantidad);
      cargados += 1;
    }
  }
  return cargados;
}
