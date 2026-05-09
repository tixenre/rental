import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { LayoutGrid, List, ArrowRight, Search, X, Sparkles, Loader2 } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { zodValidator, fallback } from "@tanstack/zod-adapter";
import { z } from "zod";
import { TopBar } from "@/components/rental/TopBar";
import { EquipmentCard } from "@/components/rental/EquipmentCard";
import { EquipmentRow } from "@/components/rental/EquipmentRow";
import { CartDrawer } from "@/components/rental/CartDrawer";
import { EquipmentDetailDialog } from "@/components/rental/EquipmentDetailDialog";
import { CartMiniBar } from "@/components/rental/CartMiniBar";
import { CarouselRow } from "@/components/rental/CarouselRow";
import { CategoryMosaic } from "@/components/rental/CategoryMosaic";
import { ListFilters } from "@/components/rental/ListFilters";
import { CategoryIllustration } from "@/components/rental/illustrations/CategoryIllustration";
import { EquipmentDetailProvider } from "@/lib/equipment-detail-context";
import { useEquipos, useDisponibilidad } from "@/hooks/useEquipos";
import { useCart } from "@/lib/cart-store";
import { type Equipment, type Category } from "@/data/equipment";
import { cn } from "@/lib/utils";

const searchSchema = z.object({
  eq: fallback(z.string().optional(), undefined),
});

export const Route = createFileRoute("/")({
  validateSearch: zodValidator(searchSchema),
  head: () => ({
    meta: [
      { title: "Rambla Rental — Alquiler de equipos de cine y foto" },
      {
        name: "description",
        content:
          "Cámaras, lentes, iluminación, audio y soportes para producciones audiovisuales. Mar del Plata.",
      },
      { property: "og:title", content: "Rambla Rental" },
      {
        property: "og:description",
        content: "Equipos de cine y foto para alquilar por jornada.",
      },
    ],
  }),
  component: Index,
});

type Mode = "grid" | "list";

function Index() {
  const { eq } = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });

  // Datos de la API
  const { data: allEquipos = [], isLoading, isError } = useEquipos();
  const { startDate, endDate } = useCart();
  const { data: disponibilidad } = useDisponibilidad(startDate, endDate);

  // Categorías y marcas derivadas de la data real de la API
  const apiCategories = useMemo(
    () => Array.from(new Set(allEquipos.map((e) => e.category))).sort(),
    [allEquipos],
  );
  const apiBrands = useMemo(
    () => Array.from(new Set(allEquipos.map((e) => e.brand).filter(Boolean))).sort(),
    [allEquipos],
  );

  const setOpenId = (id: string | null) => {
    navigate({
      search: (prev: { eq?: string }) => ({ ...prev, eq: id ?? undefined }),
      replace: true,
      resetScroll: false,
    });
  };

  const [mode, setMode] = useState<Mode>("grid");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const isMobile = window.matchMedia("(max-width: 639px)").matches;
    setMode(isMobile ? "list" : "grid");
  }, []);

  const [selectedCats, setSelectedCats] = useState<Set<string>>(new Set());
  const [brand, setBrand] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  // Scroll into view only on initial deep-link
  const shouldScrollInitialDeepLinkRef = useRef(Boolean(eq));
  const didInitialScrollRef = useRef(false);
  useEffect(() => {
    if (!shouldScrollInitialDeepLinkRef.current) return;
    if (didInitialScrollRef.current) return;
    if (!eq) return;
    didInitialScrollRef.current = true;
    requestAnimationFrame(() => {
      const el = document.getElementById(`eq-${eq}`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }, [eq]);

  // Esc cierra la fila expandida en list mode
  useEffect(() => {
    if (!eq || mode !== "list") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const trigger = document.querySelector<HTMLButtonElement>(
        `#eq-${eq} button[aria-expanded="true"]`,
      );
      setOpenId(null);
      requestAnimationFrame(() => trigger?.focus());
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eq, mode]);

  const toggleCat = (c: string) => {
    setSelectedCats((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  };

  const filtered = useMemo(() => {
    let list = allEquipos.slice();
    if (selectedCats.size > 0) list = list.filter((e) => selectedCats.has(e.category));
    if (brand) list = list.filter((e) => e.brand === brand);
    if (query.trim()) {
      const q = query.toLowerCase();
      list = list.filter(
        (e) =>
          (e.name ?? "").toLowerCase().includes(q) ||
          (e.brand ?? "").toLowerCase().includes(q) ||
          (e.category ?? "").toLowerCase().includes(q),
      );
    }
    return list;
  }, [selectedCats, brand, query, allEquipos]);

  const jumpToCategory = (c: string) => {
    setSelectedCats(new Set([c]));
    setMode("grid");
    requestAnimationFrame(() => {
      const el = document.getElementById(`cat-${c}`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      else window.scrollTo({ top: 0, behavior: "smooth" });
    });
  };

  const getDisponible = (item: Equipment) =>
    disponibilidad
      ? (disponibilidad[String(item._backendId)] ?? item.cantidad ?? 1)
      : undefined;

  return (
    <EquipmentDetailProvider value={{ openId: eq ?? null, setOpenId }}>
      <div className="min-h-screen bg-background text-foreground">
        <TopBar />

        {/* Hero amarillo brand */}
        <section className="relative overflow-hidden border-b hairline bg-amber text-ink">
          <div className="absolute inset-0 grain opacity-40" />
          <div className="relative px-6 py-12 lg:px-12 lg:py-16">
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-ink/70">
              Catálogo · {isLoading ? "…" : allEquipos.length} equipos · Mar del Plata
            </div>
            <h1 className="mt-4 wordmark text-[14vw] leading-[0.85] md:text-[7rem] lg:text-[8.5rem] text-balance">
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

            {/* CTA Estudio */}
            <div className="mt-8 inline-flex max-w-xl flex-col gap-3 rounded-2xl border border-ink/15 bg-ink/5 p-4 sm:flex-row sm:items-center sm:gap-4 sm:p-5">
              <div className="flex-1">
                <div className="inline-flex items-center gap-1.5 rounded-full bg-ink px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.25em] text-amber">
                  <Sparkles className="h-3 w-3" /> Producto estrella
                </div>
                <div className="mt-2 font-display text-xl sm:text-2xl">Conocé el Estudio</div>
                <div className="text-xs text-ink/70">
                  Foto y video · reservá por hora · pack de luces y grips opcional
                </div>
              </div>
              <Link
                to="/estudio"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-amber transition hover:bg-foreground"
              >
                Ver estudio <ArrowRight className="h-4 w-4" />
              </Link>
            </div>

            <div className="mt-6 flex flex-wrap gap-2 text-[10px] font-mono uppercase tracking-widest">
              {["calidad", "variedad", "amistad", "comunidad", "intercambio", "local"].map((w) => (
                <span key={w} className="rounded-full border border-ink/25 px-3 py-1">
                  {w}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* Toggle Modo + búsqueda sticky */}
        <div className="sticky top-[116px] sm:top-[60px] z-30 border-b hairline bg-background/95 backdrop-blur-xl">
          <div className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:gap-3 lg:px-12">
            {/* Search input */}
            <div className="relative flex-1 min-w-0 sm:max-w-xl">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Buscar equipo, marca…"
                className="w-full rounded-full border hairline bg-surface py-2 pl-9 pr-9 text-sm placeholder:text-muted-foreground focus:border-amber focus:outline-none"
              />
              {query && (
                <button
                  onClick={() => setQuery("")}
                  aria-label="Limpiar búsqueda"
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 text-muted-foreground hover:bg-foreground/10 hover:text-ink"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            <div className="flex items-center justify-between gap-3 sm:ml-auto">
              <div className="flex items-center gap-1 rounded-full border hairline p-0.5">
                <button
                  onClick={() => setMode("grid")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs uppercase tracking-wider transition",
                    mode === "grid" ? "bg-ink text-amber" : "text-muted-foreground hover:text-ink",
                  )}
                >
                  <LayoutGrid className="h-3 w-3" />
                  <span className="hidden xs:inline sm:inline">Explorar</span>
                </button>
                <button
                  onClick={() => setMode("list")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs uppercase tracking-wider transition",
                    mode === "list" ? "bg-ink text-amber" : "text-muted-foreground hover:text-ink",
                  )}
                >
                  <List className="h-3 w-3" />
                  <span className="hidden xs:inline sm:inline">Lista</span>
                </button>
              </div>
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground tabular">
                {query.trim() || mode === "list"
                  ? `${filtered.length} resultados`
                  : `${allEquipos.length} equipos`}
              </div>
            </div>
          </div>
        </div>

        {/* Loading / Error states */}
        {isLoading ? (
          <div className="flex items-center justify-center py-24 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Cargando catálogo…
          </div>
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
            onJumpToCategory={jumpToCategory}
            selectedCats={selectedCats}
            onClearCats={() => setSelectedCats(new Set())}
            query={query}
            getDisponible={getDisponible}
          />
        ) : (
          <ListMode
            allEquipos={allEquipos}
            apiCategories={apiCategories}
            apiBrands={apiBrands}
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
            }}
            filtered={filtered}
            getDisponible={getDisponible}
          />
        )}

        <CartDrawer allEquipos={allEquipos} getDisponible={getDisponible} />
        <GlobalDetailDialog allEquipos={allEquipos} mode={mode} getDisponible={getDisponible} />
      </div>
    </EquipmentDetailProvider>
  );
}

/**
 * Renders the equipment detail dialog at the route level whenever ?eq= matches
 * a known equipment. In list mode, the row expands inline so we don't open the
 * modal on top. In grid mode we always open the modal.
 */
function GlobalDetailDialog({
  allEquipos,
  mode,
  getDisponible,
}: {
  allEquipos: Equipment[];
  mode: Mode;
  getDisponible: (item: Equipment) => number | undefined;
}) {
  const { eq } = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });

  const item = eq ? allEquipos.find((e: Equipment) => e.id === eq) : undefined;
  const open = !!item && mode === "grid";

  if (!item) return null;
  return (
    <EquipmentDetailDialog
      item={item}
      open={open}
      disponible={getDisponible(item)}
      onOpenChange={(v) => {
        if (!v) {
          navigate({
            search: (prev: { eq?: string }) => ({ ...prev, eq: undefined }),
            replace: true,
          });
        }
      }}
    />
  );
}

function GridMode({
  allEquipos,
  apiCategories,
  onJumpToCategory,
  selectedCats,
  onClearCats,
  query,
  getDisponible,
}: {
  allEquipos: Equipment[];
  apiCategories: string[];
  onJumpToCategory: (c: string) => void;
  selectedCats: Set<string>;
  onClearCats: () => void;
  query: string;
  getDisponible: (item: Equipment) => number | undefined;
}) {
  const q = query.trim().toLowerCase();
  const matches = (e: Equipment) =>
    !q ||
    (e.name ?? "").toLowerCase().includes(q) ||
    (e.brand ?? "").toLowerCase().includes(q) ||
    (e.category ?? "").toLowerCase().includes(q);

  const combos = allEquipos.filter((e) => e.isCombo && matches(e));
  const isFiltered = selectedCats.size > 0;
  const isSearching = q.length > 0;
  const visibleCategories = isFiltered
    ? apiCategories.filter((c) => selectedCats.has(c))
    : apiCategories;

  // Ancho fijo de cards en carrusel para snap consistente
  const cardW = 260;

  const totalVisible = visibleCategories.reduce(
    (acc, c) => acc + allEquipos.filter((e) => e.category === c && matches(e)).length,
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
            {[...selectedCats].map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3 py-1 text-xs text-amber"
              >
                {c}
              </span>
            ))}
            <button
              onClick={onClearCats}
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

      {!isFiltered && !isSearching && combos.length > 0 && (
        <CarouselRow title="Combos" count={combos.length}>
          {combos.map((item, i) => (
            <EquipmentCard
              key={item.id}
              item={item}
              index={i}
              width={cardW + 40}
              disponible={getDisponible(item)}
            />
          ))}
        </CarouselRow>
      )}

      {visibleCategories.map((c) => {
        const items = allEquipos.filter((e) => e.category === c && matches(e));
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
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4 xl:grid-cols-5">
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
        <div className="mx-4 rounded-lg border hairline bg-surface px-6 py-16 text-center lg:mx-12">
          <div className="font-display text-2xl text-muted-foreground">Sin resultados</div>
          <p className="mt-2 text-sm text-muted-foreground">
            Probá con otro término — ningún equipo coincide con "{query}".
          </p>
        </div>
      )}

      {/* Footer mínimo */}
      <footer className="border-t hairline px-6 py-12 lg:px-12">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <div className="wordmark text-4xl text-amber">rambla</div>
            <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
              Rental · Mar del Plata
            </div>
          </div>
          <div className="flex flex-wrap gap-6 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            {(["Cámaras", "Lentes", "Iluminación", "Audio", "Soportes"] as Category[]).map((c) => (
              <div key={c} className="flex flex-col items-center gap-2 text-ink">
                <CategoryIllustration category={c} className="h-6 w-6" />
                <span>{c}</span>
              </div>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}

function ListMode({
  allEquipos,
  apiCategories,
  apiBrands,
  query,
  setQuery,
  selectedCats,
  toggleCat,
  brand,
  setBrand,
  onClear,
  filtered,
  getDisponible,
}: {
  allEquipos: Equipment[];
  apiCategories: string[];
  apiBrands: string[];
  query: string;
  setQuery: (v: string) => void;
  selectedCats: Set<string>;
  toggleCat: (c: string) => void;
  brand: string | null;
  setBrand: (b: string | null) => void;
  onClear: () => void;
  filtered: Equipment[];
  getDisponible: (item: Equipment) => number | undefined;
}) {
  const PAGE_SIZE = 20;
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

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

  return (
    <>
      <ListFilters
        query={query}
        onQuery={setQuery}
        categories={apiCategories}
        brands={apiBrands}
        selectedCategories={selectedCats}
        onToggleCategory={toggleCat}
        selectedBrand={brand}
        onBrand={setBrand}
        onClear={onClear}
      />

      <div className="px-3 py-4 pb-28 sm:px-6 sm:py-6 sm:pb-32 lg:px-12 lg:pb-32">
        {filtered.length === 0 ? (
          <div className="rounded-lg border hairline bg-surface px-6 py-16 text-center">
            <div className="font-display text-2xl text-muted-foreground">Sin resultados</div>
            <p className="mt-2 text-sm text-muted-foreground">
              Probá con otra categoría, marca o término de búsqueda.
            </p>
          </div>
        ) : (
          <>
            <div className="space-y-1.5">
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
                Cargando más equipos…
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
      <CartMiniBar allEquipos={allEquipos} />
    </>
  );
}
