import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Calendar, ChevronRight } from "lucide-react";
import { Button } from "@/design-system/ui/button";
import { useHeroTaglines } from "@/lib/hero-taglines";
import { useHeroPhotos, heroImgProps } from "@/lib/studio/hero-photos";

/* ── HeroBanner ──────────────────────────────────────────────────── */
// Hero amber del catálogo móvil. Foto rotante + eyebrow + headline + CTA "Elegir fechas".
// El heroRef ancla el amber-on-scroll del topbar. Las fotos salen de R2 (admin)
// vía useHeroPhotos — misma fuente que el hero desktop y la página /estudio.
export function HeroBanner({
  heroRef,
  equipCount,
  onDateOpen,
}: {
  heroRef: React.RefObject<HTMLDivElement | null>;
  equipCount: number;
  onDateOpen: () => void;
}) {
  const navigate = useNavigate();
  const photos = useHeroPhotos();
  const [photoIdx, setPhotoIdx] = useState(0);

  useEffect(() => {
    setPhotoIdx(0);
    if (photos.length <= 1) return;
    const id = setInterval(() => setPhotoIdx((i) => (i + 1) % photos.length), 4500);
    return () => clearInterval(id);
  }, [photos.length]);

  const taglines = useHeroTaglines();

  const taglineIdx = useMemo(() => Math.floor(Math.random() * 4), []);
  const tagline = taglines[taglineIdx % taglines.length];

  return (
    <div ref={heroRef} className="bg-ink">
      {/* Foto rotante 16:9 full-bleed (banner cinematográfico). Crossfade con
          <img> object-fit:cover — equivalente a background-size:cover pero permite
          srcset/sizes y fetchpriority, lo que habilita al browser a elegir la
          variante 800px en mobile (vs 1600px antes → ~4× menos bytes).
          bg-ink tapa cualquier gap subpíxel. */}
      <div
        className="relative overflow-hidden bg-ink"
        style={{ width: "100%", aspectRatio: "16 / 9" }}
        aria-label="El Estudio — Rambla Rental"
      >
        {photos.map((photo, i) => (
          <img
            key={photo.url}
            {...heroImgProps(photo, { eager: i === 0 })}
            alt="El Estudio — Rambla Rental"
            aria-hidden={i !== photoIdx}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "center",
              opacity: i === photoIdx ? 1 : 0,
              transition: "opacity 900ms",
            }}
          />
        ))}
        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-ink/30" />
        <Button
          type="button"
          variant="primary"
          shape="pill"
          onClick={() => navigate({ to: "/estudio" })}
          className="absolute left-4 bottom-4 min-h-[44px] h-auto gap-1.5 font-bold tracking-[-0.01em] px-4 py-2.5"
          style={{ zIndex: 1 }}
        >
          Conocé el estudio
          <ChevronRight size={13} strokeWidth={2.5} />
        </Button>
        {/* Navigation dots */}
        <div className="absolute right-4 bottom-5 flex gap-[5px]" style={{ zIndex: 1 }}>
          {photos.map((_, i) => (
            <i
              key={i}
              className="block h-[5px] rounded-full transition-[width,background] duration-[250ms]"
              style={{
                width: i === photoIdx ? 14 : 5,
                background: i === photoIdx ? "var(--amber)" : "rgba(255,255,255,0.45)",
              }}
            />
          ))}
        </div>
      </div>

      {/* Copy section — amber. */}
      <div className="bg-amber" style={{ padding: "24px 20px 32px" }}>
        <div className="font-mono text-xs uppercase tracking-[0.24em] text-ink/55 mb-3">
          Catálogo · {equipCount} equipos · Mar del Plata
        </div>

        {/* eslint-disable-next-line no-restricted-syntax -- display hero number: entre text-4xl (36px) y text-5xl (48px), óptico */}
        <div className="font-display text-[42px] font-black text-ink leading-[1] tracking-[-0.02em] mb-4">
          {tagline[0]}
          <br />
          {tagline[1]}
        </div>

        <p className="font-sans text-sm leading-[1.55] text-ink/72 mb-8">
          Cámaras, ópticas, luces, audio y soportes para producciones audiovisuales en Mar del
          Plata.
        </p>

        {/* CTA principal */}
        <Button
          type="button"
          variant="primary"
          shape="pill"
          onClick={onDateOpen}
          className="w-full h-auto py-4 text-15 font-bold"
        >
          <Calendar size={16} />
          Elegir fechas
        </Button>
      </div>
    </div>
  );
}
