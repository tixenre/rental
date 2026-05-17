import { cn } from "@/lib/utils";

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
    <div className={cn("rounded-lg border hairline bg-surface px-4 py-3", className)}>
      <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </div>
      <div className={cn("mt-1.5 font-display text-2xl font-black leading-none tabular-nums text-ink", valueClassName)}>
        {value}
      </div>
      {meta && (
        <div className="mt-1 font-mono text-[10px] text-muted-foreground">{meta}</div>
      )}
    </div>
  );
}
