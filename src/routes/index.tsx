import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { LayoutGrid, List, ArrowRight } from "lucide-react";
import { TopBar } from "@/components/rental/TopBar";
import { EquipmentCard } from "@/components/rental/EquipmentCard";
import { EquipmentRow } from "@/components/rental/EquipmentRow";
import { CartDrawer } from "@/components/rental/CartDrawer";
import { CarouselRow } from "@/components/rental/CarouselRow";
import { CategoryMosaic } from "@/components/rental/CategoryMosaic";
import { ListFilters } from "@/components/rental/ListFilters";
import { equipment, categories, type Category } from "@/data/equipment";
import { CategoryIllustration } from "@/components/rental/illustrations/CategoryIllustration";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Rambla Rental — Alquiler de equipos de cine y foto" },
      {
        name: "description",
        content:
          "Cámaras, lentes, iluminación, audio y soportes para producciones audiovisuales. Mar del Plata.",
      },
    ],
  }),
  component: Index,
});

type Mode = "grid" | "list";

function Index() {
  const [mode, setMode] = useState<Mode>("grid");
  const [selectedCats, setSelectedCats] = useState<Set<Category>>(new Set());
  const [brand, setBrand] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const toggleCat = (c: Category) => {
    setSelectedCats((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  };

  const filtered = useMemo(() => {
    let list = equipment.slice();
    if (selectedCats.size > 0) list = list.filter((e) => selectedCats.has(e.category));
    if (brand) list = list.filter((e) => e.brand === brand);
    if (query.trim()) {
      const q = query.toLowerCase();
      list = list.filter(
        (e) =>
          e.name.toLowerCase().includes(q) ||
          e.brand.toLowerCase().includes(q) ||
          e.category.toLowerCase().includes(q),
      );
    }
    return list;
  }, [selectedCats, brand, query]);

  const jumpToCategory = (c: Category) => {
    setSelectedCats(new Set([c]));
    setMode("grid");
    // scroll suave a la sección de categoría
    requestAnimationFrame(() => {
      const el = document.getElementById(`cat-${c}`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      else window.scrollTo({ top: 0, behavior: "smooth" });
    });
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <TopBar />

      {/* Hero amarillo brand */}
      <section className="relative overflow-hidden border-b hairline bg-amber text-ink">
        <div className="absolute inset-0 grain opacity-40" />
        <div className="relative px-6 py-12 lg:px-12 lg:py-16">
          <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-ink/70">
            Catálogo · {equipment.length} equipos · Mar del Plata
          </div>
          <h1 className="mt-4 wordmark text-[14vw] leading-[0.85] md:text-[7rem] lg:text-[8.5rem] text-balance">
            un lugar
            <br />
            donde pasan
            <br />
            cosas.
          </h1>
          <p className="mt-6 max-w-xl text-base text-ink/80">
            Cámaras, ópticas, luces, audio y soportes para producciones audiovisuales.
            Elegí fechas y armá tu pedido — te lo dejamos listo para retirar.
          </p>
          <div className="mt-6 flex flex-wrap gap-2 text-[10px] font-mono uppercase tracking-widest">
            {["calidad", "variedad", "amistad", "comunidad", "intercambio", "local"].map((w) => (
              <span key={w} className="rounded-full border border-ink/25 px-3 py-1">
                {w}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Toggle Modo */}
      <div className="sticky top-[68px] z-30 border-b hairline bg-background/90 backdrop-blur-xl">
        <div className="flex items-center gap-3 px-6 py-3 lg:px-12">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Modo
          </div>
          <div className="flex items-center gap-1 rounded-full border hairline p-0.5">
            <button
              onClick={() => setMode("grid")}
              className={cn(
                "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs uppercase tracking-wider transition",
                mode === "grid" ? "bg-ink text-amber" : "text-muted-foreground hover:text-ink",
              )}
            >
              <LayoutGrid className="h-3 w-3" /> Explorar
            </button>
            <button
              onClick={() => setMode("list")}
              className={cn(
                "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs uppercase tracking-wider transition",
                mode === "list" ? "bg-ink text-amber" : "text-muted-foreground hover:text-ink",
              )}
            >
              <List className="h-3 w-3" /> Lista completa
            </button>
          </div>
          <div className="ml-auto font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground tabular">
            {mode === "list" ? `${filtered.length} resultados` : `${equipment.length} equipos`}
          </div>
        </div>
      </div>

      {mode === "grid" ? (
        <GridMode onJumpToList={jumpToList} />
      ) : (
        <ListMode
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
        />
      )}

      <CartDrawer />
    </div>
  );
}

function GridMode({ onJumpToList }: { onJumpToList: (c: Category) => void }) {
  const news = equipment.filter((e) => e.isNew);
  const combos = equipment.filter((e) => e.isCombo);

  // Ancho fijo de cards en carrusel para snap consistente
  const cardW = 260;

  return (
    <div className="space-y-12 py-8 lg:py-12">
      {news.length > 0 && (
        <CarouselRow title="Ingresos" count={news.length}>
          {news.map((item, i) => (
            <EquipmentCard key={item.id} item={item} index={i} width={cardW} />
          ))}
        </CarouselRow>
      )}

      {combos.length > 0 && (
        <CarouselRow title="Combos" count={combos.length}>
          {combos.map((item, i) => (
            <EquipmentCard key={item.id} item={item} index={i} width={cardW + 40} />
          ))}
        </CarouselRow>
      )}

      <CategoryMosaic onSelect={onJumpToList} />

      {categories.map((c) => {
        const items = equipment.filter((e) => e.category === c);
        if (items.length === 0) return null;
        return (
          <CarouselRow
            key={c}
            title={c}
            count={items.length}
            action={
              <button
                onClick={() => onJumpToList(c)}
                className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-ink"
              >
                Ver todas <ArrowRight className="h-3 w-3" />
              </button>
            }
          >
            {items.map((item, i) => (
              <EquipmentCard key={item.id} item={item} index={i} width={cardW} />
            ))}
          </CarouselRow>
        );
      })}

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
            {(["Cámaras", "Lentes", "Luces", "Sonido", "Stands"] as const).map((c) => (
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
  query,
  setQuery,
  selectedCats,
  toggleCat,
  brand,
  setBrand,
  onClear,
  filtered,
}: {
  query: string;
  setQuery: (v: string) => void;
  selectedCats: Set<Category>;
  toggleCat: (c: Category) => void;
  brand: string | null;
  setBrand: (b: string | null) => void;
  onClear: () => void;
  filtered: typeof equipment;
}) {
  return (
    <>
      <ListFilters
        query={query}
        onQuery={setQuery}
        selectedCategories={selectedCats}
        onToggleCategory={toggleCat}
        selectedBrand={brand}
        onBrand={setBrand}
        onClear={onClear}
      />

      <div className="px-6 py-6 pb-24 lg:px-12">
        {filtered.length === 0 ? (
          <div className="rounded-lg border hairline bg-surface px-6 py-16 text-center">
            <div className="font-display text-2xl text-muted-foreground">Sin resultados</div>
            <p className="mt-2 text-sm text-muted-foreground">
              Probá con otra categoría, marca o término de búsqueda.
            </p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {filtered.map((item) => (
              <EquipmentRow key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
