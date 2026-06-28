import { formatARS, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Familia de componentes de plata del back-office — una sola forma por TIPO de
 * plata (no un solo componente para todo). Cada uno encapsula su formato + jerarquía:
 *  - <Monto>          monto suelto (ARS por defecto; `moneda` para USD/otras).
 *  - <PrecioJornada>  el precio de alquiler con su unidad ("$X/jornada").
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
 * PrecioJornada — el precio de alquiler con su unidad: "$12.000/jornada". Fuente
 * única del precio inline en el back-office (combo de equipos, búsquedas, calidad…),
 * para no repetir `${fmtArs(x)}/jornada` a mano. Usa "jornada" (el término del
 * negocio, igual que el catálogo público y `jornadaLabel`), NO "/día". El catálogo
 * público usa `PriceBlock`, más rico. Si no hay precio, muestra "—".
 */
export function PrecioJornada({
  value,
  className,
}: {
  value: number | null | undefined;
  className?: string;
}) {
  if (value === null || value === undefined) {
    return <span className={cn("text-muted-foreground", className)}>—</span>;
  }
  return (
    <span className={cn("tabular-nums", className)}>
      {formatARS(value)}
      <span className="text-muted-foreground">/jornada</span>
    </span>
  );
}
