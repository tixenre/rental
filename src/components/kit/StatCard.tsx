import { cn } from "@/lib/utils";

/**
 * StatCard — el bloque de número grande usado en el dashboard admin.
 *
 * Source: `docs/design-kit/kit/components/stat-card.tsx`. Sin sombra, con
 * hairline. La grilla del admin las pone en filas de 3–4.
 *
 *   ┌────────────────────────┐
 *   │ EYEBROW MONO           │  ← label
 *   │ 1.247                  │  ← value, display chunky tabular
 *   │ ↑ 12% vs. mes anterior │  ← meta, opcional
 *   └────────────────────────┘
 */
export function StatCard({
  label,
  value,
  meta,
  className,
  valueClassName,
}: {
  label: string;
  value: string;
  meta?: string;
  className?: string;
  valueClassName?: string;
}) {
  return (
    <div className={cn("rounded-lg border border-hairline bg-surface px-4 py-3", className)}>
      <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </div>
      <div
        className={cn(
          "mt-1.5 font-display text-2xl font-black leading-none tabular text-ink",
          valueClassName,
        )}
      >
        {value}
      </div>
      {meta && <div className="mt-1 font-mono text-[10px] text-muted-foreground">{meta}</div>}
    </div>
  );
}
