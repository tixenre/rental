import { type Equipment, type Category } from "@/data/equipment";
import { CategoryIllustration } from "./illustrations/CategoryIllustration";
import { CarouselRow } from "./CarouselRow";
import { cn } from "@/lib/utils";

/**
 * Categorías: carrusel en mobile/tablet, grilla de 5 columnas en desktop (lg+).
 * Click → activa esa categoría como filtro y salta al modo Lista.
 */
export function CategoryMosaic({
  allEquipos,
  categories,
  onSelect,
  getCount,
}: {
  allEquipos: Equipment[];
  categories: string[];
  onSelect: (c: string) => void;
  /** Conteo por categoría. Si no se pasa, cuenta solo la categoría primaria
   *  (legacy). El catálogo pasa el conteo por pertenencia M2M para que matchee
   *  los tabs. */
  getCount?: (c: string) => number;
}) {
  if (categories.length === 0) return null;

  const titleNode = (
    <span className="flex flex-col leading-none">
      <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
        buscá por
      </span>
      <span className="mt-1.5 leading-[0.9]">categorías</span>
    </span>
  );

  const renderCard = (c: string) => {
    const count = getCount ? getCount(c) : allEquipos.filter((e) => e.category === c).length;
    return (
      <button
        onClick={() => onSelect(c)}
        className={cn(
          "group flex h-full w-full flex-col items-start gap-3 rounded-xl border hairline bg-surface p-4 text-left transition",
          "hover:-translate-y-0.5 hover:border-ink hover:bg-amber-soft",
        )}
      >
        <span className="grid h-12 w-12 place-items-center rounded-lg bg-amber-soft text-amber transition group-hover:bg-amber group-hover:text-ink">
          <CategoryIllustration category={c as Category} className="h-8 w-8" />
        </span>
        <div className="flex w-full items-baseline justify-between gap-2">
          <span className="font-display text-base leading-tight text-ink">{c}</span>
          <span className="font-mono text-[10px] tabular text-muted-foreground">{count}</span>
        </div>
      </button>
    );
  };

  return (
    <>
      {/* Mobile / tablet: carrusel con scroll-snap */}
      <CarouselRow className="py-8 lg:hidden" title={titleNode}>
        {categories.map((c) => (
          <div key={c} style={{ flexShrink: 0 }} className="w-44 snap-start">
            {renderCard(c)}
          </div>
        ))}
      </CarouselRow>

      {/* Desktop: grilla de 5 columnas */}
      <section className="hidden lg:block relative py-12">
        <header className="mb-6 px-12">
          <h2 className="wordmark text-4xl text-ink">{titleNode}</h2>
        </header>
        <div className="grid grid-cols-5 gap-4 px-12">
          {categories.map((c) => (
            <div key={c}>{renderCard(c)}</div>
          ))}
        </div>
      </section>
    </>
  );
}
