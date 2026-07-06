import { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import { ActiveFiltersChips } from "@/components/rental/ActiveFiltersChips";
import { EquipmentRow } from "@/components/rental/EquipmentRow";
import { CartMiniBar } from "@/components/rental/CartMiniBar";
import { Spinner } from "@/design-system/ui/spinner";
import { type Equipment } from "@/data/equipment";
import { SearchEmptyState } from "./SearchEmptyState";

// Lazy: solo visibles tras interacción (preview lateral desktop, animación de
// fly-to-cart) — fuera del bundle inicial de la ruta.
const FlyToCartLayer = lazy(() =>
  import("@/components/rental/FlyToCartLayer").then((m) => ({ default: m.FlyToCartLayer })),
);
const PreviewPane = lazy(() =>
  import("@/components/rental/PreviewPane").then((m) => ({ default: m.PreviewPane })),
);

export function ListMode({
  allEquipos,
  apiCategories,
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
                {visibleItems.map((item, idx) => (
                  <EquipmentRow
                    key={item.id}
                    item={item}
                    disponible={getDisponible(item)}
                    index={idx}
                  />
                ))}
              </div>
              {hasMore && (
                <div
                  ref={sentinelRef}
                  className="flex items-center justify-center py-6 font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground"
                >
                  <Spinner size="sm" className="mr-2" />
                  Cargando más equipos…
                </div>
              )}
              {!hasMore && filtered.length > PAGE_SIZE && (
                <div className="py-6 text-center font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
                  Fin del catálogo · {filtered.length} equipos
                </div>
              )}
            </>
          )}
        </div>

        <Suspense>
          <PreviewPane
            item={previewItem}
            open={previewOpen}
            onClose={() => setPreviewOpen(false)}
            onOpen={() => setPreviewOpen(true)}
            disponible={previewItem ? getDisponible(previewItem) : undefined}
          />
        </Suspense>
      </div>

      <CartMiniBar allEquipos={allEquipos} />
      <Suspense>
        <FlyToCartLayer />
      </Suspense>
    </>
  );
}
