import { cn } from "@/lib/utils";
import { Plus } from "lucide-react";

type Props = {
  onClick: () => void;
  /** Icon component — defaults to Plus */
  icon?: React.ReactNode;
  /** If provided, renders an extended FAB with text */
  label?: string;
  className?: string;
};

export function FAB({ onClick, icon, label, className }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label ?? "Acción principal"}
      className={cn(
        "fixed right-4 z-40 flex items-center justify-center gap-2",
        "rounded-full bg-ink text-amber shadow-lg transition",
        "active:scale-95 hover:bg-foreground",
        label ? "h-14 px-5 text-sm font-semibold" : "h-14 w-14",
        className,
      )}
      style={{ bottom: "calc(1.5rem + env(safe-area-inset-bottom))" }}
    >
      {icon ?? <Plus className="h-6 w-6" />}
      {label && <span>{label}</span>}
    </button>
  );
}
