import { Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";

export function TalleresBand() {
  return (
    <section className="bg-background border-y border-border/60">
      <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-12 sm:py-16 flex flex-col sm:flex-row items-center justify-between gap-8">
        <div className="flex flex-col gap-4 max-w-xl">
          <p className="font-mono text-[0.6875rem] tracking-[0.25em] uppercase text-muted-foreground">
            Workshops & Talleres
          </p>
          <h2
            className="font-display font-black lowercase leading-[0.9] tracking-[-0.01em] text-ink"
            style={{ fontSize: "clamp(1.75rem, 4vw, 2.75rem)" }}
          >
            aprender haciendo.
          </h2>
          <p className="text-[0.9375rem] leading-[1.5] text-muted-foreground">
            Clases prácticas de dirección de arte, fotografía y video en Rambla Estudio. Cupos
            limitados.
          </p>
          <Link
            to="/workshops"
            className="inline-flex items-center gap-[9px] w-fit rounded-full border border-ink text-ink px-6 py-3 text-[0.9375rem] font-bold tracking-[-0.01em] transition-[gap,background] duration-[180ms] hover:gap-[13px] hover:bg-ink hover:text-background active:scale-[0.97]"
          >
            Ver talleres <ArrowRight size={15} strokeWidth={2.4} />
          </Link>
        </div>
        <div className="hidden sm:flex flex-col items-end gap-2 text-right shrink-0">
          <div className="rounded-2xl border border-border/60 bg-muted/30 px-6 py-4 text-sm text-muted-foreground">
            <p className="font-medium text-ink text-base">Workshop Dirección de Arte</p>
            <p className="mt-0.5">x Jime Troncoso</p>
            <p className="mt-2 text-xs">11 y 18 de julio · Rambla Estudio</p>
          </div>
        </div>
      </div>
    </section>
  );
}
