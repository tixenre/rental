import { FilterControls } from "./FilterControls";

/**
 * Sticky bar de filtros para desktop modo lista. Solo el wrapper visual —
 * los controles de marca/categorías/limpiar viven en `<FilterControls />`
 * compartido con el `<DiscoverySheet />` mobile.
 *
 * Se renderiza solo en `md+` (en mobile, `MobileStickyBar` abre el discovery sheet).
 */
export function ListFilters({
  categories,
  brands,
  selectedCategories,
  onToggleCategory,
  selectedBrand,
  onBrand,
  onClear,
}: {
  categories: string[];
  brands: { id: number | string; nombre: string }[];
  selectedCategories: Set<string>;
  onToggleCategory: (c: string) => void;
  selectedBrand: string | null;
  onBrand: (b: string | null) => void;
  onClear: () => void;
}) {
  return (
    <div className="hidden md:block sticky top-[124px] z-20 border-b hairline bg-background/90 backdrop-blur-xl">
      <div className="px-4 py-3 lg:px-12">
        <FilterControls
          layout="inline"
          categories={categories}
          brands={brands}
          selectedCategories={selectedCategories}
          onToggleCategory={onToggleCategory}
          selectedBrand={selectedBrand}
          onBrand={onBrand}
          onClear={onClear}
        />
      </div>
    </div>
  );
}
