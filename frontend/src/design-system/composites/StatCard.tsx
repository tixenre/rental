import { type ComponentType } from "react";
import { cn } from "@/lib/utils";

type StatCardTone = "default" | "warn" | "destructive";

type StatCardProps = {
  label: string;
  value: string | number;
  meta?: string;
  icon?: ComponentType<{ className?: string }>;
  tone?: StatCardTone;
  /** "lg" (default) = KPI de dashboard, valor grande. "md" = tile compacto
   *  (dentro de un dialog/modal, varios por fila). */
  size?: "md" | "lg";
  className?: string;
  valueClassName?: string;
};

const TONE_CONTAINER: Record<StatCardTone, string> = {
  default: "hairline bg-surface",
  warn: "border-amber/50 bg-amber/10",
  destructive: "border-destructive/30 bg-destructive/10",
};

const TONE_ICON: Record<StatCardTone, string> = {
  default: "",
  warn: "",
  destructive: "text-destructive",
};

/**
 * StatCard — composite único de label + valor grande + meta opcional, para
 * KPIs de dashboards admin y del portal cliente.
 *
 * Consolida las 8 variantes locales que habían aparecido en el repo
 * (rental/StatCard, media.lazy, admin/index.lazy, LiquidacionReporte::Kpi,
 * EquiposTableHelpers::KpiCard, MantenimientoEquipoDialog, HistorialEquipoDialog,
 * DashboardUsoDialog) con formas ligeramente distintas de lo mismo.
 */
export function StatCard({
  label,
  value,
  meta,
  icon: Icon,
  tone = "default",
  size = "lg",
  className,
  valueClassName,
}: StatCardProps) {
  const lg = size === "lg";
  return (
    <div
      className={cn("rounded-lg border", TONE_CONTAINER[tone], lg ? "px-4 py-3" : "p-3", className)}
    >
      <div className="flex items-center gap-1.5 font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
        {Icon && <Icon className={cn("h-3.5 w-3.5 shrink-0", TONE_ICON[tone])} />}
        <span className="truncate">{label}</span>
      </div>
      <div
        className={cn(
          "mt-1.5 font-display text-ink tabular-nums leading-none",
          lg ? "text-3xl font-black tracking-[-0.01em]" : "text-xl font-bold",
          valueClassName,
        )}
      >
        {value}
      </div>
      {meta && <div className="mt-1 font-mono text-2xs text-muted-foreground">{meta}</div>}
    </div>
  );
}
