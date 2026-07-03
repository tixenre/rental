/**
 * Precio de REFERENCIA de un equipo — simple multiplicación pricePerDay × jornadas,
 * SIN descuentos. Alcance acotado a propósito (no es un TODO pendiente): los
 * descuentos (cliente/jornadas/manual, `backend/descuentos/`) ya están implementados
 * hace tiempo, pero solo se resuelven en el backend vía `/api/cotizar` — "el front no
 * calcula plata" (MEMORIA 2026-06-29). Este helper se usa donde todavía no hay fechas
 * elegidas (`PreviewPane`, `PriceBlock`) para mostrar un precio de referencia rápido,
 * sin pegarle al backend — nunca para el total real de una reserva.
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
  // Lineal a propósito, sin descuento — ver docstring del módulo.
  const total = pricePerDay * j * q;
  return {
    perDay: pricePerDay,
    total,
    effectivePerDay: total / j / q,
    jornadas: j,
    qty: q,
  };
}
