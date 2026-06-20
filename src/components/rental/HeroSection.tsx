import { useState, useEffect } from "react";
import { Link } from "@tanstack/react-router";
import { Calendar, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useHeroPhotos } from "@/lib/studio/hero-photos";
import { useReducedMotion } from "@/lib/use-reduced-motion";

interface HeroSectionProps {
  tagline: [string, string];
  equipmentCount?: number;
  onDateOpen: () => void;
}

export function HeroSection({ tagline, equipmentCount, onDateOpen }: HeroSectionProps) {
  const photos = useHeroPhotos();
  const [photoIdx, setPhotoIdx] = useState(0);
  const [paused, setPaused] = useState(false);
  const reducedMotion = useReducedMotion();
  const autoPlayPaused = paused || reducedMotion;

  useEffect(() => {
    setPhotoIdx(0);
    if (photos.length <= 1 || autoPlayPaused) return;
    const id = setInterval(() => setPhotoIdx((i) => (i + 1) % photos.length), 4500);
    return () => clearInterval(id);
  }, [photos.length, autoPlayPaused]);

  return (
    <>
      {/* ─ Hero amber ─ */}
      <section className="grain relative overflow-hidden bg-amber">
        <div
          className="flex flex-col-reverse md:grid min-h-[78dvh] md:min-h-[560px] md:max-h-[720px]"
          style={{ gridTemplateColumns: "58% 42%" }}
        >
          {/* Left: copy */}
          <div className="flex flex-col justify-between gap-6 p-[clamp(2rem,5vw,3.5rem)_clamp(1.5rem,4vw,2.75rem)]">
            <div>
              <p className="font-mono text-[0.625rem] tracking-[0.22em] uppercase text-ink/60">
                Catálogo · {equipmentCount ? `${equipmentCount}+` : "120+"} equipos · Mar del Plata
              </p>
              <h1
                className="font-display font-black lowercase leading-[0.88] text-ink-pure mt-[clamp(0.875rem,2vw,1.375rem)]"
                style={{ fontSize: "clamp(3.5rem, 9vw, 8rem)", letterSpacing: "-0.01em" }}
              >
                <span className="block">{tagline[0]}</span>
                <span className="block">{tagline[1]}</span>
              </h1>
              <p className="text-[0.9375rem] leading-[1.6] text-ink/78 max-w-[360px] mt-3.5">
                Cámaras, lentes, luces, audio y soportes para producciones audiovisuales en Mar del
                Plata. Elegí fechas y armá tu pedido.
              </p>

              {/* Pill chips de categorías */}
              <div className="flex flex-wrap gap-1.5 mt-5">
                {["Cámaras", "Luces", "Audio", "Gimbals", "Lentes", "Soporte"].map((label) => (
                  <span
                    key={label}
                    className="inline-flex items-center gap-1 px-3 py-[5px] rounded-full font-mono text-[0.5625rem] font-semibold uppercase tracking-[0.18em] text-ink/65 border border-ink/20 transition-all duration-150 hover:border-ink/45 hover:text-ink hover:bg-ink/4 whitespace-nowrap"
                  >
                    {label}
                  </span>
                ))}
              </div>
            </div>

            {/* CTA */}
            <div>
              <button
                onClick={onDateOpen}
                className={cn(
                  "inline-flex items-center gap-2.5 bg-ink text-amber rounded-full px-[26px] py-[14px] text-[0.9375rem] font-bold tracking-[-0.01em] whitespace-nowrap shadow-[0_4px_20px_oklch(0.14_0.01_60/24%)] transition-colors duration-150 hover:bg-black active:scale-[0.97]",
                  reducedMotion && "no-motion",
                )}
              >
                <Calendar size={16} /> Elegí fechas y reservá
              </button>
            </div>
          </div>

          {/* Right: rotating photo */}
          <Link
            to="/estudio"
            className="relative overflow-hidden block bg-ink min-h-[clamp(300px,52vw,460px)] md:min-h-0 border-l border-ink/14 group"
            aria-label="Conocé el estudio"
          >
            {photos.map((src, i) => (
              <img
                key={src}
                src={src}
                alt="El Estudio — Rambla Rental"
                className={cn(
                  "absolute inset-0 w-full h-full object-cover transition-[opacity] group-hover:scale-[1.04]",
                  i === photoIdx ? "opacity-100" : "opacity-0",
                )}
                style={{ transitionDuration: "900ms" }}
                loading={i === 0 ? "eager" : "lazy"}
              />
            ))}

            {/* Gradient overlay */}
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-ink/28 opacity-85 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none" />

            {/* "Conocé el estudio" pill */}
            <div className="absolute left-[18px] bottom-[18px] z-[2] inline-flex items-center gap-2 bg-ink text-amber font-bold text-[0.8125rem] tracking-[-0.01em] px-[15px] py-[9px] rounded-full shadow-[0_6px_18px_oklch(0.14_0.01_60/34%)] group-hover:bg-black transition-[background,gap] duration-[180ms]">
              Conocé el estudio
              <span className="grid place-items-center w-[22px] h-[22px] rounded-full bg-amber text-ink group-hover:translate-x-[2px] transition-transform duration-200">
                <ArrowRight size={11} strokeWidth={2.5} />
              </span>
            </div>

            {/* Navigation dots + pause button */}
            <div
              className="absolute right-4 bottom-6 z-[2] flex items-center gap-[5px]"
              role="group"
              aria-label="Fotos del estudio"
            >
              {photos.length > 1 && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    setPaused((p) => !p);
                  }}
                  aria-label={paused ? "Reanudar presentación" : "Pausar presentación"}
                  className="mr-1 grid h-5 w-5 place-items-center rounded-full bg-black/30 text-white/70 hover:bg-black/50 hover:text-white transition"
                >
                  {paused ? (
                    <svg width="8" height="8" viewBox="0 0 8 8" fill="currentColor" aria-hidden>
                      <polygon points="1,0 7,4 1,8" />
                    </svg>
                  ) : (
                    <svg width="8" height="8" viewBox="0 0 8 8" fill="currentColor" aria-hidden>
                      <rect x="1" y="0" width="2.5" height="8" />
                      <rect x="4.5" y="0" width="2.5" height="8" />
                    </svg>
                  )}
                </button>
              )}
              {photos.map((_, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    setPhotoIdx(i);
                  }}
                  aria-label={`Foto ${i + 1} de ${photos.length}`}
                  aria-current={i === photoIdx ? "true" : undefined}
                  className={cn(
                    "block h-[6px] rounded-full transition-[width,background] duration-[250ms]",
                    i === photoIdx ? "w-[17px] bg-amber" : "w-[6px] bg-white/50 hover:bg-white/80",
                  )}
                />
              ))}
            </div>
          </Link>
        </div>
      </section>

      {/* ─ Action strip ─ */}
      <div className="bg-ink flex items-center justify-between flex-wrap gap-4 px-[clamp(1.5rem,4vw,2.75rem)] py-5">
        <Link to="/estudio" className="flex items-center gap-2.5 group">
          <span
            className="font-display font-black lowercase leading-[0.92] text-amber group-hover:opacity-80 transition-opacity duration-150"
            style={{ fontSize: "clamp(1.125rem, 3vw, 1.625rem)" }}
          >
            conocé el estudio.
          </span>
          <ArrowRight size={11} strokeWidth={2.5} className="text-amber" />
        </Link>
        <span className="font-mono text-[0.5625rem] uppercase tracking-[0.2em] text-background/45 whitespace-nowrap">
          Foto y video · por hora · luces incluidas
        </span>
      </div>
    </>
  );
}
