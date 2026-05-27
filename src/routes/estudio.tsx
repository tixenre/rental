import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Camera, Check, MessageCircle } from "lucide-react";
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

/**
 * Galería con scroll-snap nativo (touch/swipe) + mouse-drag para desktop +
 * flechas. Sigue el patrón de CarouselRow (overflow-x-auto + snap-x), no
 * Embla, para que el feel sea idéntico al resto del sitio.
 */
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

  // Mouse-drag para desktop. En touch, el navegador maneja el swipe nativo.
  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== "mouse") return;
    const el = ref.current;
    if (!el) return;
    drag.current = {
      active: true,
      moved: false,
      startX: e.clientX,
      startScroll: el.scrollLeft,
    };
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
    // pequeña pausa para que un click justo después del drag no dispare onClick.
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
          // mouse-drag affordance en desktop
          "cursor-grab active:cursor-grabbing select-none",
          // touch nativo: dejar que el navegador haga el pan-x
          "touch-pan-x",
        )}
      >
        {items.map((it) => (
          <div
            key={it.key}
            className={cn(
              "snap-start shrink-0",
              // mobile casi full-bleed (deja un asomo del próximo);
              // sm: 2 por viewport; lg: ~2.6 por viewport
              "basis-[88%] sm:basis-[58%] lg:basis-[38%]",
              "aspect-[4/3] overflow-hidden rounded-xl bg-ink/5",
            )}
          >
            {it.node}
          </div>
        ))}
      </div>

      {/* Flechas: solo desktop, sobre la franja con padding suficiente. */}
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

/** Sticky CTA "Reservar" sólo en mobile. Se oculta cuando #reservar entra en viewport. */
function MobileBookCta({ priceLabel }: { priceLabel: string | null }) {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    const target = document.getElementById("reservar");
    if (!target) return;
    // Ocultar el sticky en cuanto cualquier parte del bloque de reserva
    // entra en viewport — ya no aporta y taparía el formulario.
    const obs = new IntersectionObserver(
      (entries) => {
        const e = entries[0];
        setHidden(e.isIntersecting);
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
  const packNombre = data?.pack_nombre ?? STUDIO.addon.name;
  const packDescripcion = data?.pack_descripcion ?? STUDIO.addon.description;
  const packPrecio = data?.pack_precio ?? STUDIO.addon.pricePerDay;
  const packEquipos = useMemo(() => data?.pack_equipos ?? [], [data?.pack_equipos]);
  const precioHora = data?.precio_hora ?? STUDIO.pricePerHour;
  const minHours = data?.min_horas ?? STUDIO.minHours;
  const direccion = data?.direccion ?? "";
  const comoLlegar = data?.como_llegar ?? "";
  const testimonios = data?.testimonios ?? [];

  // Foto principal para el hero: la marcada como principal o la primera.
  // El resto va a la galería (sin repetir la del hero).
  const fotoHero = fotos.find((f) => f.es_principal) ?? fotos[0];
  const fotosGaleria = useMemo(() => {
    if (!fotoHero) return fotos;
    return fotos.filter((f) => f.id !== fotoHero.id);
  }, [fotos, fotoHero]);

  const bookingConfig = data
    ? {
        pricePerHour: data.precio_hora,
        minHours: data.min_horas,
        openHour: data.open_hour,
        closeHour: data.close_hour,
        packActivo: data.pack_activo,
        packNombre: data.pack_nombre,
        packDescripcion: data.pack_descripcion,
        packPrecio: data.pack_precio,
      }
    : undefined;

  const priceLabel = precioHora > 0 ? `${formatARS(precioHora)}/hora · mín ${minHours}h` : null;
  const priceAnchor = precioHora > 0 ? `Desde ${formatARS(precioHora)}/h · mín ${minHours}h` : null;

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

      {/* ─── Hero ──────────────────────────────────────────────────────── */}
      <section className="px-4 pt-3 pb-8 lg:px-12 lg:pt-6 lg:pb-12">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:items-center lg:gap-10">
          <div className="order-2 lg:order-1">
            <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
              {tagline}
            </p>
            <h1 className="mt-2 wordmark text-[14vw] leading-[0.92] sm:text-[10vw] md:text-[5.5rem] lg:text-[6.25rem] text-balance">
              {nombre}
            </h1>
            <p className="mt-4 max-w-lg text-base text-muted-foreground">{descripcion}</p>

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
          </div>

          {/* Foto hero — full-bleed en mobile (cancela el px-4 del section con
              -mx-4 y saca el redondeo); en desktop vuelve a la celda del grid. */}
          <div className="order-1 lg:order-2 -mx-4 lg:mx-0">
            {fotoHero ? (
              <div className="aspect-[16/10] sm:aspect-[4/3] w-full overflow-hidden rounded-none lg:rounded-2xl bg-ink/5">
                <img
                  src={fotoHero.url}
                  alt={nombre}
                  className="h-full w-full object-cover"
                  loading="eager"
                />
              </div>
            ) : (
              <PhotoPlaceholder
                className="aspect-[16/10] sm:aspect-[4/3] w-full rounded-none lg:rounded-xl"
                label="FOTO PRINCIPAL"
              />
            )}
          </div>
        </div>
      </section>

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
          <StudioBookingForm config={bookingConfig} />
          {packActivo && (
            <aside className="rounded-2xl border hairline bg-amber/10 p-5 lg:sticky lg:top-20 lg:self-start">
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-ink/60">
                Pack · add-on opcional
              </div>
              <h3 className="mt-1 font-display text-xl">{packNombre}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{packDescripcion}</p>
              <div className="mt-3 text-2xl font-semibold tabular">
                {packPrecio > 0 ? formatARS(packPrecio) : "Consultar"}
              </div>
              {packEquipos.length > 0 ? (
                <StudioPackKit equipos={packEquipos} title="Equipos incluidos" />
              ) : (
                <ul className="mt-4 space-y-2">
                  {STUDIO.addon.includes.map((it) => (
                    <li
                      key={it}
                      className="flex items-start gap-2 rounded-lg bg-ink/5 px-3 py-2 text-sm"
                    >
                      <Check className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>{it}</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-3 text-xs text-muted-foreground">
                Activá el pack al reservar (en el formulario) — se incluye lo que esté disponible en
                tu franja.
              </p>
            </aside>
          )}
        </div>
      </section>

      {/* ─── Características del espacio ─────────────────────────────── */}
      <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
        <h2 className="font-display text-2xl sm:text-3xl">Características del espacio</h2>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Lo que vas a encontrar en el lugar. No incluye equipos ni staff — el equipamiento es el
          pack opcional de arriba.
        </p>
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {features.map((f) => (
            <div key={f.label} className="rounded-xl border hairline bg-surface p-4">
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                {f.label}
              </div>
              <div className="mt-1 text-lg font-semibold">{f.value}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ─── Ubicación ───────────────────────────────────────────────── */}
      {direccion && (
        <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
          <h2 className="font-display text-2xl sm:text-3xl">Dónde estamos</h2>
          <div className="mt-6 grid gap-6 lg:grid-cols-2 lg:items-start">
            <div>
              <p className="text-base text-ink">{direccion}</p>
              {comoLlegar && (
                <p className="mt-3 whitespace-pre-line text-sm text-muted-foreground">
                  {comoLlegar}
                </p>
              )}
              <a
                href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(direccion)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 inline-flex items-center gap-2 rounded-full border hairline bg-surface px-4 py-2 text-sm text-ink transition hover:border-ink"
              >
                Ver en Google Maps
              </a>
            </div>
            <div className="aspect-[4/3] w-full overflow-hidden rounded-2xl border hairline bg-ink/5">
              <iframe
                title="Mapa del estudio"
                src={`https://www.google.com/maps?q=${encodeURIComponent(direccion)}&output=embed`}
                className="h-full w-full border-0"
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
              />
            </div>
          </div>
        </section>
      )}

      {/* ─── FAQ ─────────────────────────────────────────────────────── */}
      {faq.length > 0 && (
        <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
          <h2 className="font-display text-2xl sm:text-3xl">Preguntas frecuentes</h2>
          <div className="mt-6 space-y-3">
            {faq.map((f) => (
              <details key={f.q} className="group rounded-xl border hairline bg-surface px-4 py-3">
                <summary className="cursor-pointer list-none font-medium">{f.q}</summary>
                <p className="mt-2 text-sm text-muted-foreground">{f.a}</p>
              </details>
            ))}
          </div>
        </section>
      )}

      {/* ─── Prueba social ───────────────────────────────────────────── */}
      {testimonios.length > 0 && (
        <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
          <h2 className="font-display text-2xl sm:text-3xl">Trabajaron acá</h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {testimonios.map((t, i) => (
              <figure key={i} className="rounded-xl border hairline bg-surface p-5">
                <blockquote className="text-sm leading-relaxed text-ink">“{t.texto}”</blockquote>
                <figcaption className="mt-3 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                  {t.autor}
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}

      {/* ─── CTA WhatsApp ────────────────────────────────────────────── */}
      <section className="border-t hairline bg-ink text-amber px-4 py-12 lg:px-12 lg:py-16">
        <div className="max-w-2xl">
          <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-amber/70">
            ¿Tenés dudas?
          </div>
          <h2 className="mt-2 font-display text-3xl sm:text-4xl">Hablemos por WhatsApp</h2>
          <p className="mt-3 text-amber/80 max-w-lg">
            Te respondemos en el día. Contanos qué necesitás y armamos un presupuesto a medida —
            incluso si tu producción es más grande de lo que entra en el formulario.
          </p>
          <a
            href={`https://wa.me/${STUDIO_PHONE}?text=${encodeURIComponent(
              "Hola Rambla! Quería consultar por el estudio.",
            )}`}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-amber px-6 py-3 text-sm font-semibold text-ink transition hover:brightness-110"
          >
            <MessageCircle className="h-4 w-4" />
            Escribir por WhatsApp
          </a>
        </div>
      </section>

      {/* Padding extra al final para que el sticky CTA mobile no tape contenido */}
      <div className="h-20 lg:hidden" aria-hidden />

      <MobileBookCta priceLabel={priceLabel} />

      <CartDrawer allEquipos={[]} />
    </PublicLayout>
  );
}
