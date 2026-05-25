import { Check, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export function PhotoGrid({
  candidates,
  selected,
  onSelect,
  onBuscarMas,
  searching,
  loadingUrl,
}: {
  candidates: string[];
  selected: string;
  onSelect: (u: string) => void;
  onBuscarMas: () => void;
  searching: boolean;
  loadingUrl?: string;
}) {
  if (candidates.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-muted-foreground">
        Sin resultados. Probá con otra búsqueda o cargá una URL manual.
        <div className="mt-3">
          <Button variant="outline" size="sm" onClick={onBuscarMas} disabled={searching}>
            {searching ? (
              <>
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                Buscando…
              </>
            ) : (
              "Buscar más"
            )}
          </Button>
        </div>
      </div>
    );
  }
  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
          {candidates.length} fotos — tocá para elegir
        </span>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 text-xs"
          onClick={onBuscarMas}
          disabled={searching}
        >
          {searching ? (
            <>
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              Buscando…
            </>
          ) : (
            <>
              <Sparkles className="h-3 w-3 mr-1 text-amber" />
              Buscar más
            </>
          )}
        </Button>
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
        {candidates.map((u) => {
          const isSelected = u === selected;
          const isLoading = u === loadingUrl;
          return (
            <button
              type="button"
              key={u}
              onClick={() => !isLoading && onSelect(u)}
              title={u}
              disabled={isLoading}
              className={`relative aspect-square overflow-hidden rounded-lg border-2 transition ${
                isSelected
                  ? "border-amber ring-2 ring-amber/30"
                  : "border-transparent hover:border-muted-foreground/30"
              }`}
            >
              <img
                src={u}
                alt=""
                className="h-full w-full object-contain bg-white"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.opacity = "0.2";
                }}
              />
              {isLoading && (
                <div className="absolute inset-0 grid place-items-center bg-background/70">
                  <Loader2 className="h-5 w-5 animate-spin text-ink" />
                </div>
              )}
              {isSelected && !isLoading && (
                <span className="absolute right-1 top-1 rounded-full bg-amber p-0.5">
                  <Check className="h-3 w-3 text-ink" />
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
