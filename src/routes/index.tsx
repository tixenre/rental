import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Search, LayoutGrid, List, Star, ArrowDownAZ, DollarSign } from "lucide-react";
import { TopBar } from "@/components/rental/TopBar";
import { CategorySidebar } from "@/components/rental/CategorySidebar";
import { EquipmentCard } from "@/components/rental/EquipmentCard";
import { EquipmentRow } from "@/components/rental/EquipmentRow";
import { CartDrawer } from "@/components/rental/CartDrawer";
import { equipment, type Category } from "@/data/equipment";
import { CategoryIllustration } from "@/components/rental/illustrations/CategoryIllustration";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Rambla Rental — Alquiler de equipos de cine y foto" },
      {
        name: "description",
        content:
          "Catálogo de cámaras, lentes, iluminación, audio y soportes para producciones audiovisuales.",
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

type Sort = "relevancia" | "az" | "precio";

function Index() {
  const [category, setCategory] = useState<Category | "Todos">("Todos");
  const [brand, setBrand] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("relevancia");
  const [view, setView] = useState<"grid" | "list">("grid");

  const items = useMemo(() => {
    let list = equipment.slice();
    if (category !== "Todos") list = list.filter((e) => e.category === category);
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
    if (sort === "az") list.sort((a, b) => a.name.localeCompare(b.name));
    if (sort === "precio") list.sort((a, b) => a.pricePerDay - b.pricePerDay);
    return list;
  }, [category, brand, query, sort]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <TopBar />

      <div className="flex">
        <CategorySidebar
          activeCategory={category}
          activeBrand={brand}
          onCategory={(c) => setCategory(c)}
          onBrand={setBrand}
        />

        <main className="flex-1 min-w-0">
          {/* Hero — bloque amarillo brand */}
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
                Cámaras, ópticas, luces, audio y soportes para producciones
                audiovisuales. Elegí fechas y armá tu pedido — te lo dejamos
                listo para retirar.
              </p>
              <div className="mt-6 flex flex-wrap gap-2 text-[10px] font-mono uppercase tracking-widest">
                {["calidad", "variedad", "amistad", "comunidad", "intercambio", "local"].map((w) => (
                  <span key={w} className="rounded-full border border-ink/25 px-3 py-1">
                    {w}
                  </span>
                ))}
              </div>
              <div className="mt-10 flex flex-wrap items-end gap-6 border-t border-ink/15 pt-6">
                {(["Cámaras","Lentes","Iluminación","Audio","Soportes","Accesorios","Adaptadores"] as const).map((c) => (
                  <div key={c} className="flex flex-col items-center gap-2 text-ink">
                    <CategoryIllustration category={c} className="h-10 w-10" />
                    <span className="font-mono text-[9px] uppercase tracking-widest text-ink/70">{c}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Search & sort */}
          <div className="sticky top-[68px] z-30 border-b hairline bg-background/85 backdrop-blur-xl">
            <div className="flex items-center gap-3 px-6 py-3 lg:px-12">
              <div className="relative flex-1 max-w-xl">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Buscar equipos…"
                  className="w-full rounded-md border hairline bg-surface py-2 pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:border-amber/40 focus:outline-none"
                />
              </div>

              <div className="ml-auto hidden md:flex items-center gap-1 rounded-md border hairline p-0.5 text-xs">
                {(
                  [
                    ["relevancia", "Relevancia", Star],
                    ["az", "A–Z", ArrowDownAZ],
                    ["precio", "Precio", DollarSign],
                  ] as const
                ).map(([k, label, Icon]) => (
                  <button
                    key={k}
                    onClick={() => setSort(k)}
                    className={cn(
                      "flex items-center gap-1.5 rounded px-3 py-1.5 transition",
                      sort === k
                        ? "bg-amber text-ink"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    <Icon className="h-3 w-3" />
                    {label}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-1 rounded-md border hairline p-0.5">
                <button
                  onClick={() => setView("grid")}
                  className={cn(
                    "grid h-7 w-7 place-items-center rounded transition",
                    view === "grid"
                      ? "bg-amber text-ink"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                  aria-label="Vista grilla"
                >
                  <LayoutGrid className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => setView("list")}
                  className={cn(
                    "grid h-7 w-7 place-items-center rounded transition",
                    view === "list"
                      ? "bg-amber text-ink"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                  aria-label="Vista lista"
                >
                  <List className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>

          {/* Section header */}
          <div className="flex items-baseline justify-between px-6 pt-8 pb-4 lg:px-12">
            <div className="flex items-baseline gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                {category === "Todos" ? "Todos los equipos" : category}
                {brand ? ` · ${brand}` : ""}
              </span>
              <span className="text-muted-foreground">—</span>
              <span className="font-display text-lg tabular">{items.length}</span>
            </div>
          </div>

          {/* Grid / List */}
          <div className="px-6 pb-24 lg:px-12">
            {items.length === 0 ? (
              <div className="rounded-lg border hairline bg-surface px-6 py-16 text-center">
                <div className="font-display text-2xl text-muted-foreground">
                  Sin resultados
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Probá con otra categoría, marca o término de búsqueda.
                </p>
              </div>
            ) : view === "grid" ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
                {items.map((item, i) => (
                  <EquipmentCard key={item.id} item={item} index={i} />
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {items.map((item) => (
                  <EquipmentRow key={item.id} item={item} />
                ))}
              </div>
            )}
          </div>
        </main>
      </div>

      <CartDrawer />
    </div>
  );
}
