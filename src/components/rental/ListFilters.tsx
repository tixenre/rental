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
  brands: any[];
  selectedCategories: Set<string>;
  onToggleCategory: (c: string) => void;
  selectedBrand: string | null;
  onBrand: (b: string | null) => void;
  onClear: () => void;
}) {
  const cats = categories ?? [];
  const brandList = brands ?? [];
  const hasFilters = selectedCategories.size > 0 || !!selectedBrand || !!query.trim();

  return (
    <div className="hidden md:block sticky top-[124px] z-20 border-b hairline bg-background/90 backdrop-blur-xl">
      {/* Una sola línea: marca + categorías + limpiar, con flex-wrap si no entra. */}
      <div className="flex flex-wrap items-center gap-2 px-4 py-3 lg:px-12">
        <select
          value={selectedBrand ?? ""}
          onChange={(e) => onBrand(e.target.value || null)}
          className="shrink-0 rounded-md border hairline bg-surface px-3 py-1.5 text-xs focus:border-amber/40 focus:outline-none"
        >
          <option value="">Todas las marcas</option>
          {brandList.map((b) => (
            <option key={b.id} value={b.nombre}>
              {b.nombre}
            </option>
          ))}
        </select>

        {cats.map((c) => {
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

        {hasFilters && (
          <button
            onClick={onClear}
            className="ml-auto shrink-0 flex items-center gap-1.5 rounded-full border hairline px-3 py-1 text-xs uppercase tracking-wider text-muted-foreground hover:border-ink hover:text-ink"
          >
            <X className="h-3 w-3" /> Limpiar
          </button>
        )}
      </div>
    </div>
  );
}
