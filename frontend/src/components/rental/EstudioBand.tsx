import { Link } from "@tanstack/react-router";
import { Check, ArrowRight } from "lucide-react";
import { useHeroPhotos } from "@/lib/studio/hero-photos";

export function EstudioBand() {
  // Misma fuente que el hero: fotos del estudio desde R2 (admin).
  // Usamos la 2da foto para no repetir la del hero; si no hay, la 1ra.
  const photos = useHeroPhotos();
  const bandPhoto = photos[1] ?? photos[0];

  return (
    <section className="bg-ink grid grid-cols-1 md:grid-cols-[46%_54%]" data-area="estudio">
      <Link
        to="/estudio"
        className="relative overflow-hidden min-h-[280px] block group bg-ink"
        aria-label="Conocé el estudio"
      >
        {bandPhoto && (
          <img
            src={bandPhoto.url}
            srcSet={bandPhoto.urlSm ? `${bandPhoto.urlSm} 800w, ${bandPhoto.url} 1600w` : undefined}
            sizes="(max-width: 768px) 100vw, 46vw"
            alt="El Estudio — Rambla Rental"
            className="w-full h-full object-cover block transition-transform duration-700 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:scale-105"
            loading="eager"
          />
        )}
      </Link>
      <div className="flex flex-col justify-center gap-5 p-[clamp(2.25rem,5vw,4rem)_clamp(1.5rem,4vw,3.5rem)]">
        <p
          className="font-mono text-xs tracking-[0.2em] uppercase"
          style={{ color: "color-mix(in oklch, var(--area-accent) 80%, white)" }}
        >
          El Estudio
        </p>
        <h2
          className="font-display font-black lowercase leading-[0.9] tracking-[-0.01em] text-background"
          style={{ fontSize: "clamp(2.25rem, 5vw, 3.5rem)" }}
        >
          un lugar donde
          <br />
          pasan cosas.
        </h2>
        <ul className="list-none flex flex-col gap-[11px]">
          {[
            "Set con fondo infinito, ciclorama y luz natural.",
            "Living, cocina y zona de make-up para tu equipo.",
            "Se alquila por hora — con luces incluidas.",
          ].map((feature, i) => (
            <li
              key={i}
              className="flex items-start gap-[11px] text-15 leading-[1.45] text-background/82"
            >
              <span className="shrink-0 w-[22px] h-[22px] rounded-full bg-[var(--area-accent)] text-ink grid place-items-center mt-[1px]">
                <Check size={13} strokeWidth={2.4} />
              </span>
              {feature}
            </li>
          ))}
        </ul>
        <Link
          to="/estudio"
          className="inline-flex items-center gap-[9px] w-fit bg-[var(--area-accent)] text-ink rounded-full px-6 py-[13px] text-15 font-bold tracking-[-0.01em] transition-[gap,background] duration-[180ms] hover:gap-[13px] hover:brightness-110 active:scale-[0.97]"
        >
          Conocé el estudio <ArrowRight size={15} strokeWidth={2.4} />
        </Link>
      </div>
    </section>
  );
}
