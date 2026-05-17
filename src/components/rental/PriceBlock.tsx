import { formatARS } from "@/lib/format";
import { cn } from "@/lib/utils";

export function PriceBlock({
  pricePerDay,
  jornadas = 1,
  className,
}: {
  pricePerDay: number;
  jornadas?: number;
  className?: string;
}) {
  const showTotal = jornadas > 1;
  const total = pricePerDay * jornadas;

  return (
    <div className={cn("tabular-nums", className)}>
      <div className="font-display text-lg font-black leading-none text-ink">
        {showTotal ? formatARS(total) : formatARS(pricePerDay)}
      </div>
      <div className="mt-0.5 font-mono text-[9px] uppercase tracking-wide text-muted-foreground">
        {showTotal
          ? `${formatARS(pricePerDay)} × ${jornadas} jorn.`
          : "/ jornada"}
      </div>
    </div>
  );
}
