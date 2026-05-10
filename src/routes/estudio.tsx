import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, Camera, Check, Sparkles } from "lucide-react";
import { TopBar } from "@/components/rental/TopBar";
import { CartDrawer } from "@/components/rental/CartDrawer";
import { StudioBookingForm } from "@/components/studio/StudioBookingForm";
import { STUDIO } from "@/data/studio";
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
      { property: "og:title", content: "El Estudio — Rambla Rental" },
      {
        property: "og:description",
        content:
          "Estudio de foto y video en Mar del Plata. Reservá por hora con pack de luces y griperías opcional.",
      },
    ],
  }),
  component: EstudioPage,
});

function PhotoPlaceholder({
  className,
  label = "FOTO",
}: {
  className?: string;
  label?: string;
}) {
  return (
    <div
      className={
        "relative flex items-center justify-center overflow-hidden rounded-xl bg-surface border hairline " +
        (className ?? "")
      }
    >
      <div className="absolute inset-0 grain opacity-30" />
      <div className="relative flex flex-col items-center gap-2 text-muted-foreground">
        <Camera className="h-8 w-8 opacity-50" />
        <span className="font-mono text-[10px] uppercase tracking-[0.3em]">
          {label}
        </span>
      </div>
    </div>
  );
}

function EstudioPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <TopBar />

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
              {STUDIO.tagline}. [Bajada placeholder: contanos qué tipo de
              producciones recibe el estudio, en qué se diferencia, qué buscás
              transmitir.]
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
          [Placeholder: completar con superficie, ciclorama, altura, equipo
          fijo, climatización, etc.]
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

      <footer className="border-t hairline px-4 py-10 lg:px-12">
        <div className="wordmark text-3xl text-amber">rambla</div>
        <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
          Rental · Mar del Plata
        </div>
      </footer>

      <CartDrawer allEquipos={[]} />
    </div>
  );
}
