/**
 * Formato compartido para el kit. Lift de `src/lib/format.ts` del repo;
 * mantenelo sincronizado.
 *
 * Solo requiere `date-fns` y la dependencia ya está en el repo. Si la usás
 * en un proyecto nuevo, instalá:
 *   npm install date-fns
 */
import { format } from "date-fns";
import { es } from "date-fns/locale";

/**
 * Formatea pesos argentinos: `97500` → `"$ 97.500"`.
 *
 * Sin decimales: en Rambla los precios se redondean al múltiplo de 100
 * al calcularse (ver `calcularPrecioJornada` en el repo), así que mostrar
 * centavos no aporta nada y confunde visualmente.
 *
 * @example
 *   formatARS(24500)   // "$ 24.500"
 *   formatARS(2840500) // "$ 2.840.500"
 */
export const formatARS = (n: number) =>
  "$ " +
  new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Math.round(n));

/**
 * Formatea un rango de fechas de alquiler.
 * `"6 may 11:00 → 7 may 10:00"` o `"Elegí tus fechas"` si falta alguna.
 *
 * @example
 *   formatRentalRange(new Date("2026-05-06"), new Date("2026-05-07"), "11:00", "10:00")
 *   // → "6 may 11:00 → 7 may 10:00"
 */
export function formatRentalRange(
  start?: Date,
  end?: Date,
  startTime?: string,
  endTime?: string,
) {
  if (!start || !end) return "Elegí tus fechas";
  const s = format(start, "d MMM", { locale: es });
  const e = format(end, "d MMM", { locale: es });
  return `${s} ${startTime ?? ""} → ${e} ${endTime ?? ""}`
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Cuenta jornadas entre dos fechas. Una jornada = un día calendario
 * con sus horas. La regla del repo: si retirás el lunes 10:00 y devolvés
 * el martes 09:00, son 2 jornadas (no 1 día).
 *
 * Versión simplificada del kit. Para casos con horarios non-business,
 * usar `src/lib/pricing.ts` del repo.
 */
export function countJornadas(start?: Date, end?: Date): number {
  if (!start || !end) return 0;
  const ms = end.getTime() - start.getTime();
  return Math.max(1, Math.ceil(ms / (24 * 60 * 60 * 1000)));
}

/**
 * Pluraliza la palabra jornada/jornadas para chrome ("1 jornada", "3 jornadas").
 */
export const jornadaLabel = (n: number) => `${n} ${n === 1 ? "jornada" : "jornadas"}`;
