import { type Equipment, type Category } from "@/data/equipment";
import { CategoryIllustration } from "./illustrations/CategoryIllustration";
import { cn } from "@/lib/utils";

/**
 * Mosaico de categorías estilo brand: ilustración + nombre + contador.
 * Click → activa esa categoría como filtro y salta al modo Lista.
 * Acepta allEquipos (data real de la API) y categories (lista dinámica).
 */
export function CategoryMosaic({
  allEquipos,
  categories,
  onSelect,
}: {
  allEquipos: Equipment[];
  categories: string[];
  onSelect: (c: string) => void;
}) {
  return (
    <section className="px-6 py-8 lg:px-12 lg:py-12">
      <header className="mb-6 flex items-baseline justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
            buscá por
          </div>
          <h2 className="wordmark mt-1 text-4xl text-ink lg:text-5xl">categorías</h2>
        </div>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          {categories.length} familias
        </div>
      </header>

      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        {categories.map((c) => {
          const count = allEquipos.filter((e) => e.category === c).length;
          return (
            <li key={c}>
              <button
                onClick={() => onSelect(c)}
                className={cn(
                  "group flex w-full flex-col items-start gap-3 rounded-xl border hairline bg-surface p-4 text-left transition",
                  "hover:-translate-y-0.5 hover:border-ink hover:bg-amber-soft",
                )}
              >
                <span className="grid h-12 w-12 place-items-center rounded-lg bg-amber-soft text-amber transition group-hover:bg-amber group-hover:text-ink">
                  <CategoryIllustration category={c as Category} className="h-8 w-8" />
                </span>
                <div className="flex w-full items-baseline justify-between gap-2">
                  <span className="font-display text-base leading-tight text-ink">{c}</span>
                  <span className="font-mono text-[10px] tabular text-muted-foreground">
                    {count}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
