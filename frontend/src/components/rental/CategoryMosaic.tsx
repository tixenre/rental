import { useRef, useEffect } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { type Equipment, type Category } from "@/data/equipment";
import { CategoryIllustration } from "./illustrations/CategoryIllustration";

export function CategoryMosaic({
  allEquipos,
  categories,
  onSelect,
  getCount,
}: {
  allEquipos: Equipment[];
  categories: string[];
  onSelect: (c: string) => void;
  getCount?: (c: string) => number;
}) {
  if (categories.length === 0) return null;

  return (
    <section className="pt-4 pb-6 lg:pt-5 lg:pb-8">
      <div className="mb-4 flex items-end justify-between px-6 lg:px-12">
        <div className="flex flex-col leading-none">
          <span className="font-mono text-2xs uppercase tracking-[0.3em] text-muted-foreground">
            buscá por
          </span>
          <span className="mt-1.5 font-display text-2xl leading-[0.9]">categorías</span>
        </div>
        <ScrollButtons categories={categories} />
      </div>
      <CategoryScrollRow
        allEquipos={allEquipos}
        categories={categories}
        onSelect={onSelect}
        getCount={getCount}
      />
    </section>
  );
}

function ScrollButtons({ categories }: { categories: string[] }) {
  // Access the sibling scroll row via a shared ref key.
  // Simpler approach: use a context or just render arrows inside the scroll wrapper.
  // Here we use a data attribute to find the scroll container.
  const scrollBy = (dir: 1 | -1) => {
    const el = document.querySelector<HTMLDivElement>("[data-cat-scroll]");
    if (!el) return;
    el.scrollBy({ left: dir * Math.round(el.clientWidth * 0.7), behavior: "smooth" });
  };

  if (categories.length <= 3) return null;

  return (
    <div className="hidden sm:flex items-center gap-1">
      <button
        onClick={() => scrollBy(-1)}
        aria-label="Categorías anteriores"
        className="grid h-8 w-8 place-items-center rounded-full border hairline bg-background transition hover:border-ink hover:bg-ink hover:text-amber"
      >
        <ArrowLeft className="h-4 w-4" />
      </button>
      <button
        onClick={() => scrollBy(1)}
        aria-label="Categorías siguientes"
        className="grid h-8 w-8 place-items-center rounded-full border hairline bg-background transition hover:border-ink hover:bg-ink hover:text-amber"
      >
        <ArrowRight className="h-4 w-4" />
      </button>
    </div>
  );
}

function CategoryScrollRow({
  allEquipos,
  categories,
  onSelect,
  getCount,
}: {
  allEquipos: Equipment[];
  categories: string[];
  onSelect: (c: string) => void;
  getCount?: (c: string) => number;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    return () => {};
  }, []);

  return (
    <div
      ref={ref}
      data-cat-scroll
      className="flex snap-x snap-mandatory gap-3 overflow-x-auto scroll-pl-6 px-6 py-2 lg:scroll-pl-12 lg:px-12 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]"
    >
      {categories.map((c) => {
        const count = getCount ? getCount(c) : allEquipos.filter((e) => e.category === c).length;
        return (
          <button
            key={c}
            onClick={() => onSelect(c)}
            className="group shrink-0 w-[148px] snap-start flex flex-col items-start gap-3 rounded-xl border hairline bg-surface p-4 text-left transition hover:-translate-y-0.5 hover:border-ink hover:bg-amber-soft"
          >
            <span className="grid h-11 w-11 place-items-center rounded-lg bg-amber-soft text-amber transition group-hover:bg-amber group-hover:text-ink">
              <CategoryIllustration category={c as Category} className="h-7 w-7" />
            </span>
            <div className="flex w-full items-baseline justify-between gap-1">
              <span className="font-display text-[0.9rem] leading-tight text-ink">{c}</span>
              <span className="font-mono text-2xs tabular text-muted-foreground shrink-0">
                {count}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
