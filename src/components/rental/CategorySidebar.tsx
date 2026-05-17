import { cn } from "@/lib/utils";
import { useMemo, useState } from "react";
import { Search, LayoutGrid } from "lucide-react";
import { CategoryIllustration } from "./illustrations/CategoryIllustration";
import { type Equipment, type Category } from "@/data/equipment";

const KNOWN_CATEGORIES: Category[] = [
  "Cámaras",
  "Lentes",
  "Adaptadores",
  "Filtros",
  "Iluminación",
  "Audio",
  "Soportes",
  "Accesorios",
];

// Agrupado visual del menú lateral: categorías raíz independientes en el
// modelo de datos, pero renderizadas bajo un header común en el sidebar.
// Cada entrada: [header, lista de categorías que cuelgan]. Las categorías
// que no aparezcan acá se renderizan sueltas en su lugar habitual.
//
// Decisión: hard-coded — basta con 1 grupo por ahora ("Óptica"). Si surgen
// más (ej. "Audio" agrupando Sonido + Monitores), migrar a metadata en
// la tabla categorias.
const CATEGORY_GROUPS: { header: string; categories: string[] }[] = [
  { header: "Óptica", categories: ["Lentes", "Adaptadores", "Filtros"] },
];

// TODO: rendering de sub-cats (Montura E/EF/RF, 82mm, etc.) requiere expandir
// Equipment.category (singular) → Equipment.categories (plural M2M). Hoy el
// backend devuelve solo la categoría principal por equipo, pero los seeds
// asignan a múltiples sub-cats vía `equipo_categorias`. Cuando se expanda
// el contrato API, agregar render anidado: `<li>Lentes</li> → <ul><li>Zoom</li>
// <li>Fijo</li> <li>Montura E</li> ...</ul>`.

export function CategorySidebar({
  activeCategory,
  activeBrand,
  allEquipos,
  onCategory,
  onBrand,
}: {
  activeCategory: string;
  activeBrand: string | null;
  allEquipos: Equipment[];
  onCategory: (c: string) => void;
  onBrand: (b: string | null) => void;
}) {
  const [brandQuery, setBrandQuery] = useState("");

  // Categorías presentes en la API, manteniendo el orden canónico
  const categories = useMemo(() => {
    const inApi = new Set(allEquipos.map((e) => e.category));
    // Primero las conocidas que existen, luego cualquier extra de la API
    const known = KNOWN_CATEGORIES.filter((c) => inApi.has(c));
    const extras = Array.from(inApi).filter((c) => !KNOWN_CATEGORIES.includes(c as Category)).sort();
    return [...known, ...extras];
  }, [allEquipos]);

  // Marcas derivadas de la data real de la API (filtrando nulls/vacíos)
  const brands = useMemo(
    () => Array.from(new Set(allEquipos.map((e) => e.brand).filter(Boolean))).sort(),
    [allEquipos],
  );

  const filteredBrands = brands.filter((b) =>
    (b ?? "").toLowerCase().includes(brandQuery.toLowerCase()),
  );

  const countByCategory = (c: string) =>
    c === "Todos"
      ? allEquipos.length
      : allEquipos.filter((e) => e.category === c).length;

  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col gap-8 border-r hairline px-6 py-8 sticky top-[68px] h-[calc(100vh-68px)] overflow-y-auto">
      <div>
        <div className="mb-4 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Categorías
        </div>
        <ul className="space-y-1">
          {(() => {
            // Render con soporte de grupos visuales (ver CATEGORY_GROUPS).
            // Estructura semántica: cada grupo es un <li> con un header
            // (`<div role="presentation">`) + `<ul>` anidada con sus items.
            // Esto permite a screen readers entender la jerarquía. Si un grupo
            // tiene 0 o 1 categorías en la API, NO emitimos el header (queda
            // raro un grupo con una sola entrada).
            const items: React.ReactNode[] = [];
            const seen = new Set<string>();

            const renderButton = (c: string) => {
              const active = activeCategory === c;
              return (
                <button
                  onClick={() => onCategory(c)}
                  className={cn(
                    "group flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-sm transition",
                    active
                      ? "bg-amber-soft text-ink"
                      : "text-foreground/80 hover:bg-surface hover:text-foreground",
                  )}
                  aria-pressed={active}
                >
                  <span
                    className={cn(
                      "grid h-7 w-7 shrink-0 place-items-center rounded-md transition",
                      active ? "text-ink" : "text-foreground/40 group-hover:text-foreground/70",
                    )}
                    aria-hidden="true"
                  >
                    {c === "Todos" ? (
                      <LayoutGrid className="h-4 w-4" strokeWidth={2} />
                    ) : (
                      <CategoryIllustration
                        category={KNOWN_CATEGORIES.includes(c as Category) ? (c as Category) : "Accesorios"}
                        className="h-6 w-6"
                      />
                    )}
                  </span>
                  <span className="font-display text-base flex-1 text-left">{c}</span>
                  <span className="font-mono text-[10px] tabular text-muted-foreground">
                    {countByCategory(c)}
                  </span>
                </button>
              );
            };

            for (const c of ["Todos", ...categories]) {
              if (seen.has(c)) continue;
              const group = CATEGORY_GROUPS.find((g) => g.categories.includes(c));
              if (group) {
                // Reunir TODAS las cats del grupo presentes en la API, en
                // orden definido por CATEGORY_GROUPS (no en orden API).
                const present = group.categories.filter((gc) => categories.includes(gc) && !seen.has(gc));
                present.forEach((gc) => seen.add(gc));
                // Solo emitimos header si hay ≥2 items en el grupo;
                // sino el grupo se renderea como cats sueltas.
                if (present.length >= 2) {
                  items.push(
                    <li key={`__group__${group.header}`}>
                      <div
                        id={`group-${group.header.toLowerCase()}`}
                        className="pt-2 pb-1 px-2 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground/70"
                      >
                        {group.header}
                      </div>
                      <ul
                        className="space-y-1 ml-2 pl-3 border-l hairline"
                        aria-labelledby={`group-${group.header.toLowerCase()}`}
                      >
                        {present.map((gc) => (
                          <li key={gc}>{renderButton(gc)}</li>
                        ))}
                      </ul>
                    </li>,
                  );
                  continue;
                }
                // grupo con 1 sola cat → render plano
                present.forEach((gc) => {
                  items.push(<li key={gc}>{renderButton(gc)}</li>);
                });
                continue;
              }
              seen.add(c);
              items.push(<li key={c}>{renderButton(c)}</li>);
            }
            return items;
          })()}
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
