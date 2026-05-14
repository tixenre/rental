import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ChevronRight, Search, X } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Equipment } from "@/data/equipment";
import { buildEquipoSlug } from "@/lib/equipo-slug";
import { EmptyImage } from "./EmptyImage";
import { FilterControls } from "./FilterControls";

const MAX_RESULTS = 12;

const norm = (s: string) =>
  (s ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");

/**
 * Sheet de "discovery" mobile — unifica búsqueda y filtros en una sola
 * superficie con tabs. Reemplaza a `MobileSearchSheet` y `MobileFiltersSheet`.
 *
 * Por qué:
 * - Mental model único: el visitante abre un solo lugar para "encontrar
 *   equipos" (buscar O filtrar), no dos sheets distintos con UI propia.
 * - Header/footer compartidos.
 * - Fullscreen (no bottom-sheet) porque el input de búsqueda necesita el
 *   teclado virtual y `max-h-85vh` lo aplasta en mobiles chicos.
 *
 * El parent (MobileStickyBar) abre con `defaultTab="search"` desde el icono
 * lupa, o `defaultTab="filters"` desde el icono sliders. Una vez abierto,
 * el visitante cambia entre tabs sin cerrar.
 */
export function DiscoverySheet({
  open,
  onOpenChange,
  defaultTab,
  query,
  setQuery,
  allEquipos,
  categories,
  brands,
  selectedCategories,
  onToggleCategory,
  selectedBrand,
  onBrand,
  onClear,
  resultCount,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  defaultTab: "search" | "filters";
  query: string;
  setQuery: (q: string) => void;
  allEquipos: Equipment[];
  categories: string[];
  brands: { id: number | string; nombre: string }[];
  selectedCategories: Set<string>;
  onToggleCategory: (c: string) => void;
  selectedBrand: string | null;
  onBrand: (b: string | null) => void;
  onClear: () => void;
  resultCount: number;
}) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<"search" | "filters">(defaultTab);

  // Cuando abre, resetea al defaultTab pedido. Cuando el visitante cambia
  // de tab manualmente, eso queda hasta que se cierre.
  useEffect(() => {
    if (open) setTab(defaultTab);
  }, [open, defaultTab]);

  // Auto-focus del input al abrir en tab "search".
  useEffect(() => {
    if (open && tab === "search") {
      const t = setTimeout(() => inputRef.current?.focus(), 80);
      return () => clearTimeout(t);
    }
  }, [open, tab]);

  const trimmed = query.trim();
  const activeFilters = selectedCategories.size + (selectedBrand ? 1 : 0);

  const results = useMemo(() => {
    if (!trimmed) return [];
    const tokens = norm(trimmed).split(/\s+/).filter(Boolean);
    return allEquipos.filter((e) => {
      const specsText = (e.specs ?? []).map((s) => `${s.label} ${s.value}`).join(" ");
      const haystack = norm(
        [e.name, e.brand, e.category, e.description ?? "", specsText].join(" "),
      );
      return tokens.every((t) => haystack.includes(t));
    });
  }, [trimmed, allEquipos]);

  function handleSelect(item: Equipment) {
    onOpenChange(false);
    navigate({ to: "/equipo/$slug", params: { slug: buildEquipoSlug(item) } });
  }

  function handleCategoryFromSearch(cat: string) {
    onToggleCategory(cat);
    // Después de aplicar una sugerencia de búsqueda, ir a tab filtros
    // para que el visitante vea/ajuste filtros activos antes de cerrar.
    setTab("filters");
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ y: "100%" }}
          animate={{ y: 0 }}
          exit={{ y: "100%" }}
          transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
          className="fixed inset-0 z-50 flex flex-col bg-background"
        >
          {/* Header con back + título + tabs */}
          <div className="shrink-0 border-b hairline">
            <div className="flex items-center gap-2 px-3 py-3">
              <button
                onClick={() => onOpenChange(false)}
                className="grid h-10 w-10 shrink-0 place-items-center rounded-full hover:bg-muted"
                aria-label="Volver"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
              <div className="flex-1 font-display text-lg">Descubrir</div>
              <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground tabular pr-2">
                {resultCount} {resultCount === 1 ? "equipo" : "equipos"}
              </span>
            </div>

            <Tabs value={tab} onValueChange={(v) => setTab(v as "search" | "filters")}>
              <TabsList className="grid w-full grid-cols-2 rounded-none border-b hairline bg-transparent h-11 p-0">
                <TabsTrigger
                  value="search"
                  className="data-[state=active]:border-b-2 data-[state=active]:border-ink data-[state=active]:bg-transparent data-[state=active]:shadow-none rounded-none h-11"
                >
                  <Search className="h-3.5 w-3.5 mr-1.5" /> Buscar
                </TabsTrigger>
                <TabsTrigger
                  value="filters"
                  className="data-[state=active]:border-b-2 data-[state=active]:border-ink data-[state=active]:bg-transparent data-[state=active]:shadow-none rounded-none h-11"
                >
                  Filtros
                  {activeFilters > 0 && (
                    <span className="ml-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-ink px-1 text-[9px] font-bold text-amber">
                      {activeFilters}
                    </span>
                  )}
                </TabsTrigger>
              </TabsList>

              {/* Body */}
              <div className="flex-1 overflow-y-auto overscroll-contain">
                <TabsContent value="search" className="m-0">
                  <SearchBody
                    inputRef={inputRef}
                    query={query}
                    setQuery={setQuery}
                    trimmed={trimmed}
                    results={results}
                    categories={categories}
                    onCategorySelect={handleCategoryFromSearch}
                    onSelect={handleSelect}
                    onClose={() => onOpenChange(false)}
                  />
                </TabsContent>

                <TabsContent value="filters" className="m-0">
                  <div className="px-4 py-5 pb-8">
                    <FilterControls
                      layout="stacked"
                      categories={categories}
                      brands={brands}
                      selectedCategories={selectedCategories}
                      onToggleCategory={onToggleCategory}
                      selectedBrand={selectedBrand}
                      onBrand={onBrand}
                      onClear={onClear}
                      showClear={false}
                    />
                  </div>
                </TabsContent>
              </div>
            </Tabs>
          </div>

          {/* Footer acciones — solo en tab filtros */}
          {tab === "filters" && (
            <div
              className="shrink-0 flex items-center gap-2 border-t hairline bg-background/95 px-4 py-3 backdrop-blur-xl"
              style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}
            >
              {activeFilters > 0 && (
                <button
                  onClick={onClear}
                  className="flex items-center gap-1.5 rounded-full border hairline px-4 py-2 text-xs uppercase tracking-wider text-muted-foreground hover:border-ink hover:text-ink"
                >
                  <X className="h-3 w-3" /> Limpiar
                </button>
              )}
              <button
                onClick={() => onOpenChange(false)}
                className="ml-auto flex-1 rounded-full bg-ink px-4 py-2.5 text-sm font-semibold text-amber hover:bg-foreground"
              >
                Ver {resultCount} resultados
              </button>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function SearchBody({
  inputRef,
  query,
  setQuery,
  trimmed,
  results,
  categories,
  onCategorySelect,
  onSelect,
  onClose,
}: {
  inputRef: React.RefObject<HTMLInputElement | null>;
  query: string;
  setQuery: (q: string) => void;
  trimmed: string;
  results: Equipment[];
  categories: string[];
  onCategorySelect: (c: string) => void;
  onSelect: (item: Equipment) => void;
  onClose: () => void;
}) {
  return (
    <>
      {/* Input search sticky bajo los tabs */}
      <div className="sticky top-0 z-10 border-b hairline bg-background px-3 py-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar equipo, marca, categoría…"
            className="h-11 w-full rounded-xl border hairline bg-muted/40 pl-10 pr-10 text-base placeholder:text-muted-foreground focus:border-amber/60 focus:bg-background focus:outline-none"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 grid h-6 w-6 place-items-center rounded-full bg-muted text-muted-foreground hover:bg-muted-foreground/20"
              aria-label="Limpiar búsqueda"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {!trimmed ? (
        <div className="px-4 pt-5">
          <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Categorías
          </p>
          <div className="flex flex-wrap gap-2">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => onCategorySelect(cat)}
                className="rounded-full border hairline bg-surface px-3.5 py-2 text-sm font-medium text-ink transition active:scale-95 active:bg-muted"
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      ) : results.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-1.5 py-20 text-center">
          <p className="text-sm font-medium text-ink">Sin resultados</p>
          <p className="text-xs text-muted-foreground">
            Probá con otra palabra o revisá la ortografía
          </p>
        </div>
      ) : (
        <>
          <ul className="divide-y hairline">
            {results.slice(0, MAX_RESULTS).map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => onSelect(item)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left transition active:bg-muted"
                >
                  <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-md bg-muted/40">
                    {item.fotoUrl ? (
                      <img
                        src={item.fotoUrl}
                        alt={item.name}
                        className="h-full w-full object-cover"
                        loading="lazy"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.opacity = "0";
                        }}
                      />
                    ) : (
                      <EmptyImage category={item.category} brand={item.brand} />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="truncate text-sm font-medium text-ink">{item.name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {item.brand} · {item.category}
                    </p>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                </button>
              </li>
            ))}
          </ul>
          {results.length > MAX_RESULTS && (
            <button
              onClick={onClose}
              className="w-full py-4 text-sm font-medium text-amber"
            >
              Ver los {results.length} resultados →
            </button>
          )}
        </>
      )}
    </>
  );
}
