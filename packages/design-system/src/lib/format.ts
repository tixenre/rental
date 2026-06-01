/**
 * Rambla Rental — formatters canónicos
 * ------------------------------------------------------------
 * Fuente única de formato de precios, fechas y jornadas.
 * REGLA: nunca formatear ARS/fechas a mano en componentes — usar estos.
 *
 * Locale: es-AR (voseo, ARS, punto como separador de miles).
 */

import { format, type Locale } from "date-fns";
import { es } from "date-fns/locale";

/* ── Precios ───────────────────────────────────────────────────
   formatARS(24500)        → "$ 24.500"
   formatARS(145500,{iva}) → "$ 145.500 + IVA"   (NO suma el IVA)
   El IVA es un sufijo informativo: el neto no se modifica. */
export function formatARS(
  amount: number,
  opts: { iva?: boolean; decimals?: boolean } = {},
): string {
  const { iva = false, decimals = false } = opts;
  const n = new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: decimals ? 2 : 0,
    maximumFractionDigits: decimals ? 2 : 0,
  }).format(amount);
  return `$ ${n}${iva ? " + IVA" : ""}`;
}

/* ── Fechas ────────────────────────────────────────────────────
   formatShortDate(d) → "lun 2 jun." */
export function formatShortDate(date: Date, locale: Locale = es): string {
  return format(date, "eee d MMM.", { locale });
}

/* formatRentalRange(a, b) → "lun 2 → jue 5 jun."
   Si comparten mes, el mes se muestra solo al final. */
export function formatRentalRange(from: Date, to: Date, locale: Locale = es): string {
  const sameMonth = from.getMonth() === to.getMonth() && from.getFullYear() === to.getFullYear();
  const left = sameMonth
    ? format(from, "eee d", { locale })
    : format(from, "eee d MMM.", { locale });
  const right = format(to, "eee d MMM.", { locale });
  return `${left} → ${right}`;
}

/* ── Jornadas ──────────────────────────────────────────────────
   jornadaLabel(3)            → "3 jornadas"
   jornadaLabel(1)            → "1 jornada"
   jornadaLabel(3,{compact})  → "3 J"  (para cards chicas) */
export function jornadaLabel(n: number, opts: { compact?: boolean } = {}): string {
  if (opts.compact) return `${n} J`;
  return `${n} ${n === 1 ? "jornada" : "jornadas"}`;
}

/* ── Breakdown de precio ───────────────────────────────────────
   priceBreakdown(24500, 3) → { perDay, jornadas, total } */
export function priceBreakdown(pricePerDay: number, jornadas: number) {
  return {
    perDay: pricePerDay,
    jornadas,
    total: pricePerDay * jornadas,
  };
}
