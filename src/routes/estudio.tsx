import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, Camera, Check, Sparkles, MessageCircle, Lightbulb, Snowflake, Users } from "lucide-react";
import { PublicLayout } from "@/components/rental/PublicLayout";
import { CartDrawer } from "@/components/rental/CartDrawer";
import { StudioBookingForm } from "@/components/studio/StudioBookingForm";
import { STUDIO, STUDIO_PHONE } from "@/data/studio";
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
    links: [
      { rel: "canonical", href: "https://ramblarental.com/estudio" },
    ],
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
        <span className="font-mono text-[9px] uppercase tracking-[0.3em]">
          {label}
        </span>
      </div>
    </div>
  );
}

function EstudioPage() {
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

      {/* Hero estudio */}
      <section className="px-4 py-8 lg:px-12 lg:py-12">
        <div className="grid gap-8 lg:grid-cols-2 lg:items-end">
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-amber px-3 py-1 font-mono text-[10px] uppercase tracking-[0.25em] text-ink">
              <Sparkles className="h-3 w-3" /> Producto estrella
            </div>
            <h1 className="mt-4 wordmark text-[14vw] leading-[0.9] md:text-[6rem] lg:text-[7rem] text-balance">
              {STUDIO.name}
            </h1>
            <p className="mt-4 max-w-lg text-base text-muted-foreground">
              {STUDIO.description}
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <a
                href="#reservar"
                className="rounded-full bg-foreground px-5 py-2.5 text-sm font-semibold text-background hover:bg-amber hover:text-ink"
              >
                Reservar
              </a>
              <a
                href="#pack"
                className="rounded-full border hairline px-5 py-2.5 text-sm hover:border-ink"
              >
                Ver pack todo incluido
              </a>
            </div>
          </div>
          <PhotoPlaceholder className="aspect-[4/3] w-full" label="FOTO PRINCIPAL" />
        </div>
      </section>

      {/* Galería */}
      <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
        <div className="mb-6 flex items-end justify-between gap-3">
          <h2 className="font-display text-2xl sm:text-3xl">Galería</h2>
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            {STUDIO.gallery} fotos
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4">
          {Array.from({ length: STUDIO.gallery }).map((_, i) => (
            <PhotoPlaceholder
              key={i}
              className="aspect-square w-full"
              label={`FOTO ${i + 1}`}
            />
          ))}
        </div>
      </section>

      {/* Características */}
      <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
        <h2 className="font-display text-2xl sm:text-3xl">Características</h2>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Todo lo que necesitás para producir sin sobresaltos.
        </p>
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {STUDIO.features.map((f) => (
            <div
              key={f.label}
              className="rounded-xl border hairline bg-surface p-4"
            >
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

      {/* Pack todo incluido */}
      <section
        id="pack"
        className="border-t hairline bg-amber text-ink px-4 py-10 lg:px-12 lg:py-14"
      >
        <div className="grid gap-6 lg:grid-cols-2 lg:gap-12">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-ink/70">
              Addon · monto fijo / día
            </div>
            <h2 className="mt-2 font-display text-3xl sm:text-4xl">
              {STUDIO.addon.name}
            </h2>
            <p className="mt-3 max-w-md text-ink/80">
              {STUDIO.addon.description}
            </p>
            <div className="mt-5 text-4xl font-semibold tabular">
              {STUDIO.addon.pricePerDay > 0
                ? `${formatARS(STUDIO.addon.pricePerDay)} / día`
                : "Consultar precio"}
            </div>
          </div>
          <ul className="space-y-2">
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
        </div>
      </section>

      {/* Reservar */}
      <section
        id="reservar"
        className="border-t hairline px-4 py-10 lg:px-12 lg:py-14 scroll-mt-32"
      >
        <h2 className="font-display text-2xl sm:text-3xl">Reservar</h2>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Mínimo {STUDIO.minHours} horas. Te confirmamos disponibilidad por
          WhatsApp.
        </p>
        <div className="mt-6">
          <StudioBookingForm />
        </div>
      </section>

      {/* FAQ */}
      <section className="border-t hairline px-4 py-10 lg:px-12 lg:py-14">
        <h2 className="font-display text-2xl sm:text-3xl">Preguntas frecuentes</h2>
        <div className="mt-6 space-y-3">
          {STUDIO.faq.map((f) => (
            <details
              key={f.q}
              className="group rounded-xl border hairline bg-surface px-4 py-3"
            >
              <summary className="cursor-pointer list-none font-medium">
                {f.q}
              </summary>
              <p className="mt-2 text-sm text-muted-foreground">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* CTA WhatsApp final */}
      <section className="border-t hairline bg-ink text-amber px-4 py-12 lg:px-12 lg:py-16">
        <div className="max-w-2xl">
          <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-amber/70">
            ¿Tenés dudas?
          </div>
          <h2 className="mt-2 font-display text-3xl sm:text-4xl">
            Hablemos por WhatsApp
          </h2>
          <p className="mt-3 text-amber/80 max-w-lg">
            Te respondemos en el día. Contanos qué necesitás y armamos un
            presupuesto a medida — incluso si tu producción es más grande de
            lo que entra en el formulario.
          </p>
          <a
            href={`https://wa.me/${STUDIO_PHONE}?text=${encodeURIComponent(
              "Hola Rambla! Quería consultar por el estudio."
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

function Feature({
  icon, title, desc,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
}) {
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
