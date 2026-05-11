import { useEffect, useMemo, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ChevronRight, Search, X } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";
import type { Equipment } from "@/data/equipment";
import { buildEquipoSlug } from "@/lib/equipo-slug";
import { EmptyImage } from "./EmptyImage";

const MAX_RESULTS = 12;

const norm = (s: string) =>
  (s ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  query: string;
  setQuery: (q: string) => void;
  allEquipos: Equipment[];
  categories: string[];
  onToggleCategory: (c: string) => void;
};

export function MobileSearchSheet({
  open,
  onOpenChange,
  query,
  setQuery,
  allEquipos,
  categories,
  onToggleCategory,
}: Props) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 80);
      return () => clearTimeout(t);
    }
  }, [open]);

  const trimmed = query.trim();

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

  function handleCategorySelect(cat: string) {
    onToggleCategory(cat);
    onOpenChange(false);
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
          {/* Header */}
          <div className="flex shrink-0 items-center gap-2 border-b hairline px-3 py-3">
            <button
              onClick={() => onOpenChange(false)}
              className="grid h-10 w-10 shrink-0 place-items-center rounded-full hover:bg-muted"
              aria-label="Volver"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>

            <div className="relative flex-1 min-w-0">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") onOpenChange(false);
                }}
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

          {/* Body */}
          <div className="flex-1 overflow-y-auto overscroll-contain">
            {!trimmed ? (
              /* Empty state — category shortcuts */
              <div className="px-4 pt-5">
                <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                  Categorías
                </p>
                <div className="flex flex-wrap gap-2">
                  {categories.map((cat) => (
                    <button
                      key={cat}
                      onClick={() => handleCategorySelect(cat)}
                      className="rounded-full border hairline bg-surface px-3.5 py-2 text-sm font-medium text-ink transition active:scale-95 active:bg-muted"
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>
            ) : results.length === 0 ? (
              /* No results */
              <div className="flex flex-col items-center justify-center gap-1.5 py-20 text-center">
                <p className="text-sm font-medium text-ink">Sin resultados</p>
                <p className="text-xs text-muted-foreground">
                  Probá con otra palabra o revisá la ortografía
                </p>
              </div>
            ) : (
              /* Results list */
              <>
                <ul className="divide-y hairline">
                  {results.slice(0, MAX_RESULTS).map((item) => (
                    <li key={item.id}>
                      <button
                        onClick={() => handleSelect(item)}
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
                            <EmptyImage
                              category={item.category}
                              brand={item.brand}
                            />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="truncate text-sm font-medium text-ink">
                            {item.name}
                          </p>
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
                    onClick={() => onOpenChange(false)}
                    className="w-full py-4 text-sm font-medium text-amber"
                  >
                    Ver los {results.length} resultados →
                  </button>
                )}
              </>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
