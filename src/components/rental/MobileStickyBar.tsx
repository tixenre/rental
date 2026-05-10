import { useEffect, useRef, useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, Search, SlidersHorizontal, X } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { RentalDateModal } from "./RentalDateModal";
import { MobileFiltersSheet } from "./MobileFiltersSheet";

type Props = {
  query: string;
  setQuery: (q: string) => void;
  categories: string[];
  brands: any[];
  selectedCategories: Set<string>;
  onToggleCategory: (c: string) => void;
  selectedBrand: string | null;
  onBrand: (b: string | null) => void;
  onClear: () => void;
  resultCount: number;
};

export function MobileStickyBar({
  query,
  setQuery,
  categories,
  brands,
  selectedCategories,
  onToggleCategory,
  selectedBrand,
  onBrand,
  onClear,
  resultCount,
}: Props) {
  const { startDate, endDate, startTime, endTime, days } = useCart();
  const [dateModalOpen, setDateModalOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const searchTriggerRef = useRef<HTMLButtonElement>(null);

  const hasDates = !!(startDate && endDate);
  const jornadas = days();
  const activeFilters = selectedCategories.size + (selectedBrand ? 1 : 0);

  useEffect(() => {
    if (searchOpen) inputRef.current?.focus();
  }, [searchOpen]);

  const closeSearch = () => {
    setSearchOpen(false);
    setQuery("");
    searchTriggerRef.current?.focus();
  };

  return (
    <>
      <div className="md:hidden flex items-center gap-2">
        {searchOpen ? (
          <>
            <div className="relative flex-1 min-w-0">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") closeSearch();
                }}
                placeholder="Buscar equipo, marca…"
                className="w-full rounded-full border border-amber/40 bg-amber/5 py-2.5 pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:border-amber focus:outline-none"
              />
            </div>
            <button
              onClick={closeSearch}
              className="grid h-10 w-10 shrink-0 place-items-center rounded-full border hairline bg-surface hover:border-foreground/40"
              aria-label="Cerrar búsqueda"
            >
              <X className="h-4 w-4" />
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => setDateModalOpen(true)}
              className="flex flex-1 min-w-0 items-center gap-2 rounded-full border border-amber/40 bg-amber/5 px-3 py-2 text-left transition hover:border-amber"
              aria-label={hasDates ? "Editar fechas y horarios" : "Elegir fechas"}
            >
              <CalendarIcon className="h-4 w-4 shrink-0" />
              {hasDates ? (
                <div className="flex-1 min-w-0 text-[13px] font-medium leading-none tabular-nums truncate">
                  {format(startDate!, "dd MMM", { locale: es })} {startTime}
                  <span className="mx-1 text-muted-foreground">→</span>
                  {format(endDate!, "dd MMM", { locale: es })} {endTime}
                  <span className="ml-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    · {jornadas}j
                  </span>
                </div>
              ) : (
                <div className="flex-1 min-w-0 text-[13px] font-medium leading-none">
                  Elegir fechas
                </div>
              )}
            </button>
            <button
              ref={searchTriggerRef}
              onClick={() => setSearchOpen(true)}
              className="grid h-10 w-10 shrink-0 place-items-center rounded-full border hairline bg-surface hover:border-amber relative"
              aria-label="Buscar"
            >
              <Search className="h-4 w-4" />
              {query && (
                <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-amber" />
              )}
            </button>
            <button
              onClick={() => setFiltersOpen(true)}
              className="grid h-10 w-10 shrink-0 place-items-center rounded-full border hairline bg-surface hover:border-amber relative"
              aria-label="Filtros"
            >
              <SlidersHorizontal className="h-4 w-4" />
              {activeFilters > 0 && (
                <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-ink px-1 text-[9px] font-bold text-amber">
                  {activeFilters}
                </span>
              )}
            </button>
          </>
        )}
      </div>
      <RentalDateModal open={dateModalOpen} onOpenChange={setDateModalOpen} />
      <MobileFiltersSheet
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        categories={categories}
        brands={brands}
        selectedCategories={selectedCategories}
        onToggleCategory={onToggleCategory}
        selectedBrand={selectedBrand}
        onBrand={onBrand}
        onClear={onClear}
        resultCount={resultCount}
      />
    </>
  );
}
