import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, MessageCircle, MapPin } from "lucide-react";
import { StudioBookingForm } from "@/components/studio/StudioBookingForm";
import { StudioPackKit } from "@/components/studio/StudioPackKit";
import { STUDIO, STUDIO_PHONE } from "@/data/studio";
import { apiGetEstudio, type EstudioTrabajo, type EstudioMedia } from "@/lib/api";
import { formatARS } from "@/lib/format";
import { cn } from "@/lib/utils";
import { PublicLayout } from "@/components/rental/PublicLayout";
import { Button } from "@/design-system/ui/button";

export const Route = createLazyFileRoute("/estudio")({
  component: EstudioPage,
});

const MAPA_EMBED_DEFAULT =
  "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d5418.432520284455!2d-57.56597107511356!3d-37.98649647543215!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x9584db0050a8b0bf%3A0x3860608ed96f47f1!2sRambla%20Estudio%20y%20Rental!5e0!3m2!1ses-419!2sar!4v1782432663360!5m2!1ses-419!2sar";

// ── Grain overlay (reutilizado en secciones ink/amber) ─────────────────────
const Grain = ({ opacity = 12 }: { opacity?: number }) => (
  <div
    className="pointer-events-none absolute inset-0"
    style={{
      backgroundImage: "radial-gradient(circle, oklch(0.85 0 0 / 12%) 1px, transparent 1px)",
      backgroundSize: "5px 5px",
      opacity: opacity / 100,
    }}
  />
);

type Photo = { src: string; alt: string; hero?: boolean; ciclorama?: boolean };

// ── Galería horizontal arrastrable ─────────────────────────────────────────
// ── Trabajos: carrusel + modal ────────────────────────────────────────────────

function extractYtId(url: string): string | null {
  const m = url.match(/(?:v=|\/embed\/|youtu\.be\/)([A-Za-z0-9_-]{11})/);
  return m?.[1] ?? null;
}

const IgIcon = () => (
  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 shrink-0" fill="currentColor">
    <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
  </svg>
);

const WebIcon = () => (
  <svg
    viewBox="0 0 24 24"
    className="h-3.5 w-3.5 shrink-0"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
  >
    <circle cx="12" cy="12" r="10" />
    <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
);

function ytThumb(ytId: string) {
  return `https://img.youtube.com/vi/${ytId}/maxresdefault.jpg`;
}
function ytThumbFallback(ytId: string) {
  return `https://img.youtube.com/vi/${ytId}/hqdefault.jpg`;
}

// Thumbnail de un medio para la card. Los links traen un thumbnail permanente
// procesado por el backend; si falta (best-effort falló), YouTube cae a su
// thumbnail en vivo.
function mediaThumb(m: EstudioMedia): { src: string; fallback?: string } | null {
  if (m.kind === "foto") {
    const src = m.url_sm ?? m.url;
    return src ? { src } : null;
  }
  if (m.thumbnail) return { src: m.thumbnail };
  if (m.kind === "youtube") {
    const id = extractYtId(m.url);
    if (id) return { src: ytThumb(id), fallback: ytThumbFallback(id) };
  }
  return null;
}


function TrabajoModal({
  trabajos,
  initialIdx,
  onClose,
}: {
  trabajos: EstudioTrabajo[];
  initialIdx: number;
  onClose: () => void;
}) {
  const tCount = trabajos.length;
  const [tIdx, setTIdx] = useState(initialIdx);
  const [mIdx, setMIdx] = useState(0);

  const trabajo = trabajos[tIdx];
  const media = trabajo?.media ?? [];
  const mCount = media.length;
  const current = media[Math.min(mIdx, Math.max(mCount - 1, 0))] ?? null;

  // Navegar entre medios; al llegar al borde fluye al trabajo anterior/siguiente.
  const goMedia = useCallback(
    (d: number) => {
      const next = mIdx + d;
      if (next < 0) {
        const prevT = (tIdx - 1 + tCount) % tCount;
        setTIdx(prevT);
        setMIdx(Math.max((trabajos[prevT]?.media?.length ?? 1) - 1, 0));
      } else if (next >= mCount) {
        setTIdx((tIdx + 1) % tCount);
        setMIdx(0);
      } else {
        setMIdx(next);
      }
    },
    [mIdx, mCount, tIdx, tCount, trabajos],
  );

  // Saltar directamente al trabajo anterior/siguiente (botones del footer).
  const goTrabajo = useCallback(
    (d: number) => {
      setTIdx((i) => (i + d + tCount) % tCount);
      setMIdx(0);
    },
    [tCount],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight") goMedia(1);
      else if (e.key === "ArrowLeft") goMedia(-1);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, goMedia]);

  // El modal se ajusta al medio. YouTube = 16:9/9:16; IG = 480px (embed nativo);
  // Foto = w-fit (proporción real de la imagen, sin asumir nada).
  const isShort = current?.kind === "youtube" && /\/shorts\//.test(current.url);
  const modalWidth =
    current?.kind === "instagram"
      ? "min(94vw, 480px)"
      : current?.kind === "youtube"
        ? isShort
          ? "min(94vw, calc(82vh * 9 / 16))"
          : "min(94vw, calc(82vh * 16 / 9))"
        : undefined; // foto → w-fit (proporción nativa de la imagen)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-2 sm:p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="relative bg-ink rounded-2xl overflow-hidden max-h-[96dvh] w-fit max-w-[94vw] flex flex-col"
        style={{ width: modalWidth }}
      >
        {/* Cerrar */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-20 h-8 w-8 rounded-full bg-black/50 flex items-center justify-center text-background/70 hover:text-background transition-colors"
          aria-label="Cerrar"
        >
          <svg
            viewBox="0 0 24 24"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
          >
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>

        {/* Escenario de medios (carrusel). El modal ya tiene la proporción del
            medio actual, así que cada medio llena el ancho. */}
        <div className="relative bg-black shrink-0 flex items-center justify-center overflow-hidden">
          {current?.kind === "youtube" &&
            (() => {
              const ytId = extractYtId(current.url);
              if (!ytId) return null;
              return (
                <div
                  className="relative w-full"
                  style={{ aspectRatio: isShort ? "9 / 16" : "16 / 9" }}
                >
                  <iframe
                    src={`https://www.youtube-nocookie.com/embed/${ytId}?autoplay=1`}
                    title={trabajo.titulo}
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                    className="absolute inset-0 h-full w-full"
                  />
                </div>
              );
            })()}

          {current?.kind === "instagram" && (
            <div className="relative w-full bg-black flex items-center justify-center">
              {current.thumbnail ? (
                <>
                  <img
                    src={current.thumbnail}
                    alt={trabajo.titulo}
                    className="block w-full max-h-[82vh] object-contain"
                    style={
                      current.w && current.h
                        ? { aspectRatio: `${current.w} / ${current.h}` }
                        : undefined
                    }
                  />
                  <a
                    href={current.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="absolute bottom-2 right-2 flex items-center gap-1.5 rounded-full bg-black/60 px-3 py-1.5 text-xs text-background/70 hover:text-background transition-colors"
                    aria-label="Ver en Instagram"
                  >
                    <IgIcon />
                    Ver en Instagram
                  </a>
                </>
              ) : (
                <div className="flex min-h-48 items-center justify-center">
                  <a
                    href={current.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-background/50 hover:text-amber transition-colors"
                  >
                    <IgIcon />
                    Ver en Instagram
                  </a>
                </div>
              )}
            </div>
          )}

          {current?.kind === "foto" && (
            <img
              src={current.url_avif ?? current.url}
              alt={trabajo.titulo}
              className="block max-h-[82vh] max-w-[94vw]"
            />
          )}

          {/* Flechas dentro del medio (fluyen al trabajo anterior/siguiente al llegar al borde) */}
          {mCount > 1 && (
            <>
              <button
                onClick={() => goMedia(-1)}
                className="absolute left-2 sm:left-3 top-1/2 -translate-y-1/2 z-10 h-10 w-10 rounded-full bg-black/55 hover:bg-black/75 flex items-center justify-center text-background transition-colors"
                aria-label="Anterior"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
              <button
                onClick={() => goMedia(1)}
                className="absolute right-2 sm:right-3 top-1/2 -translate-y-1/2 z-10 h-10 w-10 rounded-full bg-black/55 hover:bg-black/75 flex items-center justify-center text-background transition-colors"
                aria-label="Siguiente"
              >
                <ArrowRight className="h-5 w-5" />
              </button>
              <div className="absolute top-3 left-3 z-10 rounded-full bg-black/55 px-2.5 py-1 font-mono text-2xs text-background/80">
                {mIdx + 1} / {mCount}
              </div>
            </>
          )}
        </div>

        {/* Puntos del carrusel de medios */}
        {mCount > 1 && (
          <div className="flex items-center justify-center gap-1.5 py-3 bg-ink shrink-0">
            {media.map((_, i) => (
              <button
                key={i}
                onClick={() => setMIdx(i)}
                aria-label={`Ir al medio ${i + 1}`}
                className={cn(
                  "h-1.5 rounded-full transition-all",
                  i === mIdx ? "w-5 bg-amber" : "w-1.5 bg-background/25 hover:bg-background/45",
                )}
              />
            ))}
          </div>
        )}

        {/* Info */}
        <div className="px-5 py-4 space-y-2 overflow-y-auto">
          {trabajo.categorias.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              {trabajo.categorias.map((cat) => (
                <span
                  key={cat}
                  className="rounded-full border border-amber/40 px-2.5 py-0.5 font-mono text-2xs uppercase tracking-[0.15em] text-amber"
                >
                  {cat}
                </span>
              ))}
            </div>
          )}
          {trabajo.titulo && (
            <h3 className="font-display font-bold text-background text-xl leading-tight">
              {trabajo.titulo}
            </h3>
          )}
          {trabajo.descripcion && (
            <p className="text-sm text-background/55 leading-relaxed">{trabajo.descripcion}</p>
          )}
          {trabajo.realizador && (
            <div className="flex items-center gap-2 pt-1">
              {trabajo.realizador_logo_url && (
                <img
                  src={trabajo.realizador_logo_url}
                  alt={trabajo.realizador}
                  className="h-6 w-6 rounded object-contain border border-background/10 shrink-0"
                />
              )}
              <span className="text-sm font-medium text-background/65">{trabajo.realizador}</span>
              {trabajo.realizador_instagram && (
                <a
                  href={`https://instagram.com/${trabajo.realizador_instagram.replace(/^@/, "")}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-1 flex items-center gap-1 text-xs text-background/35 hover:text-amber transition-colors"
                >
                  <IgIcon />
                  {trabajo.realizador_instagram.startsWith("@")
                    ? trabajo.realizador_instagram
                    : `@${trabajo.realizador_instagram}`}
                </a>
              )}
              {trabajo.realizador_web && (
                <a
                  href={
                    trabajo.realizador_web.startsWith("http")
                      ? trabajo.realizador_web
                      : `https://${trabajo.realizador_web}`
                  }
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-1 flex items-center gap-1 text-xs text-background/35 hover:text-amber transition-colors"
                >
                  <WebIcon />
                  {trabajo.realizador_web.replace(/^https?:\/\//, "").replace(/\/$/, "")}
                </a>
              )}
            </div>
          )}

          {/* Navegación entre trabajos */}
          {tCount > 1 && (
            <div className="flex items-center justify-between pt-3 mt-1 border-t border-background/10">
              <button
                onClick={() => goTrabajo(-1)}
                className="flex items-center gap-1.5 text-xs text-background/40 hover:text-amber transition-colors"
                aria-label="Trabajo anterior"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                anterior
              </button>
              <span className="font-mono text-2xs text-background/25 tabular-nums">
                {tIdx + 1} / {tCount}
              </span>
              <button
                onClick={() => goTrabajo(1)}
                className="flex items-center gap-1.5 text-xs text-background/40 hover:text-amber transition-colors"
                aria-label="Trabajo siguiente"
              >
                siguiente
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Card del carrusel. Alto fijo, ancho según la proporción REAL del thumbnail
// (vertical/cuadrado/horizontal) — sin recortar. Las dimensiones vienen del
// backend (links) o se miden al cargar la imagen (fotos); default 4/5 vertical.
function TrabajoCard({ trabajo, onOpen }: { trabajo: EstudioTrabajo; onOpen: () => void }) {
  const first = trabajo.media[0];
  const hasVideo = trabajo.media.some((m) => m.kind !== "foto");
  const t = first ? mediaThumb(first) : null;
  const multi = trabajo.media.length > 1;

  const initial = first && first.w && first.h ? first.w / first.h : null;
  const [aspect, setAspect] = useState<number | null>(initial);
  const ar = aspect ?? 4 / 5;
  // El ancho de la card sale del alto base × la proporción real, topado a 86vw.
  // El thumbnail usa `aspect-ratio` (no alto fijo) → si el ancho topa en mobile,
  // baja el alto y la proporción se mantiene (un video horizontal no se recorta).
  const CARD_H = "clamp(12rem, 40vh, 22rem)";

  return (
    <button
      onClick={onOpen}
      className="snap-start shrink-0 rounded-xl overflow-hidden border border-background/10 bg-background/5 text-left group"
      style={{ width: `min(calc(${CARD_H} * ${ar}), 86vw)` }}
      draggable={false}
    >
      {/* Thumbnail — proporción real del medio (sin recortar) */}
      <div className="relative w-full overflow-hidden bg-background/5" style={{ aspectRatio: ar }}>
        {t?.src ? (
          <img
            src={t.src}
            alt={trabajo.titulo}
            loading="lazy"
            draggable={false}
            onLoad={(e) => {
              const w = e.currentTarget.naturalWidth;
              const h = e.currentTarget.naturalHeight;
              if (w && h) setAspect(w / h);
            }}
            onError={
              t.fallback
                ? (e) => {
                    e.currentTarget.src = t.fallback!;
                    e.currentTarget.onerror = null;
                  }
                : undefined
            }
            className="h-full w-full object-cover pointer-events-none transition-transform duration-500 group-hover:scale-[1.04]"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-background/15 text-xs">sin imagen</span>
          </div>
        )}
        {/* Play badge */}
        {hasVideo && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-black/30 transition-colors">
            <div className="h-10 w-10 rounded-full bg-background/85 flex items-center justify-center shadow group-hover:scale-110 transition-transform">
              <svg viewBox="0 0 24 24" className="h-4 w-4 text-ink ml-0.5" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
            </div>
          </div>
        )}
        {/* Indicador de varios medios (estilo carrusel IG) */}
        {multi && (
          <div className="absolute top-2 right-2 rounded-full bg-black/55 px-2 py-0.5 flex items-center gap-1 text-background/90">
            <svg
              viewBox="0 0 24 24"
              className="h-3 w-3"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <rect x="8" y="8" width="12" height="12" rx="2" />
              <path d="M4 16V6a2 2 0 0 1 2-2h10" />
            </svg>
            <span className="font-mono text-2xs">{trabajo.media.length}</span>
          </div>
        )}
      </div>

      {/* Footer compacto */}
      <div className="px-3 py-2.5">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            {trabajo.titulo && (
              <p className="text-sm font-semibold text-background leading-snug truncate">
                {trabajo.titulo}
              </p>
            )}
            {trabajo.realizador && (
              <p className="text-xs text-background/45 truncate mt-0.5">{trabajo.realizador}</p>
            )}
          </div>
          {trabajo.categoria && (
            <span className="shrink-0 rounded-full bg-amber/15 px-2 py-0.5 font-mono text-2xs uppercase tracking-[0.1em] text-amber/80 whitespace-nowrap">
              {trabajo.categoria}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

function TrabajosSection({ trabajos }: { trabajos: EstudioTrabajo[] }) {
  const [filtro, setFiltro] = useState<string | null>(null);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef({ active: false, startX: 0, startScroll: 0, moved: false });

  const categorias = useMemo(() => {
    const set = new Set<string>();
    trabajos.forEach((t) => t.categorias.forEach((c) => set.add(c)));
    return [...set];
  }, [trabajos]);

  const visibles = filtro ? trabajos.filter((t) => t.categorias.includes(filtro)) : trabajos;

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    drag.current = { active: true, startX: e.clientX, startScroll: el.scrollLeft, moved: false };
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current.active || !ref.current) return;
    const dx = e.clientX - drag.current.startX;
    if (Math.abs(dx) > 4) {
      drag.current.moved = true;
      ref.current.scrollLeft = drag.current.startScroll - dx;
    }
  };
  const onPointerUp = () => {
    drag.current.active = false;
  };

  return (
    <section className="bg-ink py-14">
      <div className="px-4 lg:px-12 mb-8">
        <p className="font-mono text-2xs uppercase tracking-[0.3em] text-amber/50 mb-2.5">
          Producciones
        </p>
        <h2 className="font-display font-black lowercase leading-[0.9] text-amber text-[clamp(2rem,6vw,3.5rem)]">
          en acción.
        </h2>
        <p className="mt-3 text-15 text-background/55 max-w-md">
          Trabajos hechos por gente copada que pasó por el estudio.
        </p>
        {/* Filtros */}
        {categorias.length > 1 && (
          <div className="flex flex-wrap gap-2 mt-6">
            <button
              onClick={() => setFiltro(null)}
              className={cn(
                "rounded-full px-3.5 py-1.5 font-mono text-2xs uppercase tracking-[0.15em] transition-colors",
                filtro === null
                  ? "bg-amber text-ink"
                  : "border border-background/20 text-background/50 hover:border-background/40 hover:text-background/80",
              )}
            >
              Todo
            </button>
            {categorias.map((cat) => (
              <button
                key={cat}
                onClick={() => setFiltro(filtro === cat ? null : cat)}
                className={cn(
                  "rounded-full px-3.5 py-1.5 font-mono text-2xs uppercase tracking-[0.15em] transition-colors",
                  filtro === cat
                    ? "bg-amber text-ink"
                    : "border border-background/20 text-background/50 hover:border-background/40 hover:text-background/80",
                )}
              >
                {cat}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Carrusel */}
      <div
        ref={ref}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        className="flex gap-3 overflow-x-auto px-4 pb-2 lg:px-12 scroll-pl-4 lg:scroll-pl-12 snap-x snap-mandatory [&::-webkit-scrollbar]:hidden [scrollbar-width:none] cursor-grab active:cursor-grabbing select-none"
      >
        {visibles.map((trabajo, i) => (
          <TrabajoCard
            key={trabajo.id}
            trabajo={trabajo}
            onOpen={() => {
              if (!drag.current.moved) setSelectedIdx(i);
            }}
          />
        ))}
      </div>

      {selectedIdx !== null && (
        <TrabajoModal
          trabajos={visibles}
          initialIdx={selectedIdx}
          onClose={() => setSelectedIdx(null)}
        />
      )}
    </section>
  );
}

function DragGallery({ photos, compact = false }: { photos: Photo[]; compact?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(true);
  const drag = useRef({ active: false, startX: 0, startScroll: 0 });

  const update = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    setCanPrev(el.scrollLeft > 4);
    setCanNext(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

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
  }, [update]);

  const scrollBy = (dir: 1 | -1) => {
    const el = ref.current;
    if (!el) return;
    el.scrollBy({ left: dir * Math.round(el.clientWidth * 0.8), behavior: "smooth" });
  };

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== "mouse") return;
    const el = ref.current;
    if (!el) return;
    drag.current = { active: true, startX: e.clientX, startScroll: el.scrollLeft };
    el.setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current.active) return;
    const el = ref.current;
    if (!el) return;
    el.scrollLeft = drag.current.startScroll - (e.clientX - drag.current.startX);
  };
  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (el?.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId);
    drag.current.active = false;
  };

  const arrowCls = compact
    ? "absolute top-1/2 -translate-y-1/2 hidden lg:grid h-9 w-9 place-items-center rounded-full bg-black/55 hover:bg-black/75 text-background transition"
    : "absolute top-1/2 -translate-y-1/2 hidden lg:grid h-10 w-10 place-items-center rounded-full bg-background/90 border hairline backdrop-blur shadow-sm transition";

  return (
    <div className="relative">
      <div
        ref={ref}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        className={cn(
          "flex gap-3 overflow-x-auto snap-x snap-mandatory [&::-webkit-scrollbar]:hidden [scrollbar-width:none] cursor-grab active:cursor-grabbing select-none touch-pan-x",
          compact
            ? "px-4 pb-4 pt-5 scroll-pl-4"
            : "px-4 pb-2 lg:px-12 scroll-pl-4 lg:scroll-pl-12",
        )}
      >
        {photos.map((photo, i) => (
          <div
            key={photo.src}
            className={cn(
              "snap-start shrink-0 aspect-[4/3] overflow-hidden rounded-xl bg-surface",
              compact ? "basis-[82%] sm:basis-[60%]" : "basis-[86%] sm:basis-[56%] lg:basis-[36%]",
            )}
          >
            <img
              src={photo.src}
              alt={photo.alt}
              loading={i < 3 ? "eager" : "lazy"}
              draggable={false}
              className="h-full w-full object-cover pointer-events-none select-none"
            />
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => scrollBy(-1)}
        disabled={!canPrev}
        aria-label="Foto anterior"
        className={cn(arrowCls, "left-3", !canPrev && "opacity-0 pointer-events-none")}
      >
        <ArrowLeft className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => scrollBy(1)}
        disabled={!canNext}
        aria-label="Foto siguiente"
        className={cn(arrowCls, "right-3", !canNext && "opacity-0 pointer-events-none")}
      >
        <ArrowRight className="h-4 w-4" />
      </button>
    </div>
  );
}

// ── Barra mobile fija ──────────────────────────────────────────────────────
function MobileBookBar({ priceLabel }: { priceLabel: string }) {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    const target = document.getElementById("reservar");
    if (!target) return;
    const obs = new IntersectionObserver((entries) => setHidden(entries[0].isIntersecting), {
      threshold: 0,
    });
    obs.observe(target);
    return () => obs.disconnect();
  }, []);

  return (
    <div
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 lg:hidden transition-transform duration-200",
        hidden ? "translate-y-full" : "translate-y-0",
      )}
      aria-hidden={hidden}
    >
      <div className="flex items-center gap-3 border-t hairline bg-background/95 backdrop-blur-xl px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <div className="min-w-0 flex-1">
          <div className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
            Reservar el estudio
          </div>
          <div className="truncate text-sm font-medium">{priceLabel}</div>
        </div>
        <Button
          asChild
          variant="primary"
          shape="pill"
          className="min-h-11 h-auto px-5 py-2.5 font-semibold shrink-0"
        >
          <a href="#reservar">Reservar</a>
        </Button>
      </div>
    </div>
  );
}

// ── Página principal ───────────────────────────────────────────────────────
function EstudioPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["estudio"],
    queryFn: apiGetEstudio,
    staleTime: 1000 * 60 * 5,
    retry: 2,
  });

  const precioHora = data?.precio_hora ?? STUDIO.pricePerHour;
  const minHours = data?.min_horas ?? STUDIO.minHours;
  const packActivo = data?.pack_activo ?? true;
  const packEquipos = useMemo(() => data?.pack_equipos ?? [], [data?.pack_equipos]);
  const trabajos = useMemo(() => data?.trabajos ?? [], [data?.trabajos]);
  const faq = data?.faq ?? STUDIO.faq;
  const features = data?.features ?? STUDIO.features;

  // Ubicación — admin primero, fallback a coordenadas fijas MDQ
  const direccion = data?.direccion ?? "Mar del Plata, Buenos Aires, Argentina";
  const iframeSrc = data?.mapa_embed_url || MAPA_EMBED_DEFAULT;

  const bookingConfig = data
    ? {
        pricePerHour: data.precio_hora,
        minHours: data.min_horas,
        openHour: data.open_hour,
        closeHour: data.close_hour,
        packActivo: data.pack_activo,
        packPrecio: data.pack_precio,
      }
    : undefined;

  const priceLabel = `${formatARS(precioHora)} / hora · mín ${minHours}h`;

  const photos = useMemo(
    () =>
      (data?.fotos ?? []).map((f) => ({
        src: f.url,
        alt: "El Estudio",
        hero: f.es_principal,
        ciclorama: false as const,
      })),
    [data?.fotos],
  );
  const heroPhoto = photos.find((p) => p.hero) ?? photos[0];

  const [withPack, setWithPack] = useState(false);

  // Skeleton de carga inicial (solo cuando no hay data de cache)
  if (isLoading && !data) {
    return (
      <PublicLayout
        topBar={{ variant: "estudio", cta: { label: "Reservar el estudio", href: "#reservar" } }}
      >
        <div className="flex flex-1 flex-col gap-6 px-4 lg:px-12 py-16 animate-pulse">
          <div className="h-8 w-48 rounded-md bg-surface" />
          <div className="h-[clamp(8rem,20vw,14rem)] w-full max-w-md rounded-xl bg-surface" />
          <div className="h-4 w-64 rounded-md bg-surface" />
          <div className="h-4 w-40 rounded-md bg-surface" />
        </div>
      </PublicLayout>
    );
  }

  // Error de red — mostramos un estado claro con opción de reintentar.
  // El contenido de la página igual se renderiza con los datos estáticos de fallback.
  const networkError = isError;

  return (
    <PublicLayout
      topBar={{ variant: "estudio", cta: { label: "Reservar el estudio", href: "#reservar" } }}
    >
      {networkError && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 bg-destructive/10 border-b border-destructive/30 px-4 py-3 text-sm text-destructive"
        >
          <span>No se pudo cargar la info actualizada del estudio. Mostrando datos guardados.</span>
          <button
            onClick={() => refetch()}
            className="shrink-0 rounded-full border border-destructive/40 px-3 py-1 text-xs font-medium hover:bg-destructive/10 transition"
          >
            Reintentar
          </button>
        </div>
      )}

      <main>
        {/* ── Hero — ink editorial ──────────────────────────────────── */}
        <section className="relative overflow-hidden bg-ink px-4 lg:px-12 py-[clamp(2.5rem,5vw,4.5rem)] pb-[clamp(3rem,6vw,5rem)]">
          <Grain />
          <div className="relative">
            <p className="font-mono text-2xs uppercase tracking-[0.3em] text-amber/60 mb-4">
              Estudio fotográfico y de video · Mar del Plata
            </p>
            <h1 className="font-display font-black text-amber leading-[0.88] tracking-[-0.02em] lowercase text-[clamp(5rem,22vw,13rem)]">
              el estudio.
            </h1>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-background/65">
              Un espacio para producciones audiovisuales con todos los equipos de Rambla a mano.
              Ideal para rodajes grandes — flexible para los chicos.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <Button asChild variant="amber" shape="pill" className="h-auto px-6 py-3 font-bold">
                <a href="#reservar">Reservar</a>
              </Button>
              <span className="inline-flex items-center rounded-full border border-background/20 px-4 py-2 font-mono text-xs text-background/70 tabular-nums whitespace-nowrap">
                {priceLabel}
              </span>
            </div>
          </div>
        </section>

        {/* Foto hero — full-bleed */}
        <div className="aspect-[16/9] md:aspect-[21/9] w-full overflow-hidden bg-ink">
          {heroPhoto && (
            <img
              src={heroPhoto.src}
              alt="El Estudio — Rambla Rental"
              loading="eager"
              fetchPriority="high"
              decoding="async"
              sizes="100vw"
              className="h-full w-full object-cover block"
            />
          )}
        </div>

        {/* ── Ciclorama + galería — split editorial ink ────────────── */}
        <section className="grid lg:grid-cols-2">
          {/* Texto — ink */}
          <div className="relative overflow-hidden bg-ink px-[clamp(1.5rem,4vw,3.5rem)] py-[clamp(2.5rem,5vw,4.5rem)] flex flex-col justify-center">
            <Grain opacity={10} />
            <div className="relative">
              <p className="font-mono text-2xs uppercase tracking-[0.3em] text-amber/55 mb-5">
                La pieza central
              </p>
              <div className="flex items-baseline gap-1 leading-none">
                <span className="font-display font-black text-amber leading-[0.88] tracking-[-0.02em] text-[clamp(5rem,14vw,9rem)]">
                  6×6
                </span>
                <span className="font-mono text-amber/55 text-[clamp(1.25rem,3vw,2rem)] mb-1">
                  m
                </span>
              </div>
              <h2 className="font-display font-black text-amber lowercase leading-[0.9] tracking-[-0.02em] text-[clamp(2.25rem,6vw,4rem)] mt-1">
                ciclorama.
              </h2>
              <p className="mt-5 max-w-sm text-15 leading-relaxed text-background/65">
                La curva continua elimina el horizonte. Fondo limpio, sin sombras, listo para usar —
                sin postproducción.
              </p>
              <p className="mt-3 text-sm leading-relaxed text-background/50">
                Ideal para retratos, moda, productos, contenido de marca y rodajes comerciales.
              </p>
              <div className="mt-7 flex flex-wrap gap-2">
                {["Curva continua", "Sin sombras", "Potencia extra", "Fondos de papel"].map((t) => (
                  <span
                    key={t}
                    className="inline-flex items-center rounded-full border border-amber/30 px-3.5 py-1 font-mono text-2xs uppercase tracking-[0.2em] text-amber/70 whitespace-nowrap"
                  >
                    {t}
                  </span>
                ))}
              </div>
              <Button
                asChild
                variant="amber"
                shape="pill"
                className="mt-8 self-start h-auto px-5 py-2.5 font-bold"
              >
                <a href="#reservar">
                  Reservar el espacio
                  <ArrowRight className="h-3.5 w-3.5" />
                </a>
              </Button>
            </div>
          </div>
          {/* Galería del espacio */}
          <div className="min-h-72 lg:min-h-0 flex flex-col justify-center overflow-hidden bg-ink border-t lg:border-t-0 lg:border-l border-background/10">
            {photos.length > 0 ? (
              <DragGallery photos={photos} compact />
            ) : (
              <div className="flex-1" />
            )}
          </div>
        </section>

        {/* ── El espacio incluye ────────────────────────────────────── */}
        {(() => {
          const visibles = features.filter((f) => (f.value ?? "").trim().length > 0);
          if (visibles.length === 0) return null;
          return (
            <section className="bg-surface px-4 lg:px-12 py-12">
              <h2 className="font-display font-black lowercase text-[clamp(1.5rem,3vw,2rem)]">
                el espacio incluye.
              </h2>
              <div className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {visibles.map((f) => (
                  <div key={f.label} className="rounded-xl border hairline bg-background p-3.5">
                    <div className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground mb-1">
                      {f.label}
                    </div>
                    <div className="font-semibold text-15">{f.value}</div>
                  </div>
                ))}
              </div>
            </section>
          );
        })()}

        {/* ── Reservar ─────────────────────────────────────────────── */}
        <section
          id="reservar"
          className="relative overflow-hidden bg-amber px-4 lg:px-12 py-14 scroll-mt-16"
        >
          <Grain opacity={14} />
          <div className="relative">
            <div className="flex flex-wrap items-end justify-between gap-3 mb-7">
              <div>
                <p className="font-mono text-2xs uppercase tracking-[0.3em] text-ink/55 mb-2.5">
                  Reservas
                </p>
                <h2 className="font-display font-black lowercase leading-[0.95] text-ink text-[clamp(1.75rem,4vw,2.75rem)]">
                  reservá tu sesión.
                </h2>
                <p className="mt-2.5 max-w-md text-15 text-ink/65 leading-relaxed">
                  Mínimo {minHours} horas. Elegí día y horario — te contactamos para confirmar.
                </p>
              </div>
              <span className="font-mono text-2xs uppercase tracking-[0.2em] text-ink/50 tabular-nums whitespace-nowrap shrink-0">
                {priceLabel}
              </span>
            </div>
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:items-start">
              <StudioBookingForm
                config={bookingConfig}
                withPack={withPack}
                onPackChange={setWithPack}
              />
              {packActivo && (
                <aside className="rounded-2xl border border-ink/20 bg-ink/8 p-5 lg:sticky lg:top-20 lg:self-start">
                  <div className="font-mono text-2xs uppercase tracking-[0.2em] text-ink/55 mb-3.5">
                    Estudio + equipos · qué incluye
                  </div>
                  {withPack ? (
                    packEquipos.length > 0 ? (
                      <StudioPackKit equipos={packEquipos} title="Equipos incluidos" />
                    ) : (
                      <div className="flex flex-col gap-2.5">
                        {STUDIO.addon.includes.map((item) => (
                          <div key={item} className="flex gap-2.5 text-sm leading-relaxed">
                            <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-ink shrink-0" />
                            <span>{item}</span>
                          </div>
                        ))}
                      </div>
                    )
                  ) : (
                    <p className="text-sm text-ink/60 leading-relaxed">
                      Seleccioná "Estudio + equipos" para ver qué incluye el pack de luces y
                      griperías.
                    </p>
                  )}
                </aside>
              )}
            </div>
          </div>
        </section>

        {/* ── En acción — trabajos ──────────────────────────────────── */}
        {trabajos.length > 0 && <TrabajosSection trabajos={trabajos} />}

        {/* ── Dónde estamos ─────────────────────────────────────────── */}
        <section className="border-t hairline bg-surface px-4 lg:px-12 py-14">
          <h2 className="font-display font-black lowercase leading-[0.92] text-[clamp(1.75rem,4vw,2.5rem)] mb-8">
            dónde estamos.
          </h2>
          <div className="flex items-start gap-3 mb-6">
            <MapPin className="h-4 w-4 text-amber mt-0.5 shrink-0" />
            <p className="text-base font-semibold leading-snug">{direccion}</p>
          </div>
          <div className="w-full aspect-[16/7] overflow-hidden rounded-2xl border hairline bg-surface min-h-60">
            <iframe
              title="Mapa del estudio"
              src={iframeSrc}
              className="h-full w-full border-0 block"
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
            />
          </div>
        </section>

        {/* ── FAQ ───────────────────────────────────────────────────── */}
        {faq.filter((f) => f.q.trim() && f.a.trim()).length > 0 && (
          <section className="border-t hairline px-4 lg:px-12 py-12">
            <h2 className="font-display font-black lowercase text-[clamp(1.5rem,3vw,2rem)] mb-5">
              preguntas frecuentes.
            </h2>
            <div className="flex flex-col gap-2 max-w-2xl">
              {faq
                .filter((f) => f.q.trim() && f.a.trim())
                .map((item) => (
                  <details
                    key={item.q}
                    className="group rounded-xl border hairline bg-surface overflow-hidden"
                  >
                    <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3.5 font-semibold text-15 select-none">
                      {item.q}
                      <span className="text-muted-foreground shrink-0 transition-transform group-open:rotate-180">
                        ▾
                      </span>
                    </summary>
                    <p className="px-4 pb-4 text-sm text-muted-foreground leading-relaxed">
                      {item.a}
                    </p>
                  </details>
                ))}
            </div>
          </section>
        )}

        {/* ── CTA "hablemos." ───────────────────────────────────────── */}
        <section className="bg-ink px-4 lg:px-12 py-16">
          <div className="max-w-xl">
            <p className="font-mono text-2xs uppercase tracking-[0.3em] text-amber/60 mb-3">
              ¿Tenés dudas?
            </p>
            <h2 className="font-display font-black lowercase leading-[0.9] text-amber text-[clamp(2rem,6vw,4rem)]">
              hablemos.
            </h2>
            <p className="mt-4 text-15 leading-relaxed text-amber/65 max-w-sm">
              Te respondemos en el día. Contanos qué necesitás y armamos un presupuesto a medida.
            </p>
            <Button
              asChild
              variant="amber"
              shape="pill"
              className="mt-7 h-auto px-6 py-3 text-15 font-bold"
            >
              <a
                href={`https://wa.me/${STUDIO_PHONE}?text=${encodeURIComponent("Hola Rambla! Quería consultar por el estudio.")}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <MessageCircle className="h-4 w-4" />
                Escribir por WhatsApp
              </a>
            </Button>
          </div>
        </section>
      </main>

      {/* Spacer mobile (detrás de la barra fija) */}
      <div className="h-20 lg:hidden" aria-hidden />
      <MobileBookBar priceLabel={priceLabel} />
    </PublicLayout>
  );
}
