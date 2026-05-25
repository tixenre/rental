import { Bug, Check, Loader2, X } from "lucide-react";
import { type DiagStep } from "./types";

export function PhotoDiag({ steps }: { steps: DiagStep[] }) {
  return (
    <div className="rounded-md border hairline bg-muted/30 p-3 text-xs">
      <div className="flex items-center gap-1.5 mb-2 font-mono uppercase tracking-wide text-muted-foreground">
        <Bug className="h-3.5 w-3.5" /> Subida de foto
      </div>
      <ul className="space-y-1">
        {steps.map((s, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className="mt-0.5">
              {s.status === "ok" && <Check className="h-3.5 w-3.5 text-emerald-600" />}
              {s.status === "fail" && <X className="h-3.5 w-3.5 text-destructive" />}
              {s.status === "pending" && (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
              )}
              {s.status === "skip" && <span className="block h-3.5 w-3.5 rounded-full border" />}
            </span>
            <div className="flex-1 min-w-0">
              <div className={s.status === "fail" ? "text-destructive font-medium" : ""}>
                {s.label}
              </div>
              {s.detail && (
                <div className="text-[10px] text-muted-foreground break-all">{s.detail}</div>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
