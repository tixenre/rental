import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, MessageCircle, MapPin, ExternalLink } from "lucide-react";
import { StudioBookingForm } from "@/components/studio/StudioBookingForm";
import { StudioPackKit } from "@/components/studio/StudioPackKit";
import { STUDIO, STUDIO_PHONE } from "@/data/studio";
import { apiGetEstudio } from "@/lib/api";
import { formatARS } from "@/lib/format";
import { cn } from "@/lib/utils";
import { PublicLayout } from "@/components/rental/PublicLayout";

export const Route = createLazyFileRoute("/estudio")({
  component: EstudioPage,
});

// Coordenadas del estudio (Mar del Plata) — reemplazar con dirección real del admin
const MAPA_EMBED_DEFAULT =
  "https://maps.google.com/maps?q=-38.0028,-57.5578&z=15&hl=es&output=embed";
const MAPA_URL_DEFAULT =
  "https://www.google.com/maps/search/?api=1&query=Mar+del+Plata+Buenos+Aires+Argentina";

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
function DragGallery({ photos }: { photos: Photo[] }) {
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

  const arrowCls =
    "absolute top-1/2 -translate-y-1/2 hidden lg:grid h-10 w-10 place-items-center rounded-full bg-background/90 border hairline backdrop-blur shadow-sm transition";

  return (
    <div className="relative">
      <div
        ref={ref}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        className="flex gap-3 overflow-x-auto px-4 pb-2 lg:px-12 scroll-pl-4 lg:scroll-pl-12 snap-x snap-mandatory [&::-webkit-scrollbar]:hidden [scrollbar-width:none] cursor-grab active:cursor-grabbing select-none touch-pan-x"
      >
        {photos.map((photo, i) => (
          <div
            key={photo.src}
            className="snap-start shrink-0 basis-[86%] sm:basis-[56%] lg:basis-[36%] aspect-[4/3] overflow-hidden rounded-xl bg-surface"
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
        className={cn(
          arrowCls,
          "left-3",
          canPrev
            ? "hover:bg-ink hover:text-amber hover:border-ink"
            : "opacity-0 pointer-events-none",
        )}
      >
        <ArrowLeft className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => scrollBy(1)}
        disabled={!canNext}
        aria-label="Foto siguiente"
        className={cn(
          arrowCls,
          "right-3",
          canNext
            ? "hover:bg-ink hover:text-amber hover:border-ink"
            : "opacity-0 pointer-events-none",
        )}
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
        <a
          href="#reservar"
          className="inline-flex items-center justify-center min-h-11 rounded-full bg-ink px-5 py-2.5 text-sm font-semibold text-amber hover:brightness-110 transition shrink-0"
        >
          Reservar
        </a>
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
  const faq = data?.faq ?? STUDIO.faq;
  const features = data?.features ?? STUDIO.features;

  // Ubicación — admin primero, fallback a coordenadas fijas MDQ
  const direccion = data?.direccion ?? "Mar del Plata, Buenos Aires, Argentina";
  const comoLlegar =
    data?.como_llegar ??
    "Acceso directo para descarga de equipos. Estacionamiento en la calle (zona azul gratuita los fines de semana).";
  const iframeSrc = data?.mapa_embed_url ?? MAPA_EMBED_DEFAULT;
  const verMapaHref =
    data?.mapa_url ??
    (data?.direccion
      ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(data.direccion)}`
      : MAPA_URL_DEFAULT);

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

  // Fotos: admin primero, fallback a las fotos estáticas reales
  const apiPhotos = useMemo(
    () =>
      (data?.fotos ?? []).map((f) => ({
        src: f.url,
        alt: "El Estudio",
        hero: f.es_principal,
        ciclorama: false as const,
      })),
    [data?.fotos],
  );
  const photos = apiPhotos.length > 0 ? apiPhotos : STUDIO.photos;
  const heroPhoto = photos.find((p) => p.hero) ?? photos[0];
  const galleryPhotos = photos.filter((p) => !p.hero);
  const cicloramaPhoto =
    photos.find((p) => p.ciclorama) ??
    photos.find((p) => p.alt?.toLowerCase().includes("ciclo")) ??
    photos[2];

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
              <a
                href="#reservar"
                className="inline-flex items-center justify-center rounded-full bg-amber px-6 py-3 text-sm font-bold text-ink hover:brightness-105 transition"
              >
                Reservar
              </a>
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
              className="h-full w-full object-cover block"
            />
          )}
        </div>

        {/* ── Galería arrastrable ───────────────────────────────────── */}
        <section className="border-t hairline pt-10 pb-12">
          <div className="mb-5 flex items-end justify-between gap-3 px-4 lg:px-12">
            <div>
              <h2 className="font-display font-black lowercase text-[clamp(1.75rem,4vw,2.5rem)] leading-[0.92]">
                el espacio.
              </h2>
              <p className="mt-1.5 text-sm text-muted-foreground">
                Deslizá para ver el estudio completo.
              </p>
            </div>
            <span className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground tabular-nums shrink-0">
              {photos.length} fotos
            </span>
          </div>
          <DragGallery photos={galleryPhotos.length > 0 ? galleryPhotos : photos} />
        </section>

        {/* ── Ciclorama — split editorial ink ──────────────────────── */}
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
              <p className="mt-5 max-w-sm text-[0.9375rem] leading-relaxed text-background/65">
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
              <a
                href="#reservar"
                className="mt-8 self-start inline-flex items-center gap-2 rounded-full bg-amber px-5 py-2.5 text-sm font-bold text-ink hover:brightness-105 transition"
              >
                Reservar el espacio
                <ArrowRight className="h-3.5 w-3.5" />
              </a>
            </div>
          </div>
          {/* Foto ciclorama */}
          <div className="min-h-72 lg:min-h-0 overflow-hidden">
            {cicloramaPhoto && (
              <img
                src={cicloramaPhoto.src}
                alt="Ciclorama 6×6 m"
                loading="lazy"
                className="h-full w-full object-cover block"
              />
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
                    <div className="font-semibold text-[0.9375rem]">{f.value}</div>
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
                <p className="mt-2.5 max-w-md text-[0.9375rem] text-ink/65 leading-relaxed">
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
                          <div key={item} className="flex gap-2.5 text-[0.8125rem] leading-relaxed">
                            <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-ink shrink-0" />
                            <span>{item}</span>
                          </div>
                        ))}
                      </div>
                    )
                  ) : (
                    <p className="text-[0.8125rem] text-ink/60 leading-relaxed">
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
        <section className="bg-ink px-4 lg:px-12 py-14">
          <div className="flex flex-wrap items-end justify-between gap-3 mb-8">
            <div>
              <p className="font-mono text-2xs uppercase tracking-[0.3em] text-amber/50 mb-2.5">
                Producciones
              </p>
              <h2 className="font-display font-black lowercase leading-[0.9] text-amber text-[clamp(2rem,6vw,3.5rem)]">
                en acción.
              </h2>
              <p className="mt-3 text-[0.9375rem] text-background/55 max-w-md">
                Trabajos hechos por gente copada que pasó por el estudio.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {photos.slice(3, 9).map((photo, i) => (
              <div
                key={photo.src}
                className="rounded-xl overflow-hidden border border-background/8 bg-background/5"
              >
                <div className="aspect-[3/2] overflow-hidden">
                  <img
                    src={photo.src}
                    alt={photo.alt}
                    loading="lazy"
                    className="h-full w-full object-cover block transition-transform duration-300 hover:scale-[1.04]"
                  />
                </div>
                <div className="px-3.5 py-3 flex items-center gap-2">
                  <span className="rounded-full bg-amber/18 px-2 py-0.5 font-mono text-2xs uppercase tracking-[0.15em] text-amber whitespace-nowrap">
                    {i % 2 === 0 ? "Fotografía" : "Video"}
                  </span>
                  <span className="text-[0.8125rem] text-background/65 truncate">{photo.alt}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Dónde estamos ─────────────────────────────────────────── */}
        <section className="border-t hairline bg-surface px-4 lg:px-12 py-14">
          <h2 className="font-display font-black lowercase leading-[0.92] text-[clamp(1.75rem,4vw,2.5rem)] mb-8">
            dónde estamos.
          </h2>
          <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
            <div className="flex flex-col gap-4 pt-1">
              <div className="flex items-start gap-3">
                <MapPin className="h-4 w-4 text-amber mt-0.5 shrink-0" />
                <p className="text-base font-semibold leading-snug">{direccion}</p>
              </div>
              <p className="text-[0.9375rem] text-muted-foreground leading-relaxed pl-7">
                {comoLlegar}
              </p>
              <div className="pl-7">
                <a
                  href={verMapaHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border hairline bg-background px-4 py-2 text-sm text-ink hover:border-ink transition"
                >
                  Ver en Google Maps <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
            <div className="aspect-[4/3] overflow-hidden rounded-2xl border hairline bg-surface min-h-60">
              <iframe
                title="Mapa del estudio"
                src={iframeSrc}
                className="h-full w-full border-0 block"
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
              />
            </div>
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
                    <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3.5 font-semibold text-[0.9375rem] select-none">
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
            <p className="mt-4 text-[0.9375rem] leading-relaxed text-amber/65 max-w-sm">
              Te respondemos en el día. Contanos qué necesitás y armamos un presupuesto a medida.
            </p>
            <a
              href={`https://wa.me/${STUDIO_PHONE}?text=${encodeURIComponent("Hola Rambla! Quería consultar por el estudio.")}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-7 inline-flex items-center gap-2 rounded-full bg-amber px-6 py-3 text-[0.9375rem] font-bold text-ink hover:brightness-105 transition"
            >
              <MessageCircle className="h-4 w-4" />
              Escribir por WhatsApp
            </a>
          </div>
        </section>
      </main>

      {/* Spacer mobile (detrás de la barra fija) */}
      <div className="h-20 lg:hidden" aria-hidden />
      <MobileBookBar priceLabel={priceLabel} />
    </PublicLayout>
  );
}
