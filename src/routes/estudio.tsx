import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Camera, Check, MessageCircle, Lightbulb, Snowflake, Users } from "lucide-react";
import { PublicLayout } from "@/components/rental/PublicLayout";
import { CartDrawer } from "@/components/rental/CartDrawer";
import { StudioBookingForm } from "@/components/studio/StudioBookingForm";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";
import { STUDIO, STUDIO_PHONE } from "@/data/studio";
import { apiGetEstudio, type EstudioConfig } from "@/lib/api";
import { formatARS } from "@/lib/format";

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
      className={
        "relative flex items-center justify-center overflow-hidden rounded-xl bg-gradient-to-br from-amber-soft via-surface to-amber-soft/40 border hairline " +
        (className ?? "")
      }
    >
      <div className="absolute inset-0 grain opacity-20" />
      <div className="relative flex flex-col items-center gap-2 text-ink/40">
        <Camera className="h-7 w-7" />
        <span className="font-mono text-[9px] uppercase tracking-[0.3em]">{label}</span>
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
  const fotos = data?.fotos ?? [];
  const packActivo = data?.pack_activo ?? true;
  const packNombre = data?.pack_nombre ?? STUDIO.addon.name;
  const packDescripcion = data?.pack_descripcion ?? STUDIO.addon.description;
  const packPrecio = data?.pack_precio ?? STUDIO.addon.pricePerDay;
  const minHours = data?.min_horas ?? STUDIO.minHours;

  // foto principal para el hero (primera marcada como principal, o primera)
  const fotoPrincipal = fotos.find((f) => f.es_principal) ?? fotos[0];

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

      {/* Hero compacto */}
      <section className="px-4 pt-4 pb-7 lg:px-12 lg:pb-10">
        <div className="grid gap-6 lg:grid-cols-2 lg:items-center">
          <div>
            <h1 className="wordmark text-[12vw] leading-[0.95] md:text-[4.5rem] lg:text-[5.5rem] text-balance">
              {nombre}
            </h1>
            <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
              {tagline}
            </p>
            <p className="mt-4 max-w-lg text-sm sm:text-base text-muted-foreground">
              {descripcion}
            </p>
          </div>
          {fotoPrincipal ? (
            <div className="aspect-[4/3] w-full overflow-hidden rounded-xl">
              <img src={fotoPrincipal.url} alt={nombre} className="h-full w-full object-cover" />
            </div>
          ) : (
            <PhotoPlaceholder className="aspect-[4/3] w-full" label="FOTO PRINCIPAL" />
          )}
        </div>
      </section>

      {/* Reservar + Pack (acción principal, arriba) */}
      <section id="reservar" className="border-t hairline px-4 py-8 lg:px-12 lg:py-10 scroll-mt-24">
        <h2 className="font-display text-2xl sm:text-3xl">Reservá el estudio</h2>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Mínimo {minHours} horas. Elegí día y horario y reservá online — te contactamos para
          confirmar.
        </p>
        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:items-start">
          <StudioBookingForm config={bookingConfig} />
          {packActivo && (
            <aside className="rounded-2xl border hairline bg-amber/10 p-5">
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-ink/60">
                Pack · monto fijo
              </div>
              <h3 className="mt-1 font-display text-xl">{packNombre}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{packDescripcion}</p>
              <div className="mt-3 text-2xl font-semibold tabular">
                {packPrecio > 0 ? formatARS(packPrecio) : "Consultar"}
              </div>
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
              <p className="mt-3 text-xs text-muted-foreground">
                Activá el pack al reservar (en el formulario) — se incluye lo que esté disponible en
                tu franja.
              </p>
            </aside>
          )}
        </div>
      </section>

      {/* Galería — carrusel */}
      {(fotos.length > 0 || !data) && (
        <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
          <div className="mb-6 flex items-end justify-between gap-3">
            <h2 className="font-display text-2xl sm:text-3xl">Galería</h2>
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              {fotos.length > 0 ? `${fotos.length} fotos` : `${STUDIO.gallery} fotos`}
            </span>
          </div>
          <Carousel opts={{ align: "start" }} className="w-full">
            <CarouselContent className="-ml-3">
              {fotos.length > 0
                ? fotos.map((foto) => (
                    <CarouselItem
                      key={foto.id}
                      className="basis-4/5 pl-3 sm:basis-1/2 lg:basis-1/3"
                    >
                      <div className="aspect-[4/3] w-full overflow-hidden rounded-xl">
                        <img
                          src={foto.url}
                          alt=""
                          className="h-full w-full object-cover"
                          loading="lazy"
                        />
                      </div>
                    </CarouselItem>
                  ))
                : Array.from({ length: STUDIO.gallery }).map((_, i) => (
                    <CarouselItem key={i} className="basis-4/5 pl-3 sm:basis-1/2 lg:basis-1/3">
                      <PhotoPlaceholder className="aspect-[4/3] w-full" label={`FOTO ${i + 1}`} />
                    </CarouselItem>
                  ))}
            </CarouselContent>
            <CarouselPrevious className="hidden sm:flex" />
            <CarouselNext className="hidden sm:flex" />
          </Carousel>
          <p className="mt-3 text-center text-[10px] uppercase tracking-[0.25em] text-muted-foreground sm:hidden">
            Deslizá para ver más
          </p>
        </section>
      )}

      {/* Características */}
      <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
        <h2 className="font-display text-2xl sm:text-3xl">Características</h2>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Todo lo que necesitás para producir sin sobresaltos.
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

      {/* Por qué elegirnos */}
      <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
        <h2 className="font-display text-2xl sm:text-3xl">Por qué Rambla</h2>
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Feature
            icon={<Lightbulb className="h-5 w-5" />}
            title="Todo a mano"
            desc="Acceso directo al catálogo de Rambla — sumás cámara, lentes o luces extra al pedido del estudio."
          />
          <Feature
            icon={<Snowflake className="h-5 w-5" />}
            title="Espacio confortable"
            desc="Climatización, baño privado y zona de descanso para staff y modelos."
          />
          <Feature
            icon={<Users className="h-5 w-5" />}
            title="Atendido por nosotros"
            desc="No es un coworking automatizado. Te recibimos, te resolvemos dudas técnicas y te asistimos si lo necesitás."
          />
        </div>
      </section>

      {/* FAQ */}
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

      {/* CTA WhatsApp final */}
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

      <CartDrawer allEquipos={[]} />
    </PublicLayout>
  );
}

function Feature({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="rounded-xl border hairline bg-surface p-5 hover:border-ink/20 transition">
      <div className="grid h-10 w-10 place-items-center rounded-md bg-amber-soft text-ink">
        {icon}
      </div>
      <h3 className="mt-3 font-display text-lg text-ink">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{desc}</p>
    </div>
  );
}
