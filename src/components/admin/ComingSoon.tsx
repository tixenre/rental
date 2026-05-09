import { Construction } from "lucide-react";

export function ComingSoon({
  title,
  description,
  phase,
}: {
  title: string;
  description: string;
  phase?: string;
}) {
  return (
    <div className="px-4 md:px-8 py-6 md:py-10 max-w-3xl mx-auto">
      <div className="mb-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl md:text-4xl text-ink">{title}</h1>
      </div>

      <div className="rounded-xl border hairline bg-surface px-6 py-10 text-center space-y-4">
        <div className="mx-auto h-12 w-12 grid place-items-center rounded-full bg-accent/40">
          <Construction className="h-5 w-5 text-ink" />
        </div>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            En construcción {phase ? `· ${phase}` : ""}
          </div>
          <h2 className="font-display text-xl text-ink mt-1">Próximamente</h2>
        </div>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">{description}</p>
        <p className="text-xs text-muted-foreground">
          Mientras tanto seguí usando el back-office viejo desde el sidebar.
        </p>
      </div>
    </div>
  );
}
