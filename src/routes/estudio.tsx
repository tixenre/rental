import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Camera, MessageCircle } from "lucide-react";
import { PublicLayout } from "@/components/rental/PublicLayout";
import { CartDrawer } from "@/components/rental/CartDrawer";
import { StudioBookingForm } from "@/components/studio/StudioBookingForm";
import { StudioPackKit } from "@/components/studio/StudioPackKit";
import { STUDIO, STUDIO_PHONE } from "@/data/studio";
import { apiGetEstudio, type EstudioFoto } from "@/lib/api";
import { formatARS } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/estudio")({
  head: () => ({
    meta: [
      { title: "El Estudio — Rambla Rental" },
      {
        name: "description",
        content:
          "Estudio de foto y video en Mar del Plata. Reservá por hora con pack de luces y griperías opcional.",
      },
      { property: "og:type", content: "website" },
      { property: "og:url", content: "https://ramblarental.com/estudio" },
      { property: "og:title", content: "El Estudio — Rambla Rental" },
      {
        property: "og:description",
        content:
          "Estudio de foto y video en Mar del Plata. Reservá por hora con pack de luces y griperías opcional.",
      },
      { property: "og:image", content: "https://ramblarental.com/icon-512.png" },
      { property: "og:locale", content: "es_AR" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:title", content: "El Estudio — Rambla Rental" },
      { name: "twitter:description", content: "Estudio de foto y video · Mar del Plata" },
      { name: "twitter:image", content: "https://ramblarental.com/icon-512.png" },
    ],
    links: [{ rel: "canonical", href: "https://ramblarental.com/estudio" }],
  }),
  component: EstudioPage,
});

function PhotoPlaceholder({
  className,
  label = "Foto del estudio",
}: {
  className?: string;
  label?: string;
}) {
  return (
    <div
      className={cn(
        "relative flex items-center justify-center overflow-hidden rounded-xl bg-gradient-to-br from-amber-soft via-surface to-amber-soft/40 border hairline",
        className,
      )}
    >
      <div className="absolute inset-0 grain opacity-20" />
      <div className="relative flex flex-col items-center gap-2 text-ink/40">
        <Camera className="h-7 w-7" />
        <span className="font-mono text-[9px] uppercase tracking-[0.3em]">{label}</span>
      </div>
    </div>
  );
}

function DragGallery({
  fotos,
  placeholders,
  alt,
}: {
  fotos: EstudioFoto[];
  placeholders: number;
  alt: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(true);
  const drag = useRef<{ active: boolean; moved: boolean; startX: number; startScroll: number }>({
    active: false,
    moved: false,
    startX: 0,
    startScroll: 0,
  });

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
    el.scrollBy({ left: dir * Math.round(el.clientWidth * 0.85), behavior: "smooth" });
  };

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== "mouse") return;
    const el = ref.current;
    if (!el) return;
    drag.current = { active: true, moved: false, startX: e.clientX, startScroll: el.scrollLeft };
    el.setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current.active) return;
    const el = ref.current;
    if (!el) return;
    const dx = e.clientX - drag.current.startX;
    if (Math.abs(dx) > 5) drag.current.moved = true;
    el.scrollLeft = drag.current.startScroll - dx;
  };
  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (el && el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId);
    setTimeout(() => {
      drag.current.active = false;
      drag.current.moved = false;
    }, 0);
  };

  const items: Array<{ key: string | number; node: React.ReactNode }> =
    fotos.length > 0
      ? fotos.map((f, i) => ({
          key: f.id,
          node: (
            <img
              src={f.url}
              alt={`${alt} — foto ${i + 1}`}
              className="h-full w-full object-cover select-none"
              draggable={false}
              loading={i < 2 ? "eager" : "lazy"}
            />
          ),
        }))
      : Array.from({ length: placeholders }).map((_, i) => ({
          key: i,
          node: <PhotoPlaceholder className="h-full w-full" label={`FOTO ${i + 1}`} />,
        }));

  return (
    <div className="relative">
      <div
        ref={ref}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        className={cn(
          "flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2 lg:gap-4 lg:px-12",
          "scroll-pl-4 lg:scroll-pl-12",
          "[&::-webkit-scrollbar]:hidden [scrollbar-width:none]",
          "cursor-grab active:cursor-grabbing select-none",
          "touch-pan-x",
        )}
      >
        {items.map((it) => (
          <div
            key={it.key}
            className={cn(
              "snap-start shrink-0",
              "basis-[88%] sm:basis-[58%] lg:basis-[38%]",
              "aspect-[4/3] overflow-hidden rounded-xl bg-ink/5",
            )}
          >
            {it.node}
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => scrollBy(-1)}
        disabled={!canPrev}
        aria-label="Foto anterior"
        className={cn(
          "absolute left-3 top-1/2 hidden -translate-y-1/2 lg:grid h-10 w-10 place-items-center rounded-full bg-background/90 border hairline shadow-sm backdrop-blur transition",
          canPrev
            ? "hover:border-ink hover:bg-ink hover:text-amber"
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
          "absolute right-3 top-1/2 hidden -translate-y-1/2 lg:grid h-10 w-10 place-items-center rounded-full bg-background/90 border hairline shadow-sm backdrop-blur transition",
          canNext
            ? "hover:border-ink hover:bg-ink hover:text-amber"
            : "opacity-0 pointer-events-none",
        )}
      >
        <ArrowRight className="h-4 w-4" />
      </button>
    </div>
  );
}

function MobileBookCta({ priceLabel }: { priceLabel: string | null }) {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    const target = document.getElementById("reservar");
    if (!target) return;
    const obs = new IntersectionObserver(
      (entries) => {
        setHidden(entries[0].isIntersecting);
      },
      { threshold: 0 },
    );
    obs.observe(target);
    return () => obs.disconnect();
  }, []);
  return (
    <div
      className={cn(
        "fixed inset-x-0 bottom-0 z-30 lg:hidden",
        "transition-transform duration-200",
        hidden ? "translate-y-full" : "translate-y-0",
      )}
      aria-hidden={hidden}
    >
      <div className="pointer-events-auto flex items-center gap-3 border-t hairline bg-background/95 backdrop-blur px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <div className="min-w-0 flex-1">
          <div className="font-mono text-[9px] uppercase tracking-[0.25em] text-muted-foreground">
            Reservar el estudio
          </div>
          <div className="truncate text-sm font-medium text-ink">{priceLabel ?? "A consultar"}</div>
        </div>
        <a
          href="#reservar"
          className="inline-flex items-center justify-center rounded-full bg-ink px-5 py-2.5 text-sm font-semibold text-amber hover:brightness-110 transition"
        >
          Reservar
        </a>
      </div>
    </div>
  );
}

function EstudioPage() {
  const { data } = useQuery({
    queryKey: ["estudio"],
    queryFn: apiGetEstudio,
    staleTime: 1000 * 60 * 5,
  });

  const nombre = data?.nombre ?? STUDIO.name;
  const tagline = data?.tagline ?? STUDIO.tagline;
  const descripcion = data?.descripcion ?? STUDIO.description;
  const features = data?.features ?? STUDIO.features;
  const faq = data?.faq ?? STUDIO.faq;
  const fotos = useMemo(() => data?.fotos ?? [], [data?.fotos]);
  const packActivo = data?.pack_activo ?? true;
  const packEquipos = useMemo(() => data?.pack_equipos ?? [], [data?.pack_equipos]);
  const precioHora = data?.precio_hora ?? STUDIO.pricePerHour;
  const minHours = data?.min_horas ?? STUDIO.minHours;
  const direccion = data?.direccion ?? "";
  const comoLlegar = data?.como_llegar ?? "";
  const mapaUrl = data?.mapa_url ?? "";
  const mapaEmbedUrl = data?.mapa_embed_url ?? "";
  const testimonios = data?.testimonios ?? [];

  const tieneUbicacion = !!(mapaEmbedUrl || direccion);
  const verMapaHref =
    mapaUrl ||
    (direccion
      ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(direccion)}`
      : "");
  const iframeSrc =
    mapaEmbedUrl ||
    (direccion
      ? `https://www.google.com/maps?q=${encodeURIComponent(direccion)}&output=embed`
      : "");

  const fotoHero = fotos.find((f) => f.es_principal) ?? fotos[0];
  const fotosGaleria = useMemo(
    () => (fotoHero ? fotos.filter((f) => f.id !== fotoHero.id) : fotos),
    [fotos, fotoHero],
  );

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

  const priceLabel = precioHora > 0 ? `${formatARS(precioHora)}/hora · mín ${minHours}h` : null;
  const priceAnchor = precioHora > 0 ? `Desde ${formatARS(precioHora)}/h · mín ${minHours}h` : null;

  // Estado del modo compartido entre el formulario y el aside
  const [withPack, setWithPack] = useState(false);

  return (
    <PublicLayout>
      {/* Back link */}
      <div className="px-4 pt-4 lg:px-12">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground hover:text-ink"
        >
          <ArrowLeft className="h-3 w-3" /> Volver al catálogo
        </Link>
      </div>

      {/* ─── Hero — eyebrow + wordmark gigante stacked ─────────────── */}
      <section className="px-4 pt-3 lg:px-12 lg:pt-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground mb-4">
          {tagline}
        </p>
        <h1 className="wordmark text-[clamp(5rem,22vw,14rem)] leading-[0.88] tracking-[-0.02em]">
          {nombre}
        </h1>
        <p className="mt-5 max-w-lg text-base text-muted-foreground">{descripcion}</p>
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <a
            href="#reservar"
            className="inline-flex items-center justify-center rounded-full bg-ink px-6 py-3 text-sm font-semibold text-amber hover:brightness-110 transition"
          >
            Reservar
          </a>
          {priceAnchor && (
            <span className="inline-flex items-center rounded-full border hairline bg-surface px-4 py-2 text-xs sm:text-sm tabular text-ink">
              {priceAnchor}
            </span>
          )}
        </div>
      </section>

      {/* Foto hero — full-bleed debajo del texto */}
      <div className="mt-6">
        {fotoHero ? (
          <div className="w-full aspect-[16/11] md:aspect-[21/9] overflow-hidden">
            <img
              src={fotoHero.url}
              alt={nombre}
              className="h-full w-full object-cover"
              loading="eager"
            />
          </div>
        ) : (
          <PhotoPlaceholder
            className="aspect-[16/11] md:aspect-[21/9] w-full rounded-none"
            label="FOTO PRINCIPAL"
          />
        )}
      </div>

      {/* ─── Galería ─────────────────────────────────────────────────── */}
      {(fotosGaleria.length > 0 || !data) && (
        <section className="border-t hairline pt-8 pb-10 lg:pt-12 lg:pb-14">
          <div className="mb-5 flex items-end justify-between gap-3 px-4 lg:px-12">
            <div>
              <h2 className="font-display text-2xl sm:text-3xl">El espacio</h2>
              <p className="mt-1 text-sm text-muted-foreground">Deslizá para ver más.</p>
            </div>
            {fotosGaleria.length > 0 && (
              <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground tabular">
                {fotosGaleria.length + (fotoHero ? 1 : 0)} fotos
              </span>
            )}
          </div>
          <DragGallery fotos={fotosGaleria} placeholders={STUDIO.gallery} alt={nombre} />
        </section>
      )}

      {/* ─── Reservar + Pack ─────────────────────────────────────────── */}
      <section
        id="reservar"
        className="border-t hairline px-4 py-10 lg:px-12 lg:py-14 scroll-mt-20 lg:scroll-mt-24"
      >
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="font-display text-2xl sm:text-3xl">Reservá tu sesión</h2>
            <p className="mt-2 max-w-xl text-sm text-muted-foreground">
              Mínimo {minHours} horas. Elegí día y horario y reservá online — te contactamos para
              confirmar.
            </p>
          </div>
          {priceAnchor && (
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground tabular">
              {priceAnchor}
            </span>
          )}
        </div>
        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:items-start">
          <StudioBookingForm
            config={bookingConfig}
            withPack={withPack}
            onPackChange={setWithPack}
          />
          {packActivo && (
            <aside className="rounded-2xl border border-amber/35 bg-amber/8 p-5 lg:sticky lg:top-20 lg:self-start">
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-ink/60 mb-3.5">
                Estudio + equipos · qué incluye
              </div>
              {withPack ? (
                packEquipos.length > 0 ? (
                  <StudioPackKit equipos={packEquipos} title="Equipos incluidos" />
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Llegá con la cámara — el día de la reserva te confirmamos qué luces y griperías
                    están libres en tu franja.
                  </p>
                )
              ) : (
                <p className="text-[12px] text-muted-foreground leading-relaxed">
                  Seleccioná "Estudio + equipos" para ver qué incluye el pack de luces y griperías.
                </p>
              )}
            </aside>
          )}
        </div>
      </section>

      {/* ─── Características del espacio ─────────────────────────────── */}
      {(() => {
        const isFilled = (v: string) => {
          const t = (v ?? "").trim();
          return t.length > 0 && t !== "—" && !/^—\s*(m|m²|m\^2)?$/i.test(t);
        };
        const visibles = features.filter((f) => isFilled(f.value));
        if (visibles.length === 0) return null;
        return (
          <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
            <h2 className="font-display text-2xl sm:text-3xl">Características del espacio</h2>
            <p className="mt-2 max-w-xl text-sm text-muted-foreground">
              Lo que vas a encontrar en el lugar. No incluye equipos ni staff.
            </p>
            <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {visibles.map((f) => (
                <div key={f.label} className="rounded-xl border hairline bg-surface p-4">
                  <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                    {f.label}
                  </div>
                  <div className="mt-1 text-lg font-semibold">{f.value}</div>
                </div>
              ))}
            </div>
          </section>
        );
      })()}

      {/* ─── Ubicación ───────────────────────────────────────────────── */}
      {tieneUbicacion && (
        <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
          <h2 className="font-display text-2xl sm:text-3xl">Dónde estamos</h2>
          <div className="mt-6 grid gap-6 lg:grid-cols-2 lg:items-start">
            <div>
              {direccion && <p className="text-base text-ink">{direccion}</p>}
              {comoLlegar && (
                <p
                  className={cn(
                    direccion ? "mt-3" : "",
                    "whitespace-pre-line text-sm text-muted-foreground",
                  )}
                >
                  {comoLlegar}
                </p>
              )}
              {verMapaHref && (
                <a
                  href={verMapaHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 inline-flex items-center gap-2 rounded-full border hairline bg-surface px-4 py-2 text-sm text-ink transition hover:border-ink"
                >
                  Ver en Google Maps
                </a>
              )}
            </div>
            {iframeSrc && (
              <div className="aspect-[4/3] w-full overflow-hidden rounded-2xl border hairline bg-ink/5">
                <iframe
                  title="Mapa del estudio"
                  src={iframeSrc}
                  className="h-full w-full border-0"
                  loading="lazy"
                  referrerPolicy="no-referrer-when-downgrade"
                />
              </div>
            )}
          </div>
        </section>
      )}

      {/* ─── FAQ ─────────────────────────────────────────────────────── */}
      {(() => {
        const faqVisible = faq.filter((f) => f.q.trim() && f.a.trim());
        if (faqVisible.length === 0) return null;
        return (
          <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
            <h2 className="font-display text-2xl sm:text-3xl">Preguntas frecuentes</h2>
            <div className="mt-6 space-y-3">
              {faqVisible.map((f) => (
                <details
                  key={f.q}
                  className="group rounded-xl border hairline bg-surface px-4 py-3"
                >
                  <summary className="cursor-pointer list-none font-medium">{f.q}</summary>
                  <p className="mt-2 text-sm text-muted-foreground">{f.a}</p>
                </details>
              ))}
            </div>
          </section>
        );
      })()}

      {/* ─── Testimonios ─────────────────────────────────────────────── */}
      {(() => {
        const tv = testimonios.filter((t) => t.autor.trim() && t.texto.trim());
        if (tv.length === 0) return null;
        return (
          <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
            <h2 className="font-display text-2xl sm:text-3xl">Trabajaron acá</h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {tv.map((t, i) => (
                <figure key={i} className="rounded-xl border hairline bg-surface p-5">
                  <blockquote className="text-sm leading-relaxed text-ink">"{t.texto}"</blockquote>
                  <figcaption className="mt-3 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                    {t.autor}
                  </figcaption>
                </figure>
              ))}
            </div>
          </section>
        );
      })()}

      {/* ─── CTA WhatsApp ────────────────────────────────────────────── */}
      <section className="border-t hairline bg-ink text-amber px-4 py-12 lg:px-12 lg:py-16">
        <div className="max-w-2xl">
          <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-amber/70">
            ¿Tenés dudas?
          </div>
          <h2 className="mt-2 font-display text-3xl sm:text-4xl">Hablemos por WhatsApp</h2>
          <p className="mt-3 text-amber/80 max-w-lg">
            Te respondemos en el día. Contanos qué necesitás y armamos un presupuesto a medida.
          </p>
          <a
            href={`https://wa.me/${STUDIO_PHONE}?text=${encodeURIComponent("Hola Rambla! Quería consultar por el estudio.")}`}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-amber px-6 py-3 text-sm font-semibold text-ink transition hover:brightness-110"
          >
            <MessageCircle className="h-4 w-4" />
            Escribir por WhatsApp
          </a>
        </div>
      </section>

      <div className="h-20 lg:hidden" aria-hidden />
      <MobileBookCta priceLabel={priceLabel} />
      <CartDrawer allEquipos={[]} />
    </PublicLayout>
  );
}
