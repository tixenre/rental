import { fmtArs } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Monto — presentación única de plata en el back-office.
 *
 * Materializa la jerarquía de plata de la Filosofía de diseño: los montos
 * relevantes anclan en `text-ink font-medium tabular-nums`; el cero / vacío van
 * en muted (no compiten); una deuda va en destructive. Siempre por `fmtArs`.
 * Reemplaza los montos sueltos en muted/text-2xs y el formateo ad-hoc.
 */
export function Monto({
  value,
  tone = "auto",
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
  return <span className={cn("tabular-nums", weight, color, className)}>{fmtArs(value)}</span>;
}
