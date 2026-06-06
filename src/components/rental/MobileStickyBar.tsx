import { useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon, Search, SlidersHorizontal } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import type { Equipment } from "@/data/equipment";
import { RentalDateModal } from "./RentalDateModal";
import { DiscoverySheet } from "./DiscoverySheet";

type Props = {
  allEquipos: Equipment[];
  query: string;
  setQuery: (q: string) => void;
  categories: string[];
  brands: { id: number | string; nombre: string }[];
  selectedCategories: Set<string>;
  onToggleCategory: (c: string) => void;
  selectedBrand: string | null;
  onBrand: (b: string | null) => void;
  onClear: () => void;
  resultCount: number;
};

export function MobileStickyBar({
  allEquipos,
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
  // Un solo state — el DiscoverySheet maneja search y filters como tabs (#286).
  const [discoveryOpen, setDiscoveryOpen] = useState(false);
  const [discoveryDefaultTab, setDiscoveryDefaultTab] = useState<"search" | "filters">("search");

  const openDiscovery = (tab: "search" | "filters") => {
    setDiscoveryDefaultTab(tab);
    setDiscoveryOpen(true);
  };

  const hasDates = !!(startDate && endDate);
  const jornadas = days();
  const activeFilters = selectedCategories.size + (selectedBrand ? 1 : 0);

  return (
    <>
      <div className="md:hidden flex items-center gap-2">
        <button
          onClick={() => setDateModalOpen(true)}
          className="flex h-10 flex-1 min-w-0 items-center gap-2 rounded-full border border-amber/40 bg-amber/5 px-3 text-left transition hover:border-amber"
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
            <div className="flex-1 min-w-0 text-[13px] font-medium leading-none">Elegir fechas</div>
          )}
        </button>

        <button
          onClick={() => openDiscovery("search")}
          className="grid h-11 w-11 shrink-0 place-items-center rounded-full border hairline bg-surface hover:border-amber relative"
          aria-label="Buscar"
        >
          <Search className="h-4 w-4" />
          {query && <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-amber" />}
        </button>

        <button
          onClick={() => openDiscovery("filters")}
          className="grid h-11 w-11 shrink-0 place-items-center rounded-full border hairline bg-surface hover:border-amber relative"
          aria-label="Filtros"
        >
          <SlidersHorizontal className="h-4 w-4" />
          {activeFilters > 0 && (
            <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-ink px-1 text-[9px] font-bold text-amber">
              {activeFilters}
            </span>
          )}
        </button>
      </div>

      <RentalDateModal open={dateModalOpen} onOpenChange={setDateModalOpen} />
      <DiscoverySheet
        open={discoveryOpen}
        onOpenChange={setDiscoveryOpen}
        defaultTab={discoveryDefaultTab}
        query={query}
        setQuery={setQuery}
        allEquipos={allEquipos}
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
