import { format } from "date-fns";
import { es } from "date-fns/locale";
import { jornadasBetween } from "./rental-dates";

/** Formatea pesos argentinos: 97500 → "$97.500".
 *  Sin decimales: los precios se redondean al múltiplo de 100 al
 *  calcularse (ver `calcularPrecioJornada`), así que mostrar centavos
 *  no aporta nada y confunde visualmente. */
export const formatARS = (n: number) =>
  "$" +
  new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Math.round(n));

/** "6 may 11:00 → 7 may 10:00" o "Elegí tus fechas" */
export function formatRentalRange(start?: Date, end?: Date, startTime?: string, endTime?: string) {
  if (!start || !end) return "Elegí tus fechas";
  const s = format(start, "d MMM", { locale: es });
  const e = format(end, "d MMM", { locale: es });
  return `${s} ${startTime ?? ""} → ${e} ${endTime ?? ""}`.replace(/\s+/g, " ").trim();
}

/**
 * Cuenta jornadas entre dos fechas (1 jornada = 24 h, mínimo 1). Devuelve 0 si
 * falta alguna fecha.
 *
 * Delega en `jornadasBetween` (`src/lib/rental-dates.ts`) — la fuente ÚNICA del
 * conteo de jornadas, espejo del backend. NO reimplementa la aritmética. Para el
 * cálculo con horarios de negocio (hora de retiro vs. devolución) usar
 * `computeJornadas` del mismo módulo.
 *
 * @example
 *   countJornadas(new Date("2026-05-06"), new Date("2026-05-08")) // → 2
 *   countJornadas(new Date("2026-05-06"), new Date("2026-05-06")) // → 1
 */
export function countJornadas(start?: Date, end?: Date): number {
  if (!start || !end) return 0;
  return jornadasBetween(start, end);
}

/**
 * Pluraliza "jornada/jornadas" para chrome de UI. Fuente única del label —
 * reemplaza los "N jornada/s" inline repetidos por la app.
 *
 * @example
 *   jornadaLabel(1) // → "1 jornada"
 *   jornadaLabel(3) // → "3 jornadas"
 */
export const jornadaLabel = (n: number) => `${n} ${n === 1 ? "jornada" : "jornadas"}`;

/**
 * Formatea una fecha ISO string como "31 may" — para tablas del admin y
 * listas cortas donde el contexto ya provee el año.
 * El sufijo T12:00:00 evita el timezone shift en todos los browsers.
 *
 * @example formatFechaCorta("2026-05-31") // → "31 may"
 */
export function formatFechaCorta(s?: string | null): string {
  if (!s) return "—";
  const d = new Date(s.slice(0, 10) + "T12:00:00");
  const meses = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
  ];
  return `${d.getDate()} ${meses[d.getMonth()]}`;
}

/**
 * Formatea una fecha ISO string como "31-05-2026" — para detalle de pedidos
 * y documentos donde se necesita la fecha completa sin ambigüedad.
 *
 * @example formatFechaDisplay("2026-05-31") // → "31-05-2026"
 */
export function formatFechaDisplay(s?: string | null): string {
  if (!s) return "—";
  const d = new Date(s.slice(0, 10) + "T12:00:00");
  return [d.getDate(), d.getMonth() + 1, d.getFullYear()]
    .map((n) => String(n).padStart(2, "0"))
    .join("-");
}
