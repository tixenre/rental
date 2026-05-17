import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { CatalogoMovil } from "@/components/rental/mobile/CatalogoMovil";
import { LayoutGrid, List, ArrowRight, Sparkles, Loader2, Search, X, Check, SearchX } from "lucide-react";
import { ViewToggle } from "@/components/rental/ViewToggle";
import { Link } from "@tanstack/react-router";
import { PublicLayout } from "@/components/rental/PublicLayout";
import { MobileStickyBar } from "@/components/rental/MobileStickyBar";
import { EquipmentCard } from "@/components/rental/EquipmentCard";
import { EquipmentRow } from "@/components/rental/EquipmentRow";
import { CartDrawer } from "@/components/rental/CartDrawer";
import { CartMiniBar } from "@/components/rental/CartMiniBar";
import { FlyToCartLayer } from "@/components/rental/FlyToCartLayer";
import { CarouselRow } from "@/components/rental/CarouselRow";
import { CategoryMosaic } from "@/components/rental/CategoryMosaic";
import { BrandCarousel } from "@/components/rental/BrandCarousel";
import { ListFilters } from "@/components/rental/ListFilters";
import { ActiveFiltersChips } from "@/components/rental/ActiveFiltersChips";
import { ViewIntroDialog } from "@/components/rental/ViewIntroDialog";
import { PreviewPane } from "@/components/rental/PreviewPane";
import { useEquipos, useCategorias, useMarcas } from "@/hooks/useEquipos";
import type { BackendMarca } from "@/lib/api";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

const POPULAR_CHIPS = ["Sony FX3", "Aputure 600d", "RØDE", "Pack boda", "Pack entrevista"];

type IndexSearch = {
  /** Modo de visualización compartible por URL. `?view=grid` o `?view=list`. */
  view?: "grid" | "list";
  /** Pre-filtra el catálogo por una categoría (root o sub-cat). Se usa para
   *  deep-linking desde la página de detalle u otros entry points. */
  cat?: string;
};

export const Route = createFileRoute("/")({
  validateSearch: (search: Record<string, unknown>): IndexSearch => {
    const v = search.view;
    const c = search.cat;
    return {
      view: v === "grid" || v === "list" ? v : undefined,
      cat: typeof c === "string" && c.trim() ? c.trim() : undefined,
    };
  },
  head: () => ({
    meta: [
      { title: "Rambla Rental — Alquiler de equipos de cine y foto en Mar del Plata" },
      {
        name: "description",
        content:
          "Cámaras, lentes, iluminación, audio y soportes para producciones audiovisuales. Estudio de foto y video en Mar del Plata.",
      },
      // Open Graph (Facebook, WhatsApp, LinkedIn).
      { property: "og:type", content: "website" },
      { property: "og:url", content: "https://ramblarental.com/" },
      { property: "og:title", content: "Rambla Rental — Alquiler de equipos de cine y foto" },
      {
        property: "og:description",
        content: "Cámaras, lentes, iluminación, audio y soportes. Estudio en Mar del Plata.",
      },
      { property: "og:image", content: "https://ramblarental.com/icon-512.png" },
      { property: "og:locale", content: "es_AR" },
      // Twitter Cards.
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:title", content: "Rambla Rental" },
      { name: "twitter:description", content: "Equipos audiovisuales · Mar del Plata" },
      { name: "twitter:image", content: "https://ramblarental.com/icon-512.png" },
    ],
    links: [
      { rel: "canonical", href: "https://ramblarental.com/" },
    ],
  }),
  component: IndexOrMobile,
});

function IndexOrMobile() {
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== "undefined" && window.innerWidth < 768,
  );
  useEffect(() => {
    const mql = window.matchMedia("(max-width: 767px)");
    const onChange = () => setIsMobile(window.innerWidth < 768);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);
  if (isMobile) return <CatalogoMovil />;
  return <Index />;
}

type Mode = "grid" | "list";

function Index() {
  // Datos de la API
  const { startDate, endDate } = useCart();
  const { data: allEquipos = [], isLoading, isError } = useEquipos(startDate, endDate);
  const { data: backendCats = [] } = useCategorias();
  const { data: marcasData } = useMarcas();

  // Categorías derivadas, ordenadas por prioridad del backend.
  // Las que no aparecen en /api/categorias quedan al final, alfabéticas.
  const apiCategories = useMemo(() => {
    const cats = Array.from(new Set(allEquipos.map((e) => e.category)));
    // Sort por: prioridad ASC (manual del admin), después popularidad
    // DESC (automática del ranking #131), después alfabético.
    // Mismo criterio que el backend ORDER BY en /api/categorias.
    const meta: Record<string, { prioridad: number; popularidad: number }> = {};
    backendCats.forEach((c: { nombre: string; prioridad?: number; popularidad_score?: number }) => {
      meta[c.nombre] = {
        prioridad: c.prioridad ?? 100,
        popularidad: c.popularidad_score ?? 0,
      };
    });
    return cats.sort((a, b) => {
      const ma = meta[a] ?? { prioridad: 999, popularidad: 0 };
      const mb = meta[b] ?? { prioridad: 999, popularidad: 0 };
      if (ma.prioridad !== mb.prioridad) return ma.prioridad - mb.prioridad;
      if (ma.popularidad !== mb.popularidad) return mb.popularidad - ma.popularidad;
      return a.localeCompare(b, "es");
    });
  }, [allEquipos, backendCats]);
  const marcas = marcasData?.items ?? [];

  // Modo de view en la URL: ?view=grid | ?view=list. Si no está, default
  // según ancho de pantalla (mobile→list, desktop→grid). El navigate
  // mantiene los otros search params intactos.
  const search = useSearch({ from: "/" }) as IndexSearch;
  const navigate = useNavigate({ from: "/" });
  const defaultMode: Mode =
    typeof window !== "undefined" &&
    window.matchMedia?.("(max-width: 639px)").matches
      ? "list"
      : "grid";
  const mode: Mode = search.view ?? defaultMode;
  const setMode = (m: Mode) => {
    navigate({
      search: (prev) => ({ ...prev, view: m }),
      replace: true,
    });
  };

  const [selectedCats, setSelectedCats] = useState<Set<string>>(
    () => (search.cat ? new Set([search.cat]) : new Set()),
  );
  const [brand, setBrand] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  // Filtro "Disponibles": esconde equipos con disponible === 0 (sin stock
  // para las fechas pickeadas). Solo tiene efecto cuando hay rango de fechas
  // — sin fechas, `disponible` queda undefined y todos pasan.
  const [disponiblesOnly, setDisponiblesOnly] = useState(false);

  const toggleCat = (c: string) => {
    setSelectedCats((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  };

  const filtered = useMemo(() => {
    // Normaliza: minúsculas + sin acentos. Así "baterias" matchea "Batería".
    const norm = (s: string) =>
      (s ?? "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");

    let list = allEquipos.slice();
    if (selectedCats.size > 0) {
      // Match contra root (`e.category`) + sub-cats (vía `equipo_categorias` M2M).
      // Permite filtrar por "Montura E" o "Lentes" indistintamente.
      list = list.filter(
        (e) =>
          selectedCats.has(e.category) ||
          (e.categorias ?? []).some((c) => selectedCats.has(c.nombre)),
      );
    }
    if (brand) list = list.filter((e) => e.brand === brand);
    if (disponiblesOnly) {
      list = list.filter((e) => e.disponible === undefined || e.disponible > 0);
    }
    if (query.trim()) {
      // Cada palabra de la query debe aparecer en el "haystack" del equipo.
      const tokens = norm(query).split(/\s+/).filter(Boolean);
      list = list.filter((e) => {
        const specsText = (e.specs ?? []).map((s) => `${s.label} ${s.value}`).join(" ");
        const haystack = norm(
          [e.name, e.brand, e.category, e.description ?? "", specsText].join(" "),
        );
        return tokens.every((t) => haystack.includes(t));
      });
    }
    return list;
  }, [selectedCats, brand, query, disponiblesOnly, allEquipos]);

  const jumpToCategory = (c: string) => {
    setSelectedCats(new Set([c]));
    setMode("grid");
    requestAnimationFrame(() => {
      const el = document.getElementById(`cat-${c}`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      else window.scrollTo({ top: 0, behavior: "smooth" });
    });
  };

  const getDisponible = (item: Equipment) => item.disponible;

  // Hero scroll-amber: calcula --amber-pct para que el TopBar se tiña
  const heroRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const hero = heroRef.current;
    if (!hero) return;
    const onScroll = () => {
      const heroH = hero.offsetHeight;
      const pct = heroH > 0 ? Math.min(100, Math.round((window.scrollY / heroH) * 100)) : 0;
      document.documentElement.style.setProperty("--amber-pct", pct + "%");
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => {
      window.removeEventListener("scroll", onScroll);
      document.documentElement.style.setProperty("--amber-pct", "0%");
    };
  }, []);

  return (
    <PublicLayout topBar={{ amberOnScroll: true }}>
        <ViewIntroDialog onPick={(m) => setMode(m)} />
        {/* Hero amarillo brand */}
        <section ref={heroRef} className="relative overflow-hidden border-b hairline bg-amber text-ink">
          <div className="absolute inset-0 grain opacity-40" />
          <div className="relative px-6 py-12 lg:px-12 lg:py-16">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] sm:tracking-[0.3em] text-ink/70 break-words">
              Catálogo · {isLoading ? "…" : allEquipos.length} equipos · Mar del Plata
            </div>
            <h1 className="mt-4 wordmark text-5xl sm:text-7xl md:text-[7rem] lg:text-[8.5rem] leading-[0.9] md:leading-[0.85] text-balance break-words">
              un lugar
              <br />
              donde pasan
              <br />
              cosas.
            </h1>
            <p className="mt-6 max-w-xl text-base text-ink/80">
              Cámaras, ópticas, luces, audio y soportes para producciones audiovisuales. Elegí
              fechas y armá tu pedido — te lo dejamos listo para retirar.
            </p>

            {/* CTA Estudio — protagonista del banner */}
            <div className="mt-10 inline-flex max-w-2xl flex-col gap-4 rounded-3xl border-2 border-ink bg-ink p-6 sm:flex-row sm:items-center sm:gap-6 sm:p-7 shadow-lg">
              <div className="flex-1">
                <div className="inline-flex items-center gap-1.5 rounded-full bg-amber px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.25em] text-ink">
                  <Sparkles className="h-3 w-3" /> Espacio Rambla
                </div>
                <div className="mt-3 font-display text-2xl sm:text-3xl text-amber">Conocé el Estudio</div>
                <div className="text-sm text-amber/80 mt-1">
                  Foto y video · reservá por hora · pack de luces y grips opcional
                </div>
              </div>
              <Link
                to="/estudio"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-amber px-6 py-3 text-sm font-semibold text-ink transition hover:brightness-110"
              >
                Ver estudio <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </section>

        {/* Toggle Modo + búsqueda sticky */}
        <div className="sticky top-14 sm:top-[69px] z-30 border-b hairline bg-background">
          {/* Mobile */}
          <div className="sm:hidden px-3 py-3">
            <MobileStickyBar
              allEquipos={allEquipos}
              query={query}
              setQuery={setQuery}
              categories={apiCategories}
              brands={marcas}
              selectedCategories={selectedCats}
              onToggleCategory={toggleCat}
              selectedBrand={brand}
              onBrand={setBrand}
              onClear={() => {
                setSelectedCats(new Set());
                setBrand(null);
                setQuery("");
              }}
              resultCount={filtered.length}
            />
          </div>

          {/* Desktop: cat-bar con ViewToggle + popular chips + buscador */}
          <div className="hidden sm:flex sm:items-center sm:gap-4 sm:px-6 sm:py-2.5">

            {/* ViewToggle con indicador deslizable */}
            <ViewToggle
              options={[
                { value: "grid" as Mode, label: "Explorar", icon: <LayoutGrid className="h-3 w-3" /> },
                { value: "list" as Mode, label: "Lista", icon: <List className="h-3 w-3" /> },
              ]}
              value={mode}
              onChange={setMode}
            />

            {/* Popular chips */}
            <div className="flex flex-1 items-center gap-2 overflow-x-auto scrollbar-none">
              <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground shrink-0 select-none">
                Popular
              </span>
              {POPULAR_CHIPS.map((chip) => (
                <button
                  key={chip}
                  onClick={() => setQuery(query === chip ? "" : chip)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs font-medium whitespace-nowrap transition shrink-0",
                    query === chip
                      ? "border-amber/60 bg-amber/15 font-semibold text-ink"
                      : "border-hairline bg-transparent text-ink hover:border-ink/40 hover:bg-muted/50",
                  )}
                >
                  {chip}
                </button>
              ))}
            </div>

            {/* Buscador en la derecha del cat-bar */}
            <div className="relative shrink-0 w-56">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Buscar…"
                className="w-full rounded-full border hairline bg-surface py-1.5 pl-8 pr-7 text-sm placeholder:text-muted-foreground focus:border-amber focus:ring-[3px] focus:ring-amber/20 focus:outline-none transition"
              />
              {query && (
                <button
                  onClick={() => setQuery("")}
                  aria-label="Limpiar"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-ink"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {/* Filtro Disponibles — solo tiene efecto con fechas pickeadas */}
            <button
              type="button"
              onClick={() => setDisponiblesOnly((v) => !v)}
              className={cn(
                "shrink-0 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition whitespace-nowrap",
                disponiblesOnly
                  ? "border-[color-mix(in_oklch,var(--amber)_60%,transparent)] bg-amber-soft font-semibold text-ink"
                  : "border-hairline text-ink hover:border-ink hover:bg-muted/50",
              )}
              aria-pressed={disponiblesOnly}
              title="Mostrar solo equipos disponibles para las fechas elegidas"
            >
              <Check className="h-3 w-3" />
              Disponibles
            </button>

            {/* Contador */}
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground tabular shrink-0">
              {query.trim() || mode === "list"
                ? `${filtered.length}`
                : `${allEquipos.length}`}
            </div>
          </div>
        </div>

        {/* Loading / Error states */}
        {isLoading ? (
          mode === "list" ? (
            <div className="divide-y hairline border-t hairline mt-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-3 sm:px-6">
                  <Skeleton className="h-16 w-16 shrink-0 rounded-md" />
                  <div className="flex-1 min-w-0 space-y-1.5">
                    <Skeleton className="h-2.5 w-1/4" />
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-2.5 w-2/5" />
                  </div>
                  <Skeleton className="h-9 w-9 shrink-0 rounded-full" />
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 lg:grid-cols-4 xl:grid-cols-5 px-4 lg:px-12 mt-2">
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className="aspect-[4/5] rounded-lg border hairline overflow-hidden flex flex-col">
                  <Skeleton className="aspect-square w-full rounded-none shrink-0" />
                  <div className="flex flex-1 flex-col gap-1.5 px-2.5 py-2">
                    <Skeleton className="h-2 w-1/2" />
                    <Skeleton className="h-3 w-full" />
                    <Skeleton className="h-2 w-1/3" />
                  </div>
                </div>
              ))}
            </div>
          )
        ) : isError ? (
          <div className="mx-4 rounded-lg border hairline bg-surface px-6 py-16 text-center mt-8 lg:mx-12">
            <div className="font-display text-2xl text-muted-foreground">
              No se pudo cargar el catálogo
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              Verificá tu conexión e intentá de nuevo.
            </p>
          </div>
        ) : mode === "grid" ? (
          <GridMode
            allEquipos={allEquipos}
            apiCategories={apiCategories}
            marcas={marcas}
            selectedBrand={brand}
            onBrandSelect={(brandName) => setBrand(brandName)}
            onJumpToCategory={jumpToCategory}
            selectedCats={selectedCats}
            onClearCats={() => setSelectedCats(new Set())}
            query={query}
            disponiblesOnly={disponiblesOnly}
            getDisponible={getDisponible}
          />
        ) : (
          <ListMode
            allEquipos={allEquipos}
            apiCategories={apiCategories}
            marcas={marcas}
            query={query}
            setQuery={setQuery}
            selectedCats={selectedCats}
            toggleCat={toggleCat}
            brand={brand}
            setBrand={setBrand}
            onClear={() => {
              setSelectedCats(new Set());
              setBrand(null);
              setQuery("");
              setDisponiblesOnly(false);
            }}
            filtered={filtered}
            getDisponible={getDisponible}
            onSuggestCategory={(c) => {
              setSelectedCats(new Set([c]));
              setQuery("");
            }}
          />
        )}

        <CartDrawer allEquipos={allEquipos} getDisponible={getDisponible} />
    </PublicLayout>
  );
}

function GridMode({
  allEquipos,
  apiCategories,
  marcas,
  selectedBrand,
  onBrandSelect,
  onJumpToCategory,
  selectedCats,
  onClearCats,
  query,
  disponiblesOnly,
  getDisponible,
}: {
  allEquipos: Equipment[];
  apiCategories: string[];
  marcas: BackendMarca[];
  selectedBrand?: string | null;
  onBrandSelect: (brandName: string | null) => void;
  onJumpToCategory: (c: string) => void;
  selectedCats: Set<string>;
  onClearCats: () => void;
  query: string;
  disponiblesOnly: boolean;
  getDisponible: (item: Equipment) => number | undefined;
}) {
  const q = query.trim().toLowerCase();
  const matches = (e: Equipment) => {
    if (selectedBrand && e.brand !== selectedBrand) return false;
    if (disponiblesOnly && e.disponible !== undefined && e.disponible <= 0) return false;
    if (!q) return true;
    return (
      (e.name ?? "").toLowerCase().includes(q) ||
      (e.brand ?? "").toLowerCase().includes(q) ||
      (e.category ?? "").toLowerCase().includes(q)
    );
  };

  const isFiltered = selectedCats.size > 0 || !!selectedBrand;
  const isSearching = q.length > 0;
  // Si hay categorías seleccionadas, mostramos esas como secciones — pueden
  // ser roots o sub-cats (ej. "Montura E"). Si solo hay filtro de marca o
  // búsqueda, mostramos todas las roots del backend (matches() hace el resto).
  const visibleCategories =
    selectedCats.size > 0 ? Array.from(selectedCats) : apiCategories;

  // Una categoría puede ser root o sub-cat. Esta helper matchea contra
  // ambos: el `category` (root inferido por el mapper) y las refs en
  // `categorias` (M2M completo). Reemplaza el viejo `e.category === c`.
  const inCategory = (e: Equipment, c: string) =>
    e.category === c || (e.categorias ?? []).some((cc) => cc.nombre === c);

  // Ancho fijo de cards en carrusel para snap consistente
  const cardW = 260;

  const totalVisible = visibleCategories.reduce(
    (acc, c) => acc + allEquipos.filter((e) => inCategory(e, c) && matches(e)).length,
    0,
  );

  return (
    <div className="space-y-10 py-6 sm:space-y-12 sm:py-8 lg:py-12">
      {isFiltered && (
        <div className="px-4 lg:px-12">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Filtrando por
            </span>
            {selectedBrand && (
              <button
                onClick={() => onBrandSelect(null)}
                className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3 py-1 text-xs text-amber hover:opacity-90"
                aria-label={`Quitar filtro ${selectedBrand}`}
              >
                {selectedBrand} ×
              </button>
            )}
            {[...selectedCats].map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3 py-1 text-xs text-amber"
              >
                {c}
              </span>
            ))}
            <button
              onClick={() => { onClearCats(); onBrandSelect(null); }}
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
          categories={apiCategories}
          onSelect={onJumpToCategory}
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


      {visibleCategories.map((c) => {
        // NO re-sortear acá. allEquipos viene del backend ordenado por
        // relevancia_manual ASC, popularidad_score DESC, nombre ASC.
        // El filter preserva el orden, así que respeta el ranking automático.
        const items = allEquipos.filter((e) => inCategory(e, c) && matches(e));
        if (items.length === 0) return null;

        if (isFiltered) {
          return (
            <section key={c} id={`cat-${c}`} className="scroll-mt-40 px-4 lg:px-12">
              <div className="mb-4 flex items-end justify-between gap-3">
                <h2 className="font-display text-2xl sm:text-3xl">{c}</h2>
                <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground tabular">
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
          <div key={c} id={`cat-${c}`} className="scroll-mt-40">
            <CarouselRow
              title={c}
              count={items.length}
              action={
                !isSearching ? (
                  <button
                    onClick={() => onJumpToCategory(c)}
                    className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-ink"
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
      })}

      {isSearching && totalVisible === 0 && (
        <SearchEmptyState
          query={query}
          categories={apiCategories.slice(0, 6)}
          onSuggestCategory={onJumpToCategory}
        />
      )}
    </div>
  );
}

function SearchEmptyState({
  query,
  categories,
  onSuggestCategory,
}: {
  query: string;
  categories: string[];
  onSuggestCategory: (c: string) => void;
}) {
  return (
    <div className="px-4 lg:px-12">
      <div className="flex flex-col items-center gap-3 py-20 text-center">
        <div className="opacity-20">
          <SearchX className="h-16 w-16 text-ink" strokeWidth={1.2} />
        </div>
        <div className="font-display text-3xl font-black text-ink">Sin resultados</div>
        <div className="font-sans text-sm text-muted-foreground max-w-md">
          Ningún equipo coincide con "{query}". Probá con otro término o explorá las
          categorías populares:
        </div>
        {categories.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5 justify-center">
            {categories.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => onSuggestCategory(c)}
                className="rounded-full border border-[var(--hairline)] bg-surface px-3 py-1 text-xs font-medium text-ink hover:border-ink hover:bg-muted transition"
              >
                {c}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ListMode({
  allEquipos,
  apiCategories,
  marcas,
  query,
  setQuery,
  selectedCats,
  toggleCat,
  brand,
  setBrand,
  onClear,
  filtered,
  getDisponible,
  onSuggestCategory,
}: {
  allEquipos: Equipment[];
  apiCategories: string[];
  marcas: BackendMarca[];
  query: string;
  setQuery: (v: string) => void;
  selectedCats: Set<string>;
  toggleCat: (c: string) => void;
  brand: string | null;
  setBrand: (b: string | null) => void;
  onClear: () => void;
  filtered: Equipment[];
  getDisponible: (item: Equipment) => number | undefined;
  onSuggestCategory: (c: string) => void;
}) {
  const PAGE_SIZE = 20;
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  // Preview pane: equipo seleccionado para detalle lateral (solo desktop ≥lg).
  // Persistimos abierto/cerrado en localStorage para que el usuario no tenga
  // que reabrirlo cada visita.
  const [previewOpen, setPreviewOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    const stored = window.localStorage.getItem("rambla-preview-open");
    return stored === null ? true : stored === "true";
  });
  const [previewId, setPreviewId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("rambla-preview-open", String(previewOpen));
    }
  }, [previewOpen]);

  // Reset paging when filters/search change
  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [query, brand, selectedCats, filtered.length]);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    if (visibleCount >= filtered.length) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setVisibleCount((c) => Math.min(c + PAGE_SIZE, filtered.length));
        }
      },
      { rootMargin: "600px 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [visibleCount, filtered.length]);

  const visibleItems = filtered.slice(0, visibleCount);
  const hasMore = visibleCount < filtered.length;

  const previewItem = useMemo(
    () => (previewId ? allEquipos.find((e) => e.id === previewId) ?? null : null),
    [previewId, allEquipos],
  );

  // Auto-seleccionar el primer item visible cuando el preview está abierto
  // y todavía no hay nada elegido — así el pane no arranca vacío.
  useEffect(() => {
    if (!previewOpen) return;
    if (previewId) return;
    if (visibleItems.length === 0) return;
    setPreviewId(visibleItems[0].id);
  }, [previewOpen, previewId, visibleItems]);

  return (
    <>
      <ListFilters
        categories={apiCategories}
        brands={marcas}
        selectedCategories={selectedCats}
        onToggleCategory={toggleCat}
        selectedBrand={brand}
        onBrand={setBrand}
        onClear={onClear}
      />

      <div className="flex">
        <div className="flex-1 min-w-0 px-3 py-4 pb-28 sm:px-6 sm:py-6 sm:pb-32 lg:px-12 lg:pb-32">
          <ActiveFiltersChips
            selectedCategories={selectedCats}
            onToggleCategory={toggleCat}
            selectedBrand={brand}
            onBrand={setBrand}
            query={query}
            onQuery={setQuery}
            onClear={onClear}
          />
          {filtered.length === 0 ? (
            <SearchEmptyState
              query={query || "los filtros activos"}
              categories={apiCategories.slice(0, 6)}
              onSuggestCategory={onSuggestCategory}
            />
          ) : (
            <>
              <div
                className="space-y-1.5"
                onClickCapture={(e) => {
                  // Cuando el preview pane está abierto, click sobre una row
                  // selecciona en el pane en vez de hacer expand inline.
                  if (!previewOpen) return;
                  const target = e.target as HTMLElement;
                  // Permitir clicks en botones (add to cart, stepper) sin interferir.
                  if (target.closest("button")?.getAttribute("aria-label")?.match(/agregar|quitar|cart/i)) return;
                  const rowEl = target.closest("[id^='eq-']") as HTMLElement | null;
                  if (!rowEl) return;
                  const id = rowEl.id.slice(3);
                  if (id) {
                    e.stopPropagation();
                    e.preventDefault();
                    setPreviewId(id);
                  }
                }}
              >
                {visibleItems.map((item) => (
                  <EquipmentRow
                    key={item.id}
                    item={item}
                    disponible={getDisponible(item)}
                  />
                ))}
              </div>
              {hasMore && (
                <div
                  ref={sentinelRef}
                  className="flex items-center justify-center py-6 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground"
                >
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />Cargando más equipos…
                </div>
              )}
              {!hasMore && filtered.length > PAGE_SIZE && (
                <div className="py-6 text-center font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                  Fin del catálogo · {filtered.length} equipos
                </div>
              )}
            </>
          )}
        </div>

        <PreviewPane
          item={previewItem}
          open={previewOpen}
          onClose={() => setPreviewOpen(false)}
          onOpen={() => setPreviewOpen(true)}
          disponible={previewItem ? getDisponible(previewItem) : undefined}
        />
      </div>

      <CartMiniBar allEquipos={allEquipos} />
      <FlyToCartLayer />
    </>
  );
}
