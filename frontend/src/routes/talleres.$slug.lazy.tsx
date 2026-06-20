import { useQuery } from "@tanstack/react-query";
import { createLazyFileRoute, Link, notFound } from "@tanstack/react-router";
import {
  ArrowLeft,
  Calendar,
  MapPin,
  Users,
  CheckCircle2,
  Clock,
  ChevronRight,
} from "lucide-react";

import { Logo } from "@/components/rental/Logo";
import { WorkshopInscripcionForm } from "@/components/talleres/WorkshopInscripcionForm";
import { apiGetTaller, type Taller } from "@/lib/api";
import { formatARS } from "@/lib/format";

export const Route = createLazyFileRoute("/talleres/$slug")({
  component: TallerLandingPage,
});

const Grain = ({ opacity = 8 }: { opacity?: number }) => (
  <div
    className="pointer-events-none absolute inset-0"
    style={{
      backgroundImage: "radial-gradient(circle, oklch(0.85 0 0 / 12%) 1px, transparent 1px)",
      backgroundSize: "5px 5px",
      opacity: opacity / 100,
    }}
  />
);

function ProgramaItem({ text, index }: { text: string; index: number }) {
  return (
    <li className="flex items-start gap-3">
      <span className="shrink-0 mt-0.5 w-5 h-5 rounded-full bg-amber/20 text-amber-700 text-xs font-bold grid place-items-center">
        {index + 1}
      </span>
      <span className="text-sm leading-relaxed text-muted-foreground">{text}</span>
    </li>
  );
}

function TallerLandingPage() {
  const { slug } = Route.useParams();
  const { data: taller, isLoading, isError } = useQuery({
    queryKey: ["taller", slug],
    queryFn: () => apiGetTaller(slug),
    staleTime: 1000 * 60 * 5,
  });

  if (isLoading) {
    return (
      <div className="min-h-dvh flex items-center justify-center text-muted-foreground text-sm">
        Cargando…
      </div>
    );
  }

  if (isError || !taller) {
    throw notFound();
  }

  const fechaInicio = new Date(taller.fecha_inicio + "T12:00:00");
  const fechaFin = new Date(taller.fecha_fin + "T12:00:00");
  const optsLong: Intl.DateTimeFormatOptions = { weekday: "long", day: "numeric", month: "long" };
  const fechaInicioStr = fechaInicio.toLocaleDateString("es-AR", optsLong);
  const fechaFinStr = fechaFin.toLocaleDateString("es-AR", optsLong);

  return (
    <div className="min-h-dvh bg-background">
      {/* ── Sticky header ──────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 border-b border-border/60 bg-background/95 backdrop-blur-md">
        <div className="max-w-[1100px] mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
          <Link to="/talleres" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-ink transition">
            <ArrowLeft className="h-3.5 w-3.5" />
            Talleres
          </Link>
          <Logo className="h-6 w-auto" />
          <a
            href="#inscripcion"
            className="inline-flex items-center gap-1.5 rounded-full bg-ink text-amber px-4 py-2 text-sm font-bold hover:brightness-110 transition"
          >
            Inscribirme <ChevronRight className="h-3.5 w-3.5" />
          </a>
        </div>
      </header>

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="relative bg-ink overflow-hidden">
        <Grain opacity={10} />
        <div className="relative max-w-[1100px] mx-auto px-4 sm:px-6 py-16 sm:py-24">
          <p className="font-mono text-[0.625rem] tracking-[0.3em] uppercase text-amber mb-4">
            Workshop
          </p>
          <h1
            className="font-display font-black lowercase leading-[0.88] tracking-[-0.02em] text-background"
            style={{ fontSize: "clamp(2.75rem, 8vw, 5.5rem)" }}
          >
            {taller.nombre}
          </h1>
          <p
            className="font-display font-black lowercase leading-[0.88] tracking-[-0.02em] mt-1"
            style={{
              fontSize: "clamp(2.75rem, 8vw, 5.5rem)",
              color: "color-mix(in oklch, var(--amber) 70%, white)",
            }}
          >
            {taller.subtitulo}
          </p>

          <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm text-background/60">
            <span className="flex items-center gap-2">
              <Calendar className="h-4 w-4 shrink-0" />
              {fechaInicioStr} y {fechaFinStr}
            </span>
            <span className="flex items-center gap-2">
              <Clock className="h-4 w-4 shrink-0" />
              {taller.horario}
            </span>
            <span className="flex items-center gap-2">
              <MapPin className="h-4 w-4 shrink-0" />
              {taller.direccion}
            </span>
            <span className="flex items-center gap-2">
              <Users className="h-4 w-4 shrink-0" />
              {taller.cupos_total} cupos
            </span>
          </div>

          <div className="mt-8">
            <a
              href="#inscripcion"
              className="inline-flex items-center gap-2 rounded-full bg-amber text-ink px-7 py-3.5 text-base font-bold hover:brightness-110 active:scale-[0.97] transition-all"
            >
              Quiero inscribirme
            </a>
          </div>
        </div>
      </section>

      {/* ── Cuerpo ─────────────────────────────────────────────────────── */}
      <div className="max-w-[1100px] mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="grid lg:grid-cols-[1fr_380px] gap-10 lg:gap-16 items-start">

          {/* Columna principal */}
          <div className="flex flex-col gap-12">

            {/* Descripción + público */}
            <section>
              <p className="text-base sm:text-lg leading-relaxed text-muted-foreground">
                {taller.descripcion}
              </p>
              {taller.publico_objetivo && (
                <div className="mt-6 rounded-xl bg-muted/30 border border-border/50 px-5 py-4">
                  <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-2">
                    Orientado a
                  </p>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {taller.publico_objetivo}
                  </p>
                </div>
              )}
            </section>

            {/* Clase teórica */}
            {taller.programa_teorica.length > 0 && (
              <section>
                <div className="mb-4">
                  <p className="font-mono text-[0.625rem] tracking-[0.25em] uppercase text-amber mb-1">
                    Clase 1 — Teórica
                  </p>
                  <h2 className="font-display text-2xl font-bold text-ink lowercase tracking-tight">
                    {fechaInicioStr}, {taller.horario}
                  </h2>
                </div>
                <ul className="flex flex-col gap-3">
                  {taller.programa_teorica.map((item, i) => (
                    <ProgramaItem key={i} text={item} index={i} />
                  ))}
                </ul>
                <p className="mt-5 text-sm text-muted-foreground italic">
                  Al finalizar la clase teórica, elegiremos sobre qué proyecto queremos trabajar
                  en la clase siguiente. Nos dividiremos en equipos y tendrán 1 semana de preproducción.
                </p>
              </section>
            )}

            {/* Clase práctica */}
            {taller.programa_practica.length > 0 && (
              <section>
                <div className="mb-4">
                  <p className="font-mono text-[0.625rem] tracking-[0.25em] uppercase text-amber mb-1">
                    Clase 2 — Práctica
                  </p>
                  <h2 className="font-display text-2xl font-bold text-ink lowercase tracking-tight">
                    {fechaFinStr}, {taller.horario}
                  </h2>
                </div>
                <ul className="flex flex-col gap-3">
                  {taller.programa_practica.map((item, i) => (
                    <ProgramaItem key={i} text={item} index={i} />
                  ))}
                </ul>
              </section>
            )}

            {/* About */}
            <section className="rounded-2xl border border-border/60 bg-muted/20 px-6 py-7">
              <p className="font-mono text-[0.625rem] tracking-[0.25em] uppercase text-muted-foreground mb-4">
                Sobre
              </p>
              <h2
                className="font-display font-black lowercase leading-[0.9] tracking-[-0.02em] text-ink mb-5"
                style={{ fontSize: "clamp(1.75rem, 3.5vw, 2.5rem)" }}
              >
                {taller.instructor_nombre}
              </h2>
              <p className="text-base text-ink/80 leading-relaxed">
                {taller.instructor_bio}
              </p>
              {taller.instructor_proyectos?.length > 0 && (
                <div className="mt-6">
                  <p className="font-mono text-[0.625rem] tracking-[0.2em] uppercase text-muted-foreground mb-3">
                    Trabajó con
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {(Array.isArray(taller.instructor_proyectos)
                      ? taller.instructor_proyectos
                      : String(taller.instructor_proyectos).split(",").map((s: string) => s.trim())
                    ).map((p: string) => (
                      <span
                        key={p}
                        className="inline-block rounded-full border border-border/60 bg-background px-3 py-1 text-xs font-medium text-ink/70"
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </section>

          </div>

          {/* Sidebar sticky */}
          <div className="lg:sticky lg:top-20">
            {/* Precio */}
            <div className="rounded-2xl border border-border/60 bg-background p-5 mb-4">
              <p className="text-xs text-muted-foreground mb-1">Costo total</p>
              <p className="font-display text-3xl font-bold text-ink tabular-nums">
                {formatARS(taller.precio_total)}
              </p>
              <ul className="mt-3 flex flex-col gap-1.5">
                {[
                  `Seña del 50% al inscribirte (${formatARS(taller.precio_sena)})`,
                  `Resto antes de la primera clase`,
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2 text-xs text-muted-foreground">
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0 mt-0.5 text-green-500" strokeWidth={1.5} />
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            {/* Formulario de inscripción */}
            <div id="inscripcion" className="scroll-mt-20">
              <WorkshopInscripcionForm taller={taller} />
            </div>
          </div>
        </div>
      </div>

      {/* ── Footer mínimo ──────────────────────────────────────────────── */}
      <footer className="border-t border-border/60 py-8 mt-8">
        <div className="max-w-[1100px] mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
          <Logo className="h-5 w-auto opacity-50" />
          <span>{taller.direccion}</span>
          <Link to="/" className="hover:text-ink transition">
            Volver al catálogo
          </Link>
        </div>
      </footer>
    </div>
  );
}
