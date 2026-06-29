import { formatARS, formatMoney, UNIDADES, type Unidad } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Familia de componentes de plata del back-office — una sola forma por TIPO de
 * plata (no un solo componente para todo). Cada uno encapsula su formato + jerarquía:
 *  - <Monto>          monto suelto (ARS por defecto; `moneda` para USD/otras).
 *  - <PrecioUnidad>   el precio con su unidad: "$X/jornada" (rental) o "$X/hora"
 *                     (estudio); `compact` para mobile ("$X/j", "$X/h").
 */

/**
 * Monto — un monto con jerarquía de plata. ARS por defecto; pasá `moneda` (ej.
 * "USD") y formatea con `formatMoney` (US$). Los montos relevantes anclan en
 * `text-ink font-medium tabular-nums`; cero/vacío en muted; deuda en destructive.
 */
export function Monto({
  value,
  tone = "auto",
  moneda,
  className,
}: {
  value: number | null | undefined;
  /**
   * - `auto` (default): ink+medium si ≠0, muted si 0.
   * - `debt`: destructive (saldo a cobrar / deuda).
   * - `strong`: siempre ink+semibold (totales).
   * - `muted`: siempre secundario.
   */
  tone?: "auto" | "debt" | "strong" | "muted";
  /** Moneda del monto (default ARS). "USD" → "US$ 1.200" vía formatMoney. */
  moneda?: string;
  className?: string;
}) {
  if (value === null || value === undefined) {
    return <span className={cn("tabular-nums text-muted-foreground", className)}>—</span>;
  }
  const isZero = value === 0;
  const color =
    tone === "debt"
      ? "text-destructive"
      : tone === "muted"
        ? "text-muted-foreground"
        : tone === "strong"
          ? "text-ink"
          : isZero
            ? "text-muted-foreground"
            : "text-ink";
  const weight = tone === "strong" ? "font-semibold" : "font-medium";
  const texto = moneda ? formatMoney(value, moneda) : formatARS(value);
  return <span className={cn("tabular-nums", weight, color, className)}>{texto}</span>;
}

/**
 * PrecioUnidad — el precio inline con su unidad. Fuente única del precio en el
 * back-office (combo de equipos, búsquedas, calidad, estudio…), para no repetir
 * `${fmtArs(x)}/jornada` a mano y mantener el término consistente:
 *  - `unidad="jornada"` (default, rental) → "$12.000/jornada"
 *  - `unidad="hora"` (estudio)            → "$8.000/hora"
 *  - `compact` (mobile)                   → "$12.000/j" · "$8.000/h"
 * El término sale de `UNIDADES` (mismo del catálogo público y `unidadLabel`).
 * Para el bloque rico del catálogo público (total del período, plural) usar
 * `PriceBlock`. Si no hay precio, muestra "—".
 */
export function PrecioUnidad({
  value,
  unidad = "jornada",
  compact = false,
  className,
}: {
  value: number | null | undefined;
  unidad?: Unidad;
  /** Mobile: abrevia la unidad ("/j", "/h"). */
  compact?: boolean;
  className?: string;
}) {
  if (value === null || value === undefined) {
    return <span className={cn("text-muted-foreground", className)}>—</span>;
  }
  const suf = compact ? UNIDADES[unidad].abbr : UNIDADES[unidad].singular;
  return (
    <span className={cn("tabular-nums", className)}>
      {formatARS(value)}
      <span className="text-muted-foreground">/{suf}</span>
    </span>
  );
}
