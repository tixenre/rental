import { useState, useCallback, useMemo, useRef, useEffect, useLayoutEffect } from "react";
import { SlidersHorizontal, Search, User, ChevronUp, X, Calendar } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";
import { useEquipos, useMarcas, useCategorias } from "@/hooks/useEquipos";
import { useCart } from "@/lib/cart-store";
import { useShallow } from "zustand/react/shallow";
import { formatARS } from "@/lib/format";
import { useCotizacion } from "@/lib/cotizacion";
import { toLocalISO } from "@/lib/rental-dates";
import { type Equipment } from "@/data/equipment";
import { cn } from "@/lib/utils";
import { useRetomarPedido } from "@/lib/verificacion";
import { logSearch } from "@/lib/search-log";
import { filtrarOrdenar } from "@/lib/search/normalize";
import { RentalDateModal } from "@/components/rental/RentalDateModal";
import { TopBarShell } from "@/components/rental/TopBar";
import {
  HeroBanner,
  EquipmentRow,
  CartSheet,
  FichaSheet,
  BrandSheet,
  FiltrosSheet,
} from "./CatalogoMovilHelpers";

/* ── Shared styles ───────────────────────────────────────────────── */
const TABS_BG = "color-mix(in oklch, var(--background) 90%, transparent)";
const CARTBAR_BG = "color-mix(in oklch, var(--background) 96%, transparent)";

/* ── Main CatalogoMovil component ────────────────────────────────── */
export function CatalogoMovil() {
  // Equipment data
  const { data: allEquipos, isLoading, isError } = useEquipos();
  // Marcas: misma source que BrandCarousel del desktop + admin/marcas.
  // Trae logo_url, destacada, orden, popularidad_score, etc.
  const { data: marcasData } = useMarcas();
  const marcasCanonicas = useMemo(() => marcasData?.items ?? [], [marcasData?.items]);
  // Categorías canónicas (con parent_id) — usamos solo las root para los
  // cat-tabs, así no se mezclan sub-cats como "82mm" o "Montura E" que
  // aparecían cuando derivábamos del e.category del equipo.
  const { data: categoriasCanonicas = [] } = useCategorias();

  // Cart store — selector granular para evitar re-render del catálogo completo
  // ante cualquier cambio en el store (abrir drawer, cambiar fechas, etc.).
  const cart = useCart(
    useShallow((s) => ({
      items: s.items,
      add: s.add,
      remove: s.remove,
      startDate: s.startDate,
      endDate: s.endDate,
      startTime: s.startTime,
      endTime: s.endTime,
      days: s.days,
      clear: s.clear,
    })),
  );

  // Catalog state
  const [activeTab, setActiveTab] = useState("Todo");
  const [query, setQuery] = useState("");
  const [stockOnly, setStockOnly] = useState(false);
  const [selectedBrand, setSelectedBrand] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  // Date state
  // Fuente única: las fechas del alquiler viven en el cart store y las edita
  // el RentalDateModal compartido (mismo calendario que desktop). Acá solo se
  // leen para mostrarlas; la query de días bloqueados corre dentro del modal.
  const fechaDesde = cart.startDate ?? null;
  const fechaHasta = cart.endDate ?? null;
  const horaDesde = cart.startTime;
  const horaHasta = cart.endTime;
  const jornadas = cart.days();

  // Sheet state
  const [showDateSheet, setShowDateSheet] = useState(false);
  const [showCartSheet, setShowCartSheet] = useState(false);
  const [showBrandSheet, setShowBrandSheet] = useState(false);
  const [showFiltrosSheet, setShowFiltrosSheet] = useState(false);
  const [fichaEq, setFichaEq] = useState<Equipment | null>(null);

  // Al volver con ?openCarrito=1 (tras login o verificación) reabrimos el carrito
  // mobile; sigue persistido en localStorage por el cart-store. El desktop tiene
  // su propio handler en index.tsx; este hook cubre el mobile (CartSheet).
  useRetomarPedido(() => setShowCartSheet(true));

  const navigate = useNavigate();

  // Scroll state
  const scrollRef = useRef<HTMLDivElement>(null);
  const topbarRef = useRef<HTMLElement>(null);
  const heroRef = useRef<HTMLDivElement>(null);
  const searchBarRef = useRef<HTMLDivElement>(null);

  // Alturas sticky calculadas dinámicamente (no hardcodeadas).
  const [stickyTops, setStickyTops] = useState({ searchBar: 53, catTabs: 118 });

  // Medir las alturas reales de topbar y search bar para calcular los tops
  // sticky correctos (no hardcodeados, que se desalinean con safe-area reales).
  useLayoutEffect(() => {
    const topbar = topbarRef.current;
    const searchBar = searchBarRef.current;
    if (!topbar || !searchBar) return;
    const topbarHeight = topbar.offsetHeight;
    const searchBarHeight = searchBar.offsetHeight;
    setStickyTops({
      searchBar: topbarHeight,
      catTabs: topbarHeight + searchBarHeight,
    });
  }, []);

  const datePillLabel = useMemo(() => {
    if (!fechaDesde) return "Elegir fechas";
    const fmt = (d: Date) => {
      const dias = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
      return `${dias[d.getDay()]} ${d.getDate()}`;
    };
    return `${fmt(fechaDesde)} · ${fmt(fechaHasta!)}`;
  }, [fechaDesde, fechaHasta]);

  // Cat-tabs: solo roots (parent_id IS NULL) en orden del backend
  // (prioridad → popularidad → nombre). Antes derivábamos del e.category
  // pero el mapper a veces devolvía sub-cats ("82mm", "Montura E"),
  // entonces aparecían mezcladas en la barra.
  const categories = useMemo(() => {
    type Cat = { id?: number; nombre: string; parent_id?: number | null; total?: number };
    const cats = categoriasCanonicas as Cat[];
    const roots = cats
      .filter((c) => c.parent_id == null && (c.total ?? 0) > 0)
      .map((c) => c.nombre);
    return ["Todo", ...roots];
  }, [categoriasCanonicas]);

  // Brands para el sheet: parte del catálogo canónico (useMarcas, misma
  // source que BrandCarousel del desktop y /admin/equipos/marcas) y le
  // agrega el count en la categoría activa. Filtra las que no tienen
  // ningún equipo en la cat seleccionada (sino al clickearlas el listado
  // queda vacío). Orden: destacadas primero (por orden manual del admin),
  // resto alfabético.
  const brands = useMemo(() => {
    const counts = new Map<string, number>();
    for (const e of allEquipos) {
      if (!e.brand) continue;
      const inTab =
        activeTab === "Todo" ||
        e.category === activeTab ||
        (e.categorias ?? []).some((c) => c.nombre === activeTab);
      if (!inTab) continue;
      const k = e.brand.toLowerCase();
      counts.set(k, (counts.get(k) ?? 0) + 1);
    }

    const enriched = marcasCanonicas
      .map((m) => ({
        nombre: m.nombre,
        logo_url: m.logo_url ?? null,
        destacada: !!m.destacada,
        orden: m.orden ?? 100,
        count: counts.get(m.nombre.toLowerCase()) ?? 0,
      }))
      .filter((m) => m.count > 0);

    enriched.sort((a, b) => {
      if (a.destacada !== b.destacada) return a.destacada ? -1 : 1;
      if (a.destacada && b.destacada) return a.orden - b.orden;
      return a.nombre.localeCompare(b.nombre, "es");
    });

    return enriched;
  }, [allEquipos, activeTab, marcasCanonicas]);

  // Filtered equipment
  // Helper: matchea el activeTab contra el root del equipo o su M2M.
  // useCallback keyed en activeTab → identidad estable salvo cambio de tab,
  // así puede entrar en las deps del useMemo de filteredEquipos sin invalidarlo
  // en cada render (conducta idéntica: el filtrado ya dependía de activeTab).
  const matchesActiveTab = useCallback(
    (e: Equipment): boolean => {
      if (activeTab === "Todo") return true;
      if (e.category === activeTab) return true;
      return (e.categorias ?? []).some((c) => c.nombre === activeTab);
    },
    [activeTab],
  );

  const filteredEquipos = useMemo(() => {
    const list = allEquipos.filter((e) => {
      const matchCat = matchesActiveTab(e);
      const matchStock = !stockOnly || e.cantidad == null || e.cantidad > 0;
      const matchBrand = !selectedBrand || e.brand === selectedBrand;
      return matchCat && matchStock && matchBrand;
    });
    // Motor de búsqueda compartido (espejo del backend): sin tildes, sin
    // guiones, multi-palabra y ordenado por relevancia. Mismo comportamiento
    // que el catálogo desktop.
    if (!query.trim()) return list;
    return filtrarOrdenar(list, query, (e) => ({
      nombre: e.name,
      extra: [e.brand, e.category, e.description ?? ""].join(" "),
    }));
  }, [allEquipos, matchesActiveTab, query, stockOnly, selectedBrand]);

  // Analítica interna: registra qué busca la gente (con cuántos resultados vio).
  // Mismo módulo único que el catálogo desktop (debounce + dedupe adentro).
  useEffect(() => {
    logSearch(query, filteredEquipos.length);
  }, [query, filteredEquipos.length]);

  // Filtros activos (para el badge del botón "Filtros"). Excluye categoría
  // (esa la elige el tab) y búsqueda (esa tiene su propio input visible).
  const activeFiltersCount = (stockOnly ? 1 : 0) + (selectedBrand ? 1 : 0);

  // Cart totals — el TOTAL lo calcula el BACKEND (fuente única /api/cotizar),
  // igual que el drawer: incluye el descuento del cliente y el IVA. El reduce
  // client-side anterior mostraba el BRUTO (precio × jornadas, sin descuento) →
  // no coincidía con el carrito ni con el pedido real (#967).
  const totalItems = Object.values(cart.items).reduce((s, q) => s + q, 0);
  const cotizarItems = Object.entries(cart.items)
    .map(([id, q]) => {
      const eq = allEquipos?.find((e) => e.id === id);
      return eq ? { equipoId: eq._backendId ?? Number(eq.id), cantidad: q } : null;
    })
    .filter((x): x is { equipoId: number; cantidad: number } => x !== null);
  const hayFechas = !!(fechaDesde && fechaHasta);
  const { totalNeto: cartTotal, conIva: cartConIva } = useCotizacion({
    items: cotizarItems,
    fechaDesde: hayFechas ? toLocalISO(fechaDesde, horaDesde) : null,
    fechaHasta: hayFechas ? toLocalISO(fechaHasta, horaHasta) : null,
  }).data;

  const handleAddToCart = useCallback(
    (id: string, delta: number) => {
      if (delta > 0) cart.add(id);
      else cart.remove(id);
    },
    [cart],
  );

  const handleRowTap = useCallback((id: string) => {
    setExpanded((prev) => (prev === id ? null : id));
  }, []);

  const handleTabChange = useCallback((cat: string) => {
    setActiveTab(cat);
    setExpanded(null);
  }, []);

  // Height of compact search (used for category tabs top offset)
  // Cat-tabs sticky: calculadas dinámicamente para usar alturas reales
  // (no hardcodeadas, que varían con safe-area y padding real del topbar).
  // Nota: el topbar tiene padding-top dinámico (safe-area-inset-top),
  // así que 53px es una aproximación que falla en algunos devices.

  // h-dvh (dynamic viewport) respeta la URL bar de safari iOS — antes
  // h-screen dejaba el cart-bar tapado cuando safari mostraba su UI.
  return (
    <div className="flex flex-col h-dvh overflow-hidden bg-background relative">
      {/* Scroll container */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto overflow-x-hidden"
        style={{ WebkitOverflowScrolling: "touch", scrollbarWidth: "none" }}
      >
        {/* TopBar unificado (mismo shell que desktop / estudio / talleres):
            bg-amber, isologo + date pill central. El acceso cliente y la
            navegación entre áreas viven en el menú (AreaMenu, lo agrega el shell). */}
        <TopBarShell
          section="rental"
          headerRef={topbarRef}
          center={
            <button
              className="flex min-h-[44px] w-full items-center justify-center gap-1.5 rounded-full bg-background px-3.5 py-1.5 font-sans text-sm font-semibold text-ink transition whitespace-nowrap hover:bg-background/90"
              onClick={() => setShowDateSheet(true)}
            >
              <Calendar size={14} className="shrink-0 text-amber" />
              <span>{datePillLabel}</span>
              {fechaDesde && (
                <span className="font-mono text-xs uppercase tracking-[0.2em] text-ink/60">
                  · {jornadas} jorn.
                </span>
              )}
            </button>
          }
        />

        {/* Hero banner amber — eyebrow + headline brand + CTA. */}
        <HeroBanner
          heroRef={heroRef}
          equipCount={allEquipos?.length ?? 0}
          onDateOpen={() => setShowDateSheet(true)}
        />

        {/* Búsqueda — sticky bajo el topbar. */}
        <div
          ref={searchBarRef}
          className="sticky z-[39] px-4 py-2 backdrop-blur"
          style={{ top: stickyTops.searchBar, background: TABS_BG }}
        >
          <div className="relative">
            <Search
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
            />
            <input
              className="w-full rounded-[var(--radius-lg)] border-[1.5px] border-hairline bg-surface font-sans text-sm py-[11px] pl-[38px] pr-9 text-ink placeholder:text-muted-foreground outline-none transition-all focus:border-amber"
              style={{ fontFamily: "var(--font-sans)" }}
              aria-label="Buscar equipos"
              placeholder="Buscar equipo, marca, pack…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                aria-label="Limpiar búsqueda"
                className="absolute right-2 top-1/2 -translate-y-1/2 grid h-6 w-6 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-ink transition-colors"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Category tabs — calculado dinámicamente, directo bajo search bar */}
        <div
          className="sticky z-[39] border-b border-hairline backdrop-blur transition-[top] duration-150"
          style={{
            top: stickyTops.catTabs,
            background: TABS_BG,
          }}
        >
          <div
            className="flex overflow-x-auto px-4 py-1"
            style={{ scrollbarWidth: "none", gap: 0 }}
          >
            {categories.map((cat) => {
              const count =
                cat === "Todo"
                  ? allEquipos.length
                  : allEquipos.filter(
                      (e) =>
                        e.category === cat || (e.categorias ?? []).some((c) => c.nombre === cat),
                    ).length;
              return (
                <button
                  key={cat}
                  className={cn(
                    "flex min-h-[44px] items-center gap-1 py-[10px] pb-[9px] px-3 whitespace-nowrap shrink-0 border-b-[2.5px] transition-all",
                    activeTab === cat ? "border-amber" : "border-transparent",
                  )}
                  onClick={() => handleTabChange(cat)}
                >
                  <span
                    className={cn(
                      "font-sans text-sm leading-none",
                      activeTab === cat
                        ? "font-bold text-ink"
                        : "font-medium text-muted-foreground",
                    )}
                  >
                    {cat}
                  </span>
                  <span className="font-mono text-2xs tracking-[0.15em] text-muted-foreground leading-none">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Filter row */}
        <div className="flex items-center gap-1.5 px-4 py-2">
          <button
            className={cn(
              "flex min-h-[44px] items-center gap-1.5 px-[11px] py-[5px] rounded-full border font-sans text-xs font-medium text-ink transition-all",
              stockOnly
                ? "bg-amber-soft border-amber/60 font-semibold"
                : "border-hairline bg-transparent hover:border-ink hover:bg-muted",
            )}
            onClick={() => setStockOnly((s) => !s)}
          >
            {stockOnly && (
              <svg
                width="10"
                height="10"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
              >
                <path d="M20 6L9 17l-5-5" />
              </svg>
            )}
            Disponibles
          </button>
          <button
            type="button"
            onClick={() => setShowBrandSheet(true)}
            className={cn(
              "flex min-h-[44px] items-center gap-1.5 px-[11px] py-[5px] rounded-full border font-sans text-xs font-medium text-ink transition-all",
              selectedBrand
                ? "bg-amber-soft border-amber/60 font-semibold"
                : "border-hairline bg-transparent hover:border-ink hover:bg-muted",
            )}
          >
            {selectedBrand ?? "Marca"} ▾
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={() => setShowFiltrosSheet(true)}
            className={cn(
              "relative flex min-h-[44px] items-center gap-1.5 px-[11px] py-[5px] rounded-full border font-sans text-xs font-medium transition-all",
              activeFiltersCount > 0
                ? "border-ink text-ink"
                : "border-hairline text-muted-foreground hover:border-ink hover:text-ink",
            )}
          >
            <SlidersHorizontal size={11} />
            Filtros
            {activeFiltersCount > 0 && (
              <span className="inline-flex h-[14px] min-w-[14px] items-center justify-center rounded-full bg-ink px-1 font-mono text-2xs font-bold text-amber">
                {activeFiltersCount}
              </span>
            )}
          </button>
        </div>

        {/* Equipment list — paddingBottom respeta safe-area-inset-bottom
            de iOS para que cuando no hay cart bar visible, el último item
            no quede tapado por el home indicator. */}
        <div
          className="flex flex-col px-4"
          style={{ paddingBottom: "calc(120px + env(safe-area-inset-bottom))" }}
        >
          {isLoading && (
            <div className="text-center py-8 text-muted-foreground font-sans text-sm">
              Cargando equipos…
            </div>
          )}
          {/* Error de carga (API caída): mensaje propio, no "sin resultados"
              (que sugiere que el filtro no matcheó). Espeja el isError del desktop. */}
          {!isLoading && isError && (
            <div className="text-center py-8 px-4 text-muted-foreground font-sans text-sm">
              No se pudo cargar el catálogo. Revisá tu conexión e intentá de nuevo.
            </div>
          )}
          {!isLoading && !isError && filteredEquipos.length === 0 && (
            <div className="text-center py-8 text-muted-foreground font-sans text-sm">
              Sin resultados. Probá con otra categoría o término.
            </div>
          )}
          {filteredEquipos.map((eq) => (
            <EquipmentRow
              key={eq.id}
              eq={eq}
              inCart={cart.items[eq.id] ?? 0}
              isExpanded={expanded === eq.id}
              jornadas={jornadas}
              fechaDesde={fechaDesde}
              onTap={() => handleRowTap(eq.id)}
              onAdd={(delta) => handleAddToCart(eq.id, delta)}
              onFicha={() => setFichaEq(eq)}
            />
          ))}
        </div>

        {/* CartMiniBar — paddingBottom respeta env(safe-area-inset-bottom)
            para que el home indicator de iPhone no tape el contenido. */}
        {totalItems > 0 && (
          <div
            role="button"
            tabIndex={0}
            aria-label={`Ver tu rental: ${totalItems} ${totalItems === 1 ? "ítem" : "ítems"}, total ${formatARS(cartTotal)}`}
            className="sticky bottom-0 z-40 flex items-center gap-2.5 px-4 cursor-pointer border-t-[1.5px] border-amber backdrop-blur-lg transition-colors hover:bg-amber/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-inset"
            style={{
              background: CARTBAR_BG,
              boxShadow: "0 -8px 24px -8px rgba(0,0,0,0.12)",
              paddingTop: 10,
              paddingBottom: "max(14px, calc(env(safe-area-inset-bottom) + 8px))",
              animation: "slide-up 0.2s cubic-bezier(.32,.72,0,1)",
              WebkitTapHighlightColor: "transparent",
            }}
            onClick={() => setShowCartSheet(true)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setShowCartSheet(true);
              }
            }}
          >
            <div className="flex-1">
              <div className="font-sans text-sm font-bold text-ink leading-tight">
                {totalItems} {totalItems === 1 ? "ítem" : "ítems"}
              </div>
              <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground mt-0.5">
                {fechaDesde ? `${jornadas} jornadas` : "elegí fechas"}
              </div>
            </div>
            <div className="flex-1" />
            <div className="text-right">
              <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground">
                Total
              </div>
              <div
                className="font-mono font-bold text-ink leading-none"
                style={{ fontSize: 18, fontVariantNumeric: "tabular-nums" }}
              >
                {formatARS(cartTotal)}
                {cartConIva && (
                  <span className="text-xs font-normal text-muted-foreground"> + IVA</span>
                )}
              </div>
            </div>
            <ChevronUp
              size={16}
              className="text-muted-foreground hover:text-ink transition-colors shrink-0"
            />
          </div>
        )}
      </div>

      {/* Sheets */}
      {fichaEq && (
        <FichaSheet
          eq={fichaEq}
          onClose={() => setFichaEq(null)}
          onAddToCart={handleAddToCart}
          inCart={cart.items[fichaEq.id] ?? 0}
          jornadas={jornadas}
          fechaDesde={fechaDesde}
        />
      )}
      <RentalDateModal open={showDateSheet} onOpenChange={setShowDateSheet} />
      {showCartSheet && (
        <CartSheet
          onClose={() => setShowCartSheet(false)}
          onOpenDateSheet={() => setShowDateSheet(true)}
          equipos={allEquipos}
          cartItems={cart.items}
          jornadas={jornadas}
          fechaDesde={fechaDesde}
          fechaHasta={fechaHasta}
          horaDesde={horaDesde}
          horaHasta={horaHasta}
        />
      )}
      <BrandSheet
        open={showBrandSheet}
        onOpenChange={setShowBrandSheet}
        brands={brands}
        selected={selectedBrand}
        onSelect={setSelectedBrand}
      />
      <FiltrosSheet
        open={showFiltrosSheet}
        onOpenChange={setShowFiltrosSheet}
        stockOnly={stockOnly}
        onStockToggle={() => setStockOnly((v) => !v)}
        selectedBrand={selectedBrand}
        onBrandClear={() => setSelectedBrand(null)}
        onOpenBrandSheet={() => {
          setShowFiltrosSheet(false);
          setShowBrandSheet(true);
        }}
        activeFiltersCount={activeFiltersCount}
        onClearAll={() => {
          setStockOnly(false);
          setSelectedBrand(null);
          setShowFiltrosSheet(false);
        }}
      />
    </div>
  );
}
