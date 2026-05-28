import { formatARS } from "../lib/format";
import { cn } from "./lib/cn";

/**
 * PriceBlock — el bloque "precio + tarifa" usado en cards, rows y fichas.
 *
 * Regla del specimen:
 *   - 1 jornada → mostrar `$ 24.500` + `/ jornada` chico.
 *   - N jornadas → mostrar total grande + `3 J · $ 24.500/J` chico.
 *
 * Layout: número grande en display-font, meta abajo en mono tabular.
 * Alineado a la derecha (right-aligned).
 *
 * @example
 *   <PriceBlock pricePerDay={24500} />                  // $ 24.500 · / jornada
 *   <PriceBlock pricePerDay={24500} jornadas={3} />     // $ 73.500 · 3 J · $ 24.500/J
 *   <PriceBlock pricePerDay={24500} suffix=" + IVA" />  // $ 24.500 · / jornada + IVA
 */
export function PriceBlock({
  pricePerDay,
  jornadas = 1,
  suffix,
  className,
  align = "right",
}: {
  pricePerDay: number;
  jornadas?: number;
  /** Texto opcional al lado de "/ jornada" (ej: " + IVA"). */
  suffix?: string;
  className?: string;
  align?: "left" | "right";
}) {
  const showTotal = jornadas > 1;
  const total = pricePerDay * jornadas;

  return (
    <div
      className={cn(
        "tabular",
        align === "right" ? "text-right" : "text-left",
        className,
      )}
    >
      <div className="font-display text-lg font-black leading-none text-ink">
        {showTotal ? formatARS(total) : formatARS(pricePerDay)}
      </div>
      <div className="mt-0.5 font-mono text-[9px] uppercase tracking-wide text-muted-foreground">
        {showTotal ? (
          <>
            {jornadas} J · <span className="font-semibold text-ink/70">{formatARS(pricePerDay)}/J</span>
          </>
        ) : (
          <>/ jornada{suffix}</>
        )}
      </div>
    </div>
  );
}
