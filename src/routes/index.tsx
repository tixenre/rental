import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { useQuery } from "@tanstack/react-query";
import { CatalogoMovil } from "@/components/rental/mobile/CatalogoMovil";
import {
  LayoutGrid,
  List,
  ArrowRight,
  Sparkles,
  Loader2,
  Search,
  X,
  Check,
  SearchX,
} from "lucide-react";
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
import { SpecFilters } from "@/components/rental/SpecFilters";
import {
  useEquipos,
  useCategorias,
  useMarcas,
  discoverFilterableSpecs,
  type SpecFilterDef,
} from "@/hooks/useEquipos";
import type { BackendMarca, BackendCategoria } from "@/lib/api";
import { HERO_TAGLINES_DEFAULT, parseHeroTaglines } from "@/lib/hero-taglines";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

const POPULAR_CHIPS = [
  "Pack boda",
  "Pack entrevista",
  "Sony FX3",
  "Aputure 600d",
  "RØDE NTG",
  "Pack 3 LEDs",
  "Manfrotto",
];

type IndexSearch = {
  /** Modo de visualización compartible por URL. `?view=grid` o `?view=list`. */
  view?: "grid" | "list";
  /** Pre-filtra el catálogo por una categoría (root o sub-cat). Se usa para
   *  deep-linking desde la página de detalle u otros entry points. */
  cat?: string;
};

const SITE_URL = "https://ramblarental.com";

async function fetchOgImage(): Promise<string> {
  try {
    const res = await fetch("/api/settings/og_image_url");
    if (!res.ok) return `${SITE_URL}/icon-512.png`;
    const data = await res.json();
    const url = (data?.value as string) || "";
    if (!url) return `${SITE_URL}/icon-512.png`;
    return url.startsWith("http") ? url : `${SITE_URL}${url}`;
  } catch {
    return `${SITE_URL}/icon-512.png`;
  }
}

export const Route = createFileRoute("/")({
  validateSearch: (search: Record<string, unknown>): IndexSearch => {
    const v = search.view;
    const c = search.cat;
    return {
      view: v === "grid" || v === "list" ? v : undefined,
      cat: typeof c === "string" && c.trim() ? c.trim() : undefined,
    };
  },
  loader: async ({ context }) => {
    // Cachea por 5 min para no pegarle al backend en cada render.
    const ctx = context as {
      queryClient?: {
        fetchQuery: <T>(opts: {
          queryKey: unknown[];
          queryFn: () => Promise<T>;
          staleTime?: number;
        }) => Promise<T>;
      };
    };
    const ogImage = ctx.queryClient
      ? await ctx.queryClient.fetchQuery({
          queryKey: ["settings", "og_image_url"],
          queryFn: fetchOgImage,
          staleTime: 5 * 60 * 1000,
        })
      : await fetchOgImage();
    return { ogImage };
  },
  head: ({ loaderData }) => {
    const data = loaderData as { ogImage: string } | undefined;
    const ogImage = data?.ogImage ?? `${SITE_URL}/icon-512.png`;
    return {
      meta: [
        { title: "Rambla Rental — Alquiler de equipos de cine y foto en Mar del Plata" },
        {
          name: "description",
          content:
            "Cámaras, lentes, iluminación, audio y soportes para producciones audiovisuales. Estudio de foto y video en Mar del Plata.",
        },
        // Open Graph (Facebook, WhatsApp, LinkedIn).
        { property: "og:type", content: "website" },
        { property: "og:url", content: `${SITE_URL}/` },
        { property: "og:title", content: "Rambla Rental — Alquiler de equipos de cine y foto" },
        {
          property: "og:description",
          content: "Cámaras, lentes, iluminación, audio y soportes. Estudio en Mar del Plata.",
        },
        { property: "og:image", content: ogImage },
        { property: "og:image:width", content: "1200" },
        { property: "og:image:height", content: "630" },
        { property: "og:locale", content: "es_AR" },
        // Twitter Cards.
        { name: "twitter:card", content: "summary_large_image" },
        { name: "twitter:title", content: "Rambla Rental" },
        { name: "twitter:description", content: "Equipos audiovisuales · Mar del Plata" },
        { name: "twitter:image", content: ogImage },
      ],
      links: [{ rel: "canonical", href: `${SITE_URL}/` }],
      scripts: [
        // WebSite + SearchAction: Google muestra una caja de búsqueda inline
        // en los resultados cuando se busca el nombre de la marca, llevando
        // directo al buscador del catálogo (`/?q=...`).
        {
          type: "application/ld+json",
          children: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebSite",
            name: "Rambla Rental",
            url: `${SITE_URL}/`,
            potentialAction: {
              "@type": "SearchAction",
              target: `${SITE_URL}/?q={search_term_string}`,
              "query-input": "required name=search_term_string",
            },
          }),
        },
      ],
    };
  },
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

  const { data: taglinesData } = useQuery({
    queryKey: ["settings", "hero_taglines"],
    queryFn: async () => {
      try {
        const res = await fetch("/api/settings/hero_taglines");
        if (!res.ok) return HERO_TAGLINES_DEFAULT;
        const d = await res.json();
        return parseHeroTaglines(d.value as string);
      } catch {
        return HERO_TAGLINES_DEFAULT;
      }
    },
    staleTime: 5 * 60 * 1000,
  });
  const taglines = taglinesData ?? HERO_TAGLINES_DEFAULT;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const taglineIdx = useMemo(() => Math.floor(Math.random() * 4), []);
  const tagline = taglines[taglineIdx % taglines.length];

  // Categorías derivadas, ordenadas por prioridad del backend.
  // Las que no aparecen en /api/categorias quedan al final, alfabéticas.
  const apiCategories = useMemo(() => {
    // Set de nombres visibles (todos los niveles) según el backend, que ya
    // filtra `visible=TRUE` en /api/categorias. El mosaico/tabs muestran solo
    // categorías que (a) tienen equipos y (b) están marcadas visibles. El
    // admin las cura desde la solapa Diseño. Si todavía no cargó el árbol
    // (`backendCats` vacío), no filtramos para evitar un flash sin tiles.
    const visibleNames = new Set<string>();
    const walk = (nodes: BackendCategoria[]) => {
      nodes.forEach((n) => {
        visibleNames.add(n.nombre);
        if (n.children?.length) walk(n.children);
      });
    };
    walk(backendCats);

    let cats = Array.from(new Set(allEquipos.map((e) => e.category)));
    if (visibleNames.size > 0) {
      cats = cats.filter((c) => visibleNames.has(c));
    }
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
    typeof window !== "undefined" && window.matchMedia?.("(max-width: 639px)").matches
      ? "list"
      : "grid";
  const mode: Mode = search.view ?? defaultMode;
  const setMode = (m: Mode) => {
    navigate({
      search: (prev) => ({ ...prev, view: m }),
      replace: true,
    });
  };

  /** Filtros por specs estructuradas (Fase H). Mapeo
   *  `spec_key → value seleccionado`. Solo se aplican si el equipo
   *  pertenece a la categoría que tiene esa spec en el template. */
  const [specFilters, setSpecFilters] = useState<Record<string, string>>({});
  const [selectedCats, setSelectedCats] = useState<Set<string>>(() =>
    search.cat ? new Set([search.cat]) : new Set(),
  );
  const [brand, setBrand] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  // Filtro "Disponibles": esconde equipos con disponible === 0 (sin stock
  // para las fechas pickeadas). Solo tiene efecto cuando hay rango de fechas
  // — sin fechas, `disponible` queda undefined y todos pasan.
  const [disponiblesOnly, setDisponiblesOnly] = useState(false);
  // Scroll-feel: `scrolled` se activa cuando el hero se tiñó >65% (mismo
  // umbral que el snap del topbar) → retinta el cat-bar para que combine con
  // el topbar amber. `spyCat` resalta el tab de la categoría en viewport
  // (scroll-spy) en modo browse, sin filtrar.
  const [scrolled, setScrolled] = useState(false);
  const [spyCat, setSpyCat] = useState<string | null>(null);

  const toggleCat = (c: string) => {
    setSelectedCats((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  };

  // Counts por categoría. Pre-buildeo un Map en una sola pasada en lugar
  // de hacer `allEquipos.filter(...)` dentro del `.map()` de tabs — eso
  // era O(equipos × categorías). Con ~120 equipos × ~15 cats eran 1800
  // operaciones en cada render.
  const categoryCounts = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of allEquipos) {
      const seen = new Set<string>();
      if (e.category) seen.add(e.category);
      for (const c of e.categorias ?? []) {
        if (c.nombre) seen.add(c.nombre);
      }
      for (const cat of seen) {
        map.set(cat, (map.get(cat) ?? 0) + 1);
      }
    }
    return map;
  }, [allEquipos]);

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
    // Filtros por specs estructuradas (Fase H): match exacto del value
    // contra `equipo.specsRaw[key].value`. Si el equipo no tiene esa
    // spec (porque no está en su template de categoría), no matchea.
    const activeSpecFilters = Object.entries(specFilters).filter(([, v]) => v);
    if (activeSpecFilters.length > 0) {
      list = list.filter((eq) => {
        const specs = eq.specsRaw || {};
        return activeSpecFilters.every(([key, value]) => {
          const sp = specs[key];
          return sp && String(sp.value).trim() === value;
        });
      });
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
  }, [selectedCats, brand, query, disponiblesOnly, allEquipos, specFilters]);

  // Specs filtrables — descubiertas del subset cat/brand/query (sin
  // aplicar spec-filters todavía, para que los valores disponibles no
  // desaparezcan al elegir uno).
  const filterableSpecs = useMemo(() => {
    const base = allEquipos.filter((e) => {
      if (selectedCats.size > 0) {
        const inCat =
          selectedCats.has(e.category) ||
          (e.categorias ?? []).some((c) => selectedCats.has(c.nombre));
        if (!inCat) return false;
      }
      if (brand && e.brand !== brand) return false;
      return true;
    });
    return discoverFilterableSpecs(base);
  }, [allEquipos, selectedCats, brand]);

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
      setScrolled((prev) => (prev === pct >= 65 ? prev : pct >= 65));
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => {
      window.removeEventListener("scroll", onScroll);
      document.documentElement.style.setProperty("--amber-pct", "0%");
    };
  }, []);

  // Scroll-spy: en modo browse (grid, sin filtro ni búsqueda) resalta el tab
  // de la categoría que está en viewport. No filtra — solo actualiza `spyCat`.
  const browseMode = mode === "grid" && selectedCats.size === 0 && !query.trim();
  useEffect(() => {
    if (!browseMode) {
      setSpyCat(null);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const cat = (entry.target as HTMLElement).dataset.cat;
            if (cat) setSpyCat(cat);
          }
        }
      },
      { rootMargin: "-40% 0px -55% 0px" },
    );
    const sections = document.querySelectorAll("[data-cat-section]");
    sections.forEach((s) => observer.observe(s));
    return () => observer.disconnect();
  }, [browseMode, allEquipos.length]);

  return (
    <PublicLayout topBar={{ amberOnScroll: true }}>
      <ViewIntroDialog onPick={(m) => setMode(m)} />
      {/* Hero amarillo brand */}
      <section
        ref={heroRef}
        className="relative overflow-hidden border-b hairline bg-amber text-ink"
      >
        <div className="absolute inset-0 grain opacity-40" />
        <div className="relative px-6 py-12 lg:px-12 lg:py-16">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] sm:tracking-[0.3em] text-ink/70 break-words">
            Catálogo · {isLoading ? "…" : allEquipos.length} equipos · Mar del Plata
          </div>
          <h1 className="mt-4 wordmark text-5xl sm:text-7xl md:text-[7rem] lg:text-[8.5rem] leading-[0.9] md:leading-[0.85] text-balance break-words">
            {tagline[0]}
            <br />
            {tagline[1]}
          </h1>
          <p className="mt-6 max-w-xl text-base text-ink/80">
            Cámaras, ópticas, luces, audio y soportes para producciones audiovisuales. Elegí fechas
            y armá tu pedido — te lo dejamos listo para retirar.
          </p>

          {/* CTA Estudio — protagonista del banner */}
          <div className="mt-10 inline-flex max-w-2xl flex-col gap-4 rounded-3xl border-2 border-ink bg-ink p-6 sm:flex-row sm:items-center sm:gap-6 sm:p-7 shadow-lg">
            <div className="flex-1">
              <div className="inline-flex items-center gap-1.5 rounded-full bg-amber px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.25em] text-ink">
                <Sparkles className="h-3 w-3" /> Espacio Rambla
              </div>
              <div className="mt-3 font-display text-2xl sm:text-3xl text-amber">
                Conocé el Estudio
              </div>
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

      {/* Toggle Modo + búsqueda sticky. Al scrollear >65% (mismo umbral que
            el snap del topbar) se retinta de amber soft para combinar con el
            topbar teñido en vez de quedar como una barra blanca "rota". */}
      <div
        className="sticky top-16 z-30 border-b hairline backdrop-blur-xl transition-colors"
        style={{
          background: scrolled
            ? "color-mix(in oklch, var(--amber) 20%, var(--background))"
            : "var(--background)",
        }}
      >
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
              setSpecFilters({});
            }}
            resultCount={filtered.length}
          />
        </div>

        {/* Desktop: cat-bar 2 filas (toggle+buscador / cat-tabs+disponibles)
              siguiendo design handoff. Popular chips en su propia fila debajo
              (solo en modo lista). */}
        <div className="hidden sm:block">
          {/* Fila 1: ViewToggle (izq) + Buscador (der) */}
          <div className="flex items-center gap-4 px-6 py-2.5 border-b hairline">
            <ViewToggle
              options={[
                { value: "grid" as Mode, label: "Grid", icon: <LayoutGrid className="h-3 w-3" /> },
                { value: "list" as Mode, label: "Lista", icon: <List className="h-3 w-3" /> },
              ]}
              value={mode}
              onChange={setMode}
            />

            {/* Buscador protagonista — crece hasta 520px y se alinea a la
                  derecha (design handoff §3.1). */}
            <div className="relative ml-auto w-full max-w-[520px]">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Buscar equipo, marca o categoría…"
                className="w-full rounded-full border border-ink/15 bg-surface-elevated py-2.5 pl-11 pr-9 text-sm font-medium shadow-sm placeholder:font-normal placeholder:text-muted-foreground focus:border-amber focus:ring-[3px] focus:ring-amber/20 focus:outline-none transition"
              />
              {query && (
                <button
                  onClick={() => setQuery("")}
                  aria-label="Limpiar"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-ink"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Fila 2: Cat-tabs (izq, scroll horizontal) + Disponibles (der) */}
          <div className="flex items-center gap-3 pl-4 pr-6 overflow-x-auto scrollbar-none">
            <div className="flex shrink-0">
              {["Todo", ...apiCategories].map((cat) => {
                // En browse mode el highlight sigue al scroll-spy (spyCat),
                // sin filtrar; al filtrar/buscar vuelve a basarse en selectedCats.
                const isActive = browseMode
                  ? cat === (spyCat ?? "Todo")
                  : cat === "Todo"
                    ? selectedCats.size === 0
                    : selectedCats.has(cat);
                const count = cat === "Todo" ? allEquipos.length : (categoryCounts.get(cat) ?? 0);
                return (
                  <button
                    key={cat}
                    onClick={() => {
                      if (cat === "Todo") setSelectedCats(new Set());
                      else setSelectedCats(new Set([cat]));
                    }}
                    className={cn(
                      "flex items-baseline gap-1.5 px-3.5 pt-2.5 pb-2 whitespace-nowrap shrink-0 border-b-[2.5px] transition",
                      isActive ? "border-amber" : "border-transparent hover:border-hairline",
                    )}
                  >
                    <span
                      className={cn(
                        "font-sans text-sm",
                        isActive ? "font-bold text-ink" : "font-medium text-muted-foreground",
                      )}
                    >
                      {cat}
                    </span>
                    <span className="font-mono text-[9px] tracking-[0.1em] text-muted-foreground tabular">
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="flex-1 min-w-2" />

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
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground tabular shrink-0 pl-1">
              {query.trim() || mode === "list" ? `${filtered.length}` : `${allEquipos.length}`}
            </div>
          </div>
        </div>
      </div>

      {/* Popular bar — fila separada bajo el cat-bar, solo en modo lista.
            No sticky: scrollea fuera con el contenido (mismo patrón que el
            móvil — los populares no tienen sentido después de empezar a
            scrollear). */}
      {mode === "list" && (
        <div className="hidden sm:flex items-center gap-2 px-6 py-2 border-b hairline bg-background overflow-x-auto scrollbar-none">
          <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground shrink-0">
            Populares:
          </span>
          {POPULAR_CHIPS.map((chip) => (
            <button
              key={chip}
              onClick={() => setQuery(query === chip ? "" : chip)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium whitespace-nowrap transition shrink-0",
                query === chip
                  ? "border-amber/60 bg-amber/15 font-semibold text-ink"
                  : "border-hairline bg-surface text-ink hover:border-ink/40 hover:bg-muted/50",
              )}
            >
              {chip}
            </button>
          ))}
        </div>
      )}

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
              <div
                key={i}
                className="aspect-[4/5] rounded-lg border hairline overflow-hidden flex flex-col"
              >
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
            setSpecFilters({});
            setDisponiblesOnly(false);
          }}
          filtered={filtered}
          getDisponible={getDisponible}
          onSuggestCategory={(c) => {
            setSelectedCats(new Set([c]));
            setQuery("");
          }}
          filterableSpecs={filterableSpecs}
          specFilters={specFilters}
          setSpecFilters={setSpecFilters}
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
  const visibleCategories = selectedCats.size > 0 ? Array.from(selectedCats) : apiCategories;

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
              onClick={() => {
                onClearCats();
                onBrandSelect(null);
              }}
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
          getCount={(c) => allEquipos.filter((e) => inCategory(e, c)).length}
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
          <div key={c} id={`cat-${c}`} data-cat-section data-cat={c} className="scroll-mt-40">
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
          Ningún equipo coincide con "{query}". Probá con otro término o explorá las categorías
          populares:
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
  filterableSpecs,
  specFilters,
  setSpecFilters,
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
  filterableSpecs: SpecFilterDef[];
  specFilters: Record<string, string>;
  setSpecFilters: Dispatch<SetStateAction<Record<string, string>>>;
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
    () => (previewId ? (allEquipos.find((e) => e.id === previewId) ?? null) : null),
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
          {/* Filtros dinámicos por specs estructuradas (Fase H).
              Solo aparece si el dataset filtrado por cat/brand tiene
              specs con `en_filtros=true` y 2+ valores únicos. */}
          {filterableSpecs.length > 0 && (
            <div className="mb-3 rounded-lg border hairline bg-card/40 p-3">
              <SpecFilters
                filterableSpecs={filterableSpecs}
                selected={specFilters}
                onChange={(key, value) => {
                  setSpecFilters((prev) => {
                    const next = { ...prev };
                    if (value == null) delete next[key];
                    else next[key] = value;
                    return next;
                  });
                }}
                layout="stacked"
              />
            </div>
          )}
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
                  if (
                    target
                      .closest("button")
                      ?.getAttribute("aria-label")
                      ?.match(/agregar|quitar|cart/i)
                  )
                    return;
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
                  <EquipmentRow key={item.id} item={item} disponible={getDisponible(item)} />
                ))}
              </div>
              {hasMore && (
                <div
                  ref={sentinelRef}
                  className="flex items-center justify-center py-6 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground"
                >
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
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
