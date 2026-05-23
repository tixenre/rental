import { type Equipment, type Category } from "@/data/equipment";
import { CategoryIllustration } from "./illustrations/CategoryIllustration";
import { cn } from "@/lib/utils";

/**
 * Mosaico de categorías estilo brand: ilustración + nombre + contador.
 * Click → activa esa categoría como filtro y salta al modo Lista.
 * Acepta allEquipos (data real de la API) y categories (lista dinámica).
 * Diseño 1:1 con el mock del handoff (eyebrow "buscá por" + título
 * "categorías" + grid auto-fill de tiles; muestra todas las categorías).
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
  return (
    <section className="px-6 py-8 lg:px-12 lg:py-12">
      <header className="mb-6">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
          buscá por
        </div>
        <h2 className="wordmark mt-1.5 text-5xl text-ink leading-[0.9]">categorías</h2>
      </header>

      <ul className="grid gap-2.5 [grid-template-columns:repeat(auto-fill,minmax(160px,1fr))]">
        {categories.map((c) => {
          const count = getCount ? getCount(c) : allEquipos.filter((e) => e.category === c).length;
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
