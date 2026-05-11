/**
 * Cálculo de precios de alquiler.
 *
 * Hoy: simple multiplicación pricePerDay × jornadas.
 *
 * Mañana (issue #73): aplicar descuentos por cantidad de jornadas
 * (tramos configurables) y descuento del cliente preestablecido. Cuando se
 * implemente, este helper devuelve `total` aplicando el descuento; el
 * `effectivePerDay` muestra el valor por jornada real (post-descuento) — que
 * será distinto al `perDay` base.
 *
 * Mantener TODO el cálculo de precios pasando por acá para que el día que se
 * agreguen descuentos no haya que tocar todos los componentes.
 */

export type PriceBreakdown = {
  /** Precio por jornada listado del equipo (base, sin descuentos). */
  perDay: number;
  /** Total del período, ya con descuentos aplicados (hoy: total = perDay × jornadas). */
  total: number;
  /** Valor efectivo por jornada (total / jornadas). Hoy igual a perDay; con descuentos, menor. */
  effectivePerDay: number;
  /** Cantidad de jornadas del período. */
  jornadas: number;
  /** Cantidad de unidades del equipo en el carrito. */
  qty: number;
};

/**
 * Calcula el desglose de precio para un equipo dado un período y cantidad.
 *
 * @param pricePerDay precio por jornada listado del equipo
 * @param jornadas cantidad de jornadas del período (>= 1)
 * @param qty cantidad de unidades del equipo (>= 1, default 1)
 */
export function priceBreakdown(
  pricePerDay: number,
  jornadas: number,
  qty: number = 1,
): PriceBreakdown {
  const j = Math.max(1, jornadas);
  const q = Math.max(1, qty);
  // TODO #73: aplicar descuentos por jornadas + descuento del cliente.
  // Por ahora es lineal — pricePerDay × jornadas × qty.
  const total = pricePerDay * j * q;
  return {
    perDay: pricePerDay,
    total,
    effectivePerDay: total / j / q,
    jornadas: j,
    qty: q,
  };
}
