import { cn } from "@/lib/utils";
import { X } from "lucide-react";

/**
 * Controles de filtros compartidos entre el sticky bar desktop (ListFilters)
 * y la tab "Filtros" del DiscoverySheet mobile.
 *
 * Dos layouts:
 * - "inline" — todo en una línea con flex-wrap. Pensado para sticky bar.
 * - "stacked" — secciones verticales con labels. Pensado para sheet mobile.
 *
 * En ambos: misma estética de chip (rounded-full, ink/amber para activo) y
 * mismo select (border hairline + amber focus).
 */
export function FilterControls({
  layout,
  categories,
  brands,
  selectedCategories,
  onToggleCategory,
  selectedBrand,
  onBrand,
  onClear,
  showClear = true,
  showCategories = true,
}: {
  layout: "inline" | "stacked";
  categories: string[];
  brands: { id: number | string; nombre: string }[];
  selectedCategories: Set<string>;
  onToggleCategory: (c: string) => void;
  selectedBrand: string | null;
  onBrand: (b: string | null) => void;
  onClear: () => void;
  showClear?: boolean;
  showCategories?: boolean;
}) {
  const hasFilters = selectedCategories.size > 0 || !!selectedBrand;

  if (layout === "inline") {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <BrandSelect
          brands={brands}
          selectedBrand={selectedBrand}
          onBrand={onBrand}
          className="shrink-0 px-3 py-1.5 text-xs"
        />
        {showCategories &&
          categories.map((c) => (
            <CategoryChip
              key={c}
              label={c}
              active={selectedCategories.has(c)}
              onClick={() => onToggleCategory(c)}
              size="sm"
            />
          ))}
        {showClear && hasFilters && (
          <button
            onClick={onClear}
            className="ml-auto shrink-0 flex items-center gap-1.5 rounded-full border hairline px-3 py-1 text-xs uppercase tracking-wider text-muted-foreground hover:border-ink hover:text-ink"
          >
            <X className="h-3 w-3" /> Limpiar
          </button>
        )}
      </div>
    );
  }

  // stacked
  return (
    <div className="space-y-6">
      <section>
        <div className="mb-2 t-eyebrow">Marca</div>
        <BrandSelect
          brands={brands}
          selectedBrand={selectedBrand}
          onBrand={onBrand}
          className="w-full px-3 py-2 text-sm"
        />
      </section>

      <section>
        <div className="mb-2 t-eyebrow">Categorías</div>
        <div className="flex flex-wrap gap-1.5">
          {categories.map((c) => (
            <CategoryChip
              key={c}
              label={c}
              active={selectedCategories.has(c)}
              onClick={() => onToggleCategory(c)}
              size="md"
            />
          ))}
        </div>
      </section>
    </div>
  );
}

function BrandSelect({
  brands,
  selectedBrand,
  onBrand,
  className,
}: {
  brands: { id: number | string; nombre: string }[];
  selectedBrand: string | null;
  onBrand: (b: string | null) => void;
  className?: string;
}) {
  return (
    <select
      value={selectedBrand ?? ""}
      onChange={(e) => onBrand(e.target.value || null)}
      className={cn(
        "rounded-md border hairline bg-surface focus:border-amber/40 focus:outline-none",
        className,
      )}
    >
      <option value="">Todas las marcas</option>
      {brands.map((b) => (
        // value = nombre (no id) porque el filtro de Index compara con e.brand
        // (string nombre, no id). Si pasáramos id, el filtro nunca matchearía.
        <option key={b.id} value={b.nombre}>
          {b.nombre}
        </option>
      ))}
    </select>
  );
}

function CategoryChip({
  label,
  active,
  onClick,
  size,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  size: "sm" | "md";
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "shrink-0 rounded-full border transition",
        size === "sm" ? "px-3 py-1 text-xs" : "px-3 py-1.5 text-xs",
        active
          ? "border-ink bg-ink text-amber"
          : "hairline text-foreground/70 hover:border-ink hover:text-ink",
      )}
    >
      {label}
    </button>
  );
}
