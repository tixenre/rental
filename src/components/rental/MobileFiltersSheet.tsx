import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { X } from "lucide-react";
import { FilterControls } from "./FilterControls";

/**
 * Bottom sheet de filtros para mobile. Solo el wrapper visual (header con
 * contador + footer con CTA "Ver N resultados"). Los controles de
 * marca/categorías/limpiar viven en `<FilterControls />` compartido con
 * `<ListFilters />`.
 */
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
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  categories: string[];
  brands: { id: number | string; nombre: string }[];
  selectedCategories: Set<string>;
  onToggleCategory: (c: string) => void;
  selectedBrand: string | null;
  onBrand: (b: string | null) => void;
  onClear: () => void;
  resultCount: number;
}) {
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

        <div className="px-4 py-5 pb-8">
          <FilterControls
            layout="stacked"
            categories={categories}
            brands={brands}
            selectedCategories={selectedCategories}
            onToggleCategory={onToggleCategory}
            selectedBrand={selectedBrand}
            onBrand={onBrand}
            onClear={onClear}
            showClear={false}
          />
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
