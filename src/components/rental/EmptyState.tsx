import { type ReactNode } from "react";
import { cn } from "@/lib/utils";

export function EmptyState({
  icon,
  title,
  sub,
  className,
  children,
}: {
  icon: ReactNode;
  title: string;
  sub?: string;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-4 py-12 text-center", className)}>
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-amber/15 text-amber">
        {icon}
      </div>
      <div>
        <div className="font-display text-xl font-black text-ink">{title}</div>
        {sub && <p className="mt-1 max-w-xs text-sm text-muted-foreground">{sub}</p>}
      </div>
      {children}
    </div>
  );
}
