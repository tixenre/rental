import { useRef, useState, useEffect, type ReactNode } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Banda horizontal con scroll-snap nativo + flechas prev/next.
 * Reemplaza la grilla en la home modo Grid.
 */
export function CarouselRow({
  title,
  count,
  action,
  children,
  className,
}: {
  title: ReactNode;
  count?: number;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(true);

  const update = () => {
    const el = ref.current;
    if (!el) return;
    setCanPrev(el.scrollLeft > 4);
    setCanNext(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  };

  useEffect(() => {
    update();
    const el = ref.current;
    if (!el) return;
    el.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      el.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, []);

  const scrollBy = (dir: 1 | -1) => {
    const el = ref.current;
    if (!el) return;
    el.scrollBy({ left: dir * Math.round(el.clientWidth * 0.85), behavior: "smooth" });
  };

  return (
    <section className={cn("relative", className)}>
      <header className="mb-4 flex items-end justify-between gap-4 px-6 lg:px-12">
        <div className="flex items-baseline gap-3">
          <h2 className="wordmark text-3xl text-ink lg:text-4xl">{title}</h2>
          {typeof count === "number" && (
            <span className="font-mono text-[11px] uppercase tracking-[0.25em] text-muted-foreground tabular">
              {count} ítems
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {action}
          <div className="hidden sm:flex items-center gap-1">
            <button
              onClick={() => scrollBy(-1)}
              disabled={!canPrev}
              aria-label="Anterior"
              className={cn(
                "grid h-8 w-8 place-items-center rounded-full border hairline transition",
                canPrev
                  ? "bg-background hover:border-ink hover:bg-ink hover:text-amber"
                  : "opacity-30",
              )}
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => scrollBy(1)}
              disabled={!canNext}
              aria-label="Siguiente"
              className={cn(
                "grid h-8 w-8 place-items-center rounded-full border hairline transition",
                canNext
                  ? "bg-background hover:border-ink hover:bg-ink hover:text-amber"
                  : "opacity-30",
              )}
            >
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      <div
        ref={ref}
        className="flex snap-x snap-mandatory gap-3 overflow-x-auto scroll-pl-6 px-6 py-2 lg:scroll-pl-12 lg:px-12 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]"
      >
        {children}
      </div>
    </section>
  );
}
