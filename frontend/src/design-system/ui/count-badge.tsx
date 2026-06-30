import * as React from "react";
import { cn } from "@/lib/utils";

export interface CountBadgeProps {
  count: number;
  /** "sm" = h-4 w-4 (text-3xs). "md" = h-5 w-5 (text-xs). */
  size?: "sm" | "md";
  className?: string;
}

export function CountBadge({ count, size = "sm", className }: CountBadgeProps) {
  if (count <= 0) return null;
  return (
    <span
      className={cn(
        "inline-grid place-items-center rounded-full bg-ink px-1 font-bold tabular-nums text-amber",
        size === "sm" ? "h-4 min-w-4 text-3xs" : "h-5 min-w-5 text-xs",
        className,
      )}
      aria-label={`${count}`}
    >
      {count > 99 ? "99+" : count}
    </span>
  );
}
