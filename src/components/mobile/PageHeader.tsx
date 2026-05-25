import { cn } from "@/lib/utils";
import { ArrowLeft } from "lucide-react";

type Props = {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  /** Right-side action (button, icon, etc.) */
  action?: React.ReactNode;
  className?: string;
};

export function PageHeader({ title, subtitle, onBack, action, className }: Props) {
  return (
    <div
      className={cn(
        "sticky top-0 z-10 flex items-center gap-2 border-b hairline bg-background/95 px-3 backdrop-blur-xl",
        className,
      )}
      style={{
        paddingTop: "calc(0.625rem + env(safe-area-inset-top))",
        paddingBottom: "0.625rem",
      }}
    >
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          aria-label="Volver"
          className="grid h-10 w-10 shrink-0 place-items-center rounded-full transition hover:bg-muted active:bg-muted"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
      )}

      <div className="min-w-0 flex-1">
        <h1 className="truncate font-display text-lg leading-tight">{title}</h1>
        {subtitle && <p className="truncate text-xs text-muted-foreground">{subtitle}</p>}
      </div>

      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
