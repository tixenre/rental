import { useMemo } from "react";
import { type Brand } from "@/types/brand";
import { type Equipment } from "@/data/equipment";
import { CarouselRow } from "./CarouselRow";
import { BrandCard } from "./BrandCard";

/**
 * "Marcas destacadas" — carrusel curado en la home. Muestra hasta TOP_N
 * marcas ordenadas por cantidad de equipos disponibles. Click filtra el
 * catálogo (toggle: re-click deselecciona).
 *
 * Cambio de framing (post audit UX): antes era "Marcas" = todas las marcas.
 * Eso duplicaba el filtro de marca y confundía como navegación.
 * Ahora son destacadas (curadas por count) — funcionan como entrada
 * visual rápida a las marcas más relevantes del catálogo.
 *
 * Para curar manualmente: futuro issue con flag `marcas.destacada: boolean`.
 * Hoy la curación es automática por count.
 */
const TOP_N = 8;

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
  // Pre-calcular count por marca y limitar a TOP_N. Si una marca está
  // seleccionada pero no entra en top N, la forzamos a entrar al inicio
  // para que el visitante no la pierda visualmente al filtrar.
  const destacadas = useMemo(() => {
    const counts = brands.map((b) => ({
      brand: b,
      count: allEquipos.filter((e) => (e.brand as string).toLowerCase() === b.nombre.toLowerCase()).length,
    }));
    counts.sort((a, b) => b.count - a.count);
    const top = counts.slice(0, TOP_N);
    const isSelectedInTop = top.some(
      (x) => !!selectedBrand && x.brand.nombre.toLowerCase() === selectedBrand.toLowerCase(),
    );
    if (!isSelectedInTop && selectedBrand) {
      const sel = counts.find(
        (x) => x.brand.nombre.toLowerCase() === selectedBrand.toLowerCase(),
      );
      if (sel) return [sel, ...top.slice(0, TOP_N - 1)];
    }
    return top;
  }, [brands, allEquipos, selectedBrand]);

  if (destacadas.length === 0) return null;

  return (
    <CarouselRow title="Marcas destacadas" count={destacadas.length}>
      {destacadas.map(({ brand, count }) => {
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
