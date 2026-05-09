import { categories, brands, type Category } from "@/data/equipment";
import { cn } from "@/lib/utils";
import { Search, X } from "lucide-react";

export function ListFilters({
  query,
  onQuery,
  selectedCategories,
  onToggleCategory,
  selectedBrand,
  onBrand,
  onClear,
}: {
  query: string;
  onQuery: (v: string) => void;
  selectedCategories: Set<Category>;
  onToggleCategory: (c: Category) => void;
  selectedBrand: string | null;
  onBrand: (b: string | null) => void;
  onClear: () => void;
}) {
  const hasFilters = selectedCategories.size > 0 || !!selectedBrand || !!query.trim();

  return (
    <div className="sticky top-[116px] z-20 border-b hairline bg-background/90 backdrop-blur-xl">
      <div className="flex flex-col gap-3 px-6 py-4 lg:px-12">
        {/* Buscador + marca + clear */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[240px] max-w-2xl">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(e) => onQuery(e.target.value)}
              placeholder="Buscar equipo, marca o categoría…"
              autoFocus
              className="w-full rounded-full border-2 hairline bg-surface py-3 pl-12 pr-4 text-base placeholder:text-muted-foreground focus:border-amber focus:outline-none"
            />
          </div>
          <select
            value={selectedBrand ?? ""}
            onChange={(e) => onBrand(e.target.value || null)}
            className="rounded-md border hairline bg-surface px-3 py-2 text-sm focus:border-amber/40 focus:outline-none"
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
              className="flex items-center gap-1.5 rounded-full border hairline px-3 py-1.5 text-xs uppercase tracking-wider text-muted-foreground hover:border-ink hover:text-ink"
            >
              <X className="h-3 w-3" /> Limpiar
            </button>
          )}
        </div>

        {/* Chips de categorías */}
        <div className="flex flex-wrap gap-1.5">
          {categories.map((c) => {
            const active = selectedCategories.has(c);
            return (
              <button
                key={c}
                onClick={() => onToggleCategory(c)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs transition",
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
