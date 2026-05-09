import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  categories: string[];
  brands: string[];
  selectedCategories: Set<string>;
  onToggleCategory: (c: string) => void;
  selectedBrand: string | null;
  onBrand: (b: string | null) => void;
  onClear: () => void;
  resultCount: number;
};

export function MobileFiltersSheet({
  open,
  onOpenChange,
  categories,
  brands,
  selectedCategories,
  onToggleCategory,
  selectedBrand,
  onBrand,
  onClear,
  resultCount,
}: Props) {
  const activeCount = selectedCategories.size + (selectedBrand ? 1 : 0);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="max-h-[85vh] overflow-y-auto rounded-t-2xl p-0"
      >
        <SheetHeader className="sticky top-0 z-10 border-b hairline bg-background/95 px-4 py-3 text-left backdrop-blur-xl">
          <div className="flex items-center justify-between">
            <SheetTitle className="font-display text-lg">Filtros</SheetTitle>
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground tabular">
              {resultCount} resultados
              {activeCount > 0 && ` · ${activeCount} activo${activeCount === 1 ? "" : "s"}`}
            </span>
          </div>
        </SheetHeader>

        <div className="space-y-6 px-4 py-5 pb-8">
          {/* Marca */}
          <section>
            <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Marca
            </div>
            <select
              value={selectedBrand ?? ""}
              onChange={(e) => onBrand(e.target.value || null)}
              className="w-full rounded-md border hairline bg-surface px-3 py-2 text-sm focus:border-amber/40 focus:outline-none"
            >
              <option value="">Todas las marcas</option>
              {brands.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </section>

          {/* Categorías */}
          <section>
            <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Categorías
            </div>
            <div className="flex flex-wrap gap-1.5">
              {categories.map((c) => {
                const active = selectedCategories.has(c);
                return (
                  <button
                    key={c}
                    onClick={() => onToggleCategory(c)}
                    className={cn(
                      "rounded-full border px-3 py-1.5 text-xs transition",
                      active
                        ? "border-ink bg-ink text-amber"
                        : "hairline text-foreground/70 hover:border-ink hover:text-ink",
                    )}
                  >
                    {c}
                  </button>
                );
              })}
            </div>
          </section>
        </div>

        {/* Footer acciones */}
        <div
          className="sticky bottom-0 z-10 flex items-center gap-2 border-t hairline bg-background/95 px-4 py-3 backdrop-blur-xl"
          style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}
        >
          {activeCount > 0 && (
            <button
              onClick={onClear}
              className="flex items-center gap-1.5 rounded-full border hairline px-4 py-2 text-xs uppercase tracking-wider text-muted-foreground hover:border-ink hover:text-ink"
            >
              <X className="h-3 w-3" /> Limpiar
            </button>
          )}
          <button
            onClick={() => onOpenChange(false)}
            className="ml-auto flex-1 rounded-full bg-ink px-4 py-2.5 text-sm font-semibold text-amber hover:bg-foreground"
          >
            Ver {resultCount} resultados
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
