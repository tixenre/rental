import { ChevronRight, X } from "lucide-react";
import { Button } from "@/design-system/ui/button";
import { BottomSheet } from "@/components/mobile/BottomSheet";
import { cn } from "@/lib/utils";

/* ── FiltrosSheet ────────────────────────────────────────────────── */
export function FiltrosSheet({
  open,
  onOpenChange,
  stockOnly,
  onStockToggle,
  selectedBrand,
  onBrandClear,
  onOpenBrandSheet,
  activeFiltersCount,
  onClearAll,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  stockOnly: boolean;
  onStockToggle: () => void;
  selectedBrand: string | null;
  onBrandClear: () => void;
  onOpenBrandSheet: () => void;
  activeFiltersCount: number;
  onClearAll: () => void;
}) {
  return (
    <BottomSheet
      open={open}
      onOpenChange={onOpenChange}
      title="Filtros"
      showClose
      footer={
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            shape="pill"
            onClick={onClearAll}
            disabled={activeFiltersCount === 0}
            className="flex-1 h-auto py-3 font-sans text-sm font-semibold"
          >
            Limpiar
          </Button>
          <Button
            type="button"
            variant="primary"
            shape="pill"
            onClick={() => onOpenChange(false)}
            className="flex-1 h-auto py-3 font-sans text-sm font-bold"
          >
            Aplicar
          </Button>
        </div>
      }
    >
      <div className="px-4 py-3 space-y-3">
        {/* Disponibles toggle */}
        <div className="rounded-lg border border-hairline px-3.5 py-3 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="font-sans text-sm font-semibold text-ink">Disponibles</div>
            <div className="font-mono text-2xs text-muted-foreground mt-0.5">
              Esconder equipos sin stock para tus fechas
            </div>
          </div>
          <button
            type="button"
            onClick={onStockToggle}
            role="switch"
            aria-checked={stockOnly}
            className={cn(
              "relative h-6 w-11 rounded-full transition shrink-0",
              stockOnly ? "bg-amber" : "bg-muted",
            )}
          >
            <span
              className={cn(
                "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
                stockOnly && "translate-x-5",
              )}
            />
          </button>
        </div>

        {/* Marca selector */}
        <button
          type="button"
          onClick={onOpenBrandSheet}
          className="w-full rounded-lg border border-hairline px-3.5 py-3 flex items-center justify-between gap-3 hover:bg-muted transition text-left"
        >
          <div className="min-w-0">
            <div className="font-sans text-sm font-semibold text-ink">Marca</div>
            <div className="font-mono text-2xs text-muted-foreground mt-0.5 truncate">
              {selectedBrand ?? "Todas"}
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {selectedBrand && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onBrandClear();
                }}
                className="grid h-6 w-6 place-items-center rounded-full bg-muted text-muted-foreground hover:bg-ink/10 hover:text-ink"
                aria-label="Limpiar marca"
              >
                <X className="h-3 w-3" />
              </button>
            )}
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </div>
        </button>
      </div>
    </BottomSheet>
  );
}
