import { useMemo } from "react";
import { ArrowRight } from "lucide-react";
import { CategoryMosaic } from "@/components/rental/CategoryMosaic";
import { BrandCarousel } from "@/components/rental/BrandCarousel";
import { EquipmentCard } from "@/components/rental/EquipmentCard";
import { CarouselRow } from "@/components/rental/CarouselRow";
import { type Equipment } from "@/data/equipment";
import type { BackendMarca } from "@/lib/api";
import { SearchEmptyState } from "./SearchEmptyState";

export function GridMode({
  allEquipos,
  filtered,
  apiCategories,
  rootApiCategories,
  rootSubtrees,
  marcas,
  selectedBrand,
  onBrandSelect,
  onJumpToCategory,
  selectedCats,
  onClearCats,
  query,
  getDisponible,
  onSuggestCategory,
}: {
  allEquipos: Equipment[];
  filtered: Equipment[];
  apiCategories: string[];
  rootApiCategories: string[];
  rootSubtrees: Map<string, Set<string>>;
  marcas: BackendMarca[];
  selectedBrand?: string | null;
  onBrandSelect: (brandName: string | null) => void;
  onJumpToCategory: (c: string) => void;
  selectedCats: Set<string>;
  onClearCats: () => void;
  query: string;
  getDisponible: (item: Equipment) => number | undefined;
  onSuggestCategory: (c: string) => void;
}) {
  // Los filtros NO se re-implementan acá: el Grid consume `filtered` — el
  // MISMO resultado canónico (motor filtrarOrdenar + marca/disponibles/
  // favoritos/specs) que usa la Lista. Con búsqueda activa se muestra plano
  // y rankeado; en browse, las secciones se gatean por pertenencia.
  const matchIds = useMemo(() => new Set(filtered.map((e) => e.id)), [filtered]);

  const isFiltered = selectedCats.size > 0 || !!selectedBrand;
  const isSearching = query.trim().length > 0;
  // En browse mode mostramos solo categorías raíz. Al filtrar se usa la
  // selección directa (puede ser raíz o sub-cat).
  const visibleCategories = selectedCats.size > 0 ? Array.from(selectedCats) : rootApiCategories;

  // inCategory: matchea equipo contra una categoría. Si la categoría es raíz
  // (tiene subárbol) incluye todos los equipos de sus descendientes — tanto
  // por el M2M `categorias` como por la categoría primaria/inferida
  // (`e.category`), que es lo único que tiene un equipo sin categoría
  // asignada en el admin. Si es una sub-cat seleccionada directamente,
  // matcheo exacto.
  const inCategory = (e: Equipment, c: string) => {
    const subtree = rootSubtrees.get(c);
    if (subtree) {
      return subtree.has(e.category) || (e.categorias ?? []).some((cc) => subtree.has(cc.nombre));
    }
    return e.category === c || (e.categorias ?? []).some((cc) => cc.nombre === c);
  };

  // Secciones por categoría + bucket "Otros": todo equipo que pasa los
  // filtros aparece en ALGUNA sección. Los que no caen en ninguna categoría
  // visible (sin categoría asignada en el admin, #859) van a "Otros" en vez
  // de desaparecer del Grid en silencio.
  // NO re-sortear: allEquipos viene del backend ordenado por relevancia_manual
  // ASC, popularidad_score DESC, nombre ASC; el filter preserva ese ranking.
  const secciones = visibleCategories.map((c) => ({
    cat: c,
    items: allEquipos.filter((e) => inCategory(e, c) && matchIds.has(e.id)),
    real: true,
  }));
  const enSeccion = new Set(secciones.flatMap((s) => s.items.map((e) => e.id)));
  const huerfanos = filtered.filter((e) => !enSeccion.has(e.id));
  if (huerfanos.length > 0) {
    secciones.push({ cat: "Otros", items: huerfanos, real: false });
  }

  // Ancho fijo de cards en carrusel para snap consistente
  const cardW = 260;

  return (
    <div className="space-y-10 pt-2 pb-6 sm:space-y-12 sm:pt-3 sm:pb-8 lg:pt-4 lg:pb-12">
      {isFiltered && (
        <div className="px-4 lg:px-12">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
              Filtrando por
            </span>
            {selectedBrand && (
              <button
                onClick={() => onBrandSelect(null)}
                className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3 py-1 text-xs text-[var(--area-accent)] hover:opacity-90"
                aria-label={`Quitar filtro ${selectedBrand}`}
              >
                {selectedBrand} ×
              </button>
            )}
            {[...selectedCats].map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3 py-1 text-xs text-[var(--area-accent)]"
              >
                {c}
              </span>
            ))}
            <button
              onClick={() => {
                onClearCats();
                onBrandSelect(null);
              }}
              className="ml-1 rounded-full border hairline px-3 py-1 text-xs text-muted-foreground hover:border-ink hover:text-ink"
            >
              Ver todo
            </button>
          </div>
        </div>
      )}

      {!isFiltered && !isSearching && (
        <CategoryMosaic
          allEquipos={allEquipos}
          categories={rootApiCategories}
          onSelect={onJumpToCategory}
          getCount={(c) => allEquipos.filter((e) => inCategory(e, c)).length}
        />
      )}

      {!isFiltered && !isSearching && marcas.length > 0 && (
        <div className="hidden sm:block">
          <BrandCarousel
            brands={marcas}
            allEquipos={allEquipos}
            selectedBrand={selectedBrand}
            onBrandSelect={onBrandSelect}
          />
        </div>
      )}

      {isSearching ? (
        filtered.length === 0 ? (
          <SearchEmptyState
            query={query}
            categories={apiCategories.slice(0, 6)}
            onSuggestCategory={onSuggestCategory}
          />
        ) : (
          <section className="px-4 lg:px-12">
            <div className="mb-4 flex items-end justify-between gap-3">
              <h2 className="font-display text-2xl sm:text-3xl">Resultados</h2>
              <span className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground tabular">
                {filtered.length} {filtered.length === 1 ? "equipo" : "equipos"}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 lg:grid-cols-4 xl:grid-cols-5">
              {filtered.map((item, i) => (
                <EquipmentCard
                  key={item.id}
                  item={item}
                  index={i}
                  disponible={getDisponible(item)}
                />
              ))}
            </div>
          </section>
        )
      ) : (
        secciones.map(({ cat: c, items, real }) => {
          if (items.length === 0) return null;
          const key = real ? c : "__otros";

          if (isFiltered) {
            return (
              <section
                key={key}
                id={real ? `cat-${c}` : undefined}
                className="scroll-mt-40 px-4 lg:px-12"
              >
                <div className="mb-4 flex items-end justify-between gap-3">
                  <h2 className="font-display text-2xl sm:text-3xl">{c}</h2>
                  <span className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground tabular">
                    {items.length} {items.length === 1 ? "equipo" : "equipos"}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 lg:grid-cols-4 xl:grid-cols-5">
                  {items.map((item, i) => (
                    <EquipmentCard
                      key={item.id}
                      item={item}
                      index={i}
                      disponible={getDisponible(item)}
                    />
                  ))}
                </div>
              </section>
            );
          }

          return (
            <div
              key={key}
              id={real ? `cat-${c}` : undefined}
              data-cat-section={real ? "" : undefined}
              data-cat={real ? c : undefined}
              className="scroll-mt-40"
            >
              <CarouselRow
                title={c}
                count={items.length}
                action={
                  real ? (
                    <button
                      onClick={() => onJumpToCategory(c)}
                      className="hit-area-inline flex items-center gap-1 font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground hover:text-ink"
                    >
                      Ver sólo {c} <ArrowRight className="h-3 w-3" />
                    </button>
                  ) : undefined
                }
              >
                {items.map((item, i) => (
                  <EquipmentCard
                    key={item.id}
                    item={item}
                    index={i}
                    width={cardW}
                    disponible={getDisponible(item)}
                  />
                ))}
              </CarouselRow>
            </div>
          );
        })
      )}
    </div>
  );
}
