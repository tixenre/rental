import { cn } from "@/lib/utils";
import { formatARS } from "@/lib/format";

export function AdminCard({
  children,
  onClick,
  className,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "w-full card p-3 space-y-2 transition",
        onClick && "cursor-pointer active:bg-muted",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function AdminCardHeader({
  label,
  title,
  subtitle,
  badge,
}: {
  label?: string;
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-2">
      <div className="min-w-0 flex-1">
        {label && (
          <div className="mb-0.5 font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
            {label}
          </div>
        )}
        <div className="truncate font-medium text-ink">{title}</div>
        {subtitle && <div className="truncate text-xs text-muted-foreground">{subtitle}</div>}
      </div>
      {badge && <div className="shrink-0">{badge}</div>}
    </div>
  );
}

export function AdminCardMeta({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("text-sm text-muted-foreground", className)}>{children}</div>;
}

export function AdminCardFooter({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center justify-between gap-2 pt-0.5", className)}>
      {children}
    </div>
  );
}

export function AdminCardPrice({ total, saldo }: { total: number; saldo?: number | null }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="font-semibold tabular text-ink">{formatARS(total)}</span>
      {saldo != null && saldo > 0 && (
        <span className="text-xs tabular text-destructive">saldo {formatARS(saldo)}</span>
      )}
    </div>
  );
}

export function AdminCardActions({ children }: { children: React.ReactNode }) {
  return <div className="flex items-center gap-1">{children}</div>;
}
