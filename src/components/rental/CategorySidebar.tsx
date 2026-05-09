import { categories, brands, equipment, type Category } from "@/data/equipment";
import { cn } from "@/lib/utils";
import { useState } from "react";
import { Search, LayoutGrid } from "lucide-react";
import { CategoryIllustration } from "./illustrations/CategoryIllustration";

export function CategorySidebar({
  activeCategory,
  activeBrand,
  onCategory,
  onBrand,
}: {
  activeCategory: Category | "Todos";
  activeBrand: string | null;
  onCategory: (c: Category | "Todos") => void;
  onBrand: (b: string | null) => void;
}) {
  const [brandQuery, setBrandQuery] = useState("");
  const filteredBrands = brands.filter((b) =>
    b.toLowerCase().includes(brandQuery.toLowerCase()),
  );
  const countByCategory = (c: Category | "Todos") =>
    c === "Todos" ? equipment.length : equipment.filter((e) => e.category === c).length;

  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col gap-8 border-r hairline px-6 py-8 sticky top-[68px] h-[calc(100vh-68px)] overflow-y-auto">
      <div>
        <div className="mb-4 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Categorías
        </div>
        <ul className="space-y-1">
          {(["Todos", ...categories] as const).map((c) => {
            const active = activeCategory === c;
            return (
              <li key={c}>
                <button
                  onClick={() => onCategory(c)}
                  className={cn(
                    "group flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-sm transition",
                    active
                      ? "bg-amber-soft text-ink"
                      : "text-foreground/80 hover:bg-surface hover:text-foreground",
                  )}
                >
                  <span
                    className={cn(
                      "grid h-7 w-7 shrink-0 place-items-center rounded-md transition",
                      active ? "text-ink" : "text-foreground/40 group-hover:text-foreground/70",
                    )}
                  >
                    {c === "Todos" ? (
                      <LayoutGrid className="h-4 w-4" strokeWidth={2} />
                    ) : (
                      <CategoryIllustration category={c} className="h-6 w-6" />
                    )}
                  </span>
                  <span className="font-display text-base flex-1 text-left">{c}</span>
                  <span className="font-mono text-[10px] tabular text-muted-foreground">
                    {countByCategory(c)}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Marcas
          </span>
          {activeBrand && (
            <button
              onClick={() => onBrand(null)}
              className="font-mono text-[10px] uppercase tracking-widest text-amber hover:underline"
            >
              limpiar
            </button>
          )}
        </div>
        <div className="relative mb-3">
          <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
          <input
            value={brandQuery}
            onChange={(e) => setBrandQuery(e.target.value)}
            placeholder="Buscar marca…"
            className="w-full rounded-md border hairline bg-surface py-1.5 pl-7 pr-2 text-xs placeholder:text-muted-foreground focus:border-amber/40 focus:outline-none"
          />
        </div>
        <ul className="space-y-0.5">
          {filteredBrands.map((b) => {
            const active = activeBrand === b;
            return (
              <li key={b}>
                <button
                  onClick={() => onBrand(active ? null : b)}
                  className={cn(
                    "block w-full text-left text-sm transition py-1 px-2 rounded",
                    active
                      ? "text-amber"
                      : "text-foreground/70 hover:text-foreground",
                  )}
                >
                  {b}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}
