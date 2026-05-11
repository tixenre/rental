import { type Brand } from "@/types/brand";
import { CarouselRow } from "./CarouselRow";
import { BrandCard } from "./BrandCard";

export function BrandCarousel({
  brands,
  allEquipos,
  selectedBrand,
  onBrandSelect,
}: {
  brands: Brand[];
  allEquipos: any[];
  selectedBrand?: string | null;
  onBrandSelect: (brandId: number) => void;
}) {
  return (
    <CarouselRow title="Marcas" count={brands.length}>
      {brands.map((brand) => {
        // e.brand es un string (nombre de marca) en el tipo Equipment
        const count = allEquipos.filter(
          (e) => (e.brand as string).toLowerCase() === brand.nombre.toLowerCase()
        ).length;
        const isSelected = selectedBrand ? parseInt(selectedBrand) === brand.id : false;

        return (
          <div key={brand.id} style={{ flexShrink: 0 }}>
            <BrandCard
              brand={brand}
              count={count}
              isSelected={isSelected}
              onClick={() => onBrandSelect(brand.id)}
            />
          </div>
        );
      })}
    </CarouselRow>
  );
}
