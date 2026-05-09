import { cn } from "@/lib/utils";
import { X } from "lucide-react";

export function ListFilters({
  query,
  categories,
  brands,
  selectedCategories,
  onToggleCategory,
  selectedBrand,
  onBrand,
  onClear,
}: {
  query: string;
  onQuery: (v: string) => void;
  categories: string[];
  brands: string[];
  selectedCategories: Set<string>;
  onToggleCategory: (c: string) => void;
  selectedBrand: string | null;
  onBrand: (b: string | null) => void;
  onClear: () => void;
}) {
  const hasFilters = selectedCategories.size > 0 || !!selectedBrand || !!query.trim();

  return (
    <div className="sticky top-[180px] sm:top-[124px] z-20 border-b hairline bg-background/90 backdrop-blur-xl">
      <div className="flex flex-col gap-3 px-4 py-3 lg:px-12">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedBrand ?? ""}
            onChange={(e) => onBrand(e.target.value || null)}
            className="rounded-md border hairline bg-surface px-3 py-1.5 text-xs focus:border-amber/40 focus:outline-none"
          >
            <option value="">Todas las marcas</option>
            {brands.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
          {hasFilters && (
            <button
              onClick={onClear}
              className="flex items-center gap-1.5 rounded-full border hairline px-3 py-1 text-xs uppercase tracking-wider text-muted-foreground hover:border-ink hover:text-ink"
            >
              <X className="h-3 w-3" /> Limpiar
            </button>
          )}
        </div>

        {/* Chips de categorías — scroll horizontal en mobile */}
        <div className="-mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 lg:mx-0 lg:flex-wrap lg:px-0 lg:overflow-visible lg:pb-0">
          {categories.map((c) => {
            const active = selectedCategories.has(c);
            return (
              <button
                key={c}
                onClick={() => onToggleCategory(c)}
                className={cn(
                  "shrink-0 rounded-full border px-3 py-1 text-xs transition",
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
      </div>
    </div>
  );
}
