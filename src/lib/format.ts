import { format } from "date-fns";
import { es } from "date-fns/locale";

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
