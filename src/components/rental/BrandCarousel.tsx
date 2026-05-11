import { type Brand } from "@/types/brand";
import { type Equipment } from "@/data/equipment";
import { CarouselRow } from "./CarouselRow";
import { BrandCard } from "./BrandCard";

/**
 * Carrusel de marcas en la home. Click filtra el catálogo por la marca
 * seleccionada (toggle: re-click deselecciona).
 *
 * Antes el callback pasaba `brand.id` (number) pero el filtro de Index
 * compara con `e.brand` que es el NOMBRE (string) — nunca matcheaba.
 * Ahora pasa el nombre, que es lo que el filtro espera.
 */
export function BrandCarousel({
  brands,
  allEquipos,
  selectedBrand,
  onBrandSelect,
}: {
  brands: Brand[];
  allEquipos: Equipment[];
  /** El nombre de la marca seleccionada, o null. */
  selectedBrand?: string | null;
  /** Recibe el nombre de la marca (no el id) — toggle: null deselecciona. */
  onBrandSelect: (brandName: string | null) => void;
}) {
  return (
    <CarouselRow title="Marcas" count={brands.length}>
      {brands.map((brand) => {
        const count = allEquipos.filter(
          (e) => (e.brand as string).toLowerCase() === brand.nombre.toLowerCase()
        ).length;
        const isSelected =
          !!selectedBrand && selectedBrand.toLowerCase() === brand.nombre.toLowerCase();

        return (
          <div key={brand.id} style={{ flexShrink: 0 }}>
            <BrandCard
              brand={brand}
              count={count}
              isSelected={isSelected}
              onClick={() =>
                // Toggle: si ya está seleccionada, deseleccionar.
                onBrandSelect(isSelected ? null : brand.nombre)
              }
            />
          </div>
        );
      })}
    </CarouselRow>
  );
}
