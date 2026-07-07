/**
 * nav.tsx — ítems de navegación del portal cliente: sidebar (desktop) y
 * bottom-nav (mobile). Extraído de ClientePortalHelpers.tsx.
 */
import { cn } from "@/lib/utils";

// ── Navegación: sidebar item ──────────────────────────────────────────────────

export function SidebarNavItem({
  icon,
  label,
  count,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  count?: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-2.5 rounded-md px-3 py-2.5 font-sans text-sm font-medium transition text-left",
        active
          ? "bg-amber-soft text-ink font-semibold"
          : "text-muted-foreground hover:text-ink hover:bg-surface",
      )}
    >
      <span className={cn("shrink-0", active ? "text-ink" : "text-muted-foreground")}>{icon}</span>
      <span className="flex-1">{label}</span>
      {count != null && count > 0 && (
        <span
          className={cn(
            "font-mono text-2xs tabular-nums rounded-full px-1.5 py-px",
            active ? "bg-amber text-ink" : "bg-muted text-muted-foreground",
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
}

// ── Navegación: bottom nav item ───────────────────────────────────────────────

export function BottomNavItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-col items-center justify-center gap-1 py-2.5 min-h-[56px] transition",
        active ? "text-ink" : "text-muted-foreground",
      )}
    >
      <span className={cn("transition", active && "text-ink")}>{icon}</span>
      <span
        className={cn(
          "font-mono text-2xs uppercase tracking-[0.12em] transition",
          active ? "text-ink font-semibold" : "text-muted-foreground",
        )}
      >
        {label}
      </span>
      {active && (
        <span className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-amber rounded-b" />
      )}
    </button>
  );
}
