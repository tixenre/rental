import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { createLazyFileRoute, Link, notFound } from "@tanstack/react-router";
import { Calendar, MapPin, Users, CheckCircle2, Clock, X } from "lucide-react";

import { PublicLayout } from "@/components/rental/PublicLayout";
import { Button } from "@/design-system/ui/button";
import { Logo } from "@/components/rental/Logo";
import { WorkshopInscripcionForm } from "@/components/talleres/WorkshopInscripcionForm";
import { TallerCalendario } from "@/components/talleres/TallerCalendario";
import { ResponsiveImage } from "@/components/common/ResponsiveImage";
import { apiGetTaller, type EdicionLite, type Taller } from "@/lib/api";
import { formatARS } from "@/lib/format";
import { useEntityMedia } from "@/hooks/useEntityMedia";
import { findVariant } from "@/lib/media/types";

export const Route = createLazyFileRoute("/workshops/$slug")({
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
      <span className="shrink-0 mt-0.5 w-5 h-5 rounded-full bg-rosa text-white text-xs font-bold grid place-items-center">
        {index + 1}
      </span>
      <span className="text-sm leading-relaxed text-muted-foreground">{text}</span>
    </li>
  );
}

function ordinalEdicion(n: number): string {
  const map: Record<number, string> = { 1: "1ra", 2: "2da", 3: "3ra", 4: "4ta" };
  return map[n] ?? `${n}ta`;
}

function SoldOutModal({
  proxima,
  currentEdicion,
  onDismiss,
}: {
  proxima: EdicionLite;
  currentEdicion: number;
  onDismiss: () => void;
}) {
  const opts: Intl.DateTimeFormatOptions = { weekday: "long", day: "numeric", month: "long" };
  const fechaA = new Date(proxima.fecha_inicio + "T12:00:00").toLocaleDateString("es-AR", opts);
  const fechaB = new Date(proxima.fecha_fin + "T12:00:00").toLocaleDateString("es-AR", opts);
  const labelActual = ordinalEdicion(currentEdicion);
  const labelProxima = ordinalEdicion(proxima.numero_edicion);
  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 sm:p-6"
      style={{ background: "oklch(0.15 0 0 / 65%)" }}
      onClick={(e) => e.target === e.currentTarget && onDismiss()}
    >
      <div className="relative w-full max-w-sm rounded-2xl bg-background border border-border/60 p-7 shadow-2xl">
        <button
          onClick={onDismiss}
          aria-label="Cerrar"
          className="absolute top-4 right-4 p-1.5 rounded-full text-muted-foreground hover:text-ink hover:bg-muted transition"
        >
          <X className="h-4 w-4" />
        </button>
        <p className="font-mono text-2xs tracking-[0.25em] uppercase text-rosa mb-3">
          {labelActual} edición
        </p>
        <h2
          className="font-display font-bold lowercase text-ink leading-tight mb-2"
          style={{ fontSize: "1.6rem" }}
        >
          los cupos se agotaron
        </h2>
        <p className="text-sm text-muted-foreground mb-6">
          Pero hay lugar en la <strong className="text-ink">{labelProxima} edición</strong> —{" "}
          {fechaA} y {fechaB}.
        </p>
        <Link
          to="/workshops/$slug"
          params={{ slug: proxima.slug }}
          className="flex items-center justify-center w-full rounded-full bg-rosa text-ink font-bold py-3 hover:brightness-110 active:scale-[0.97] transition-all"
          onClick={onDismiss}
        >
          Inscribirme en la {labelProxima} edición
        </Link>
        <button
          onClick={onDismiss}
          className="w-full mt-3 text-sm text-muted-foreground hover:text-ink transition py-1"
        >
          Cerrar
        </button>
      </div>
    </div>
  );
}

// ── InteresadoForm ────────────────────────────────────────────────────────────

function InteresadoForm({ slug }: { slug: string }) {
  const [form, setForm] = useState({ nombre: "", email: "", telefono: "" });
  const [status, setStatus] = useState<"idle" | "sending" | "ok" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.nombre.trim() || !form.email.trim()) return;
    setStatus("sending");
    try {
      const res = await fetch(`/api/talleres/${slug}/interesado`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j?.detail ?? `Error ${res.status}`);
      }
      setStatus("ok");
    } catch (err) {
      setErrorMsg((err as Error).message);
      setStatus("error");
    }
  }

  if (status === "ok") {
    return (
      <div className="rounded-2xl border border-verde/40 bg-verde/10 px-5 py-6 text-center">
        <CheckCircle2 className="h-8 w-8 text-verde mx-auto mb-3" strokeWidth={1.5} />
        <p className="font-semibold text-ink">¡Anotado/a!</p>
        <p className="text-sm text-muted-foreground mt-1">Te avisamos cuando haya nuevas fechas.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
        Avisame si hay más fechas
      </p>
      <input
        required
        type="text"
        placeholder="Tu nombre"
        value={form.nombre}
        onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
        className="w-full rounded-xl border border-input bg-background px-4 py-3 text-sm text-ink placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <input
        required
        type="email"
        placeholder="Tu email"
        value={form.email}
        onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
        className="w-full rounded-xl border border-input bg-background px-4 py-3 text-sm text-ink placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <input
        type="tel"
        placeholder="Tu teléfono (opcional)"
        value={form.telefono}
        onChange={(e) => setForm((f) => ({ ...f, telefono: e.target.value }))}
        className="w-full rounded-xl border border-input bg-background px-4 py-3 text-sm text-ink placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      />
      {status === "error" && <p className="text-xs text-destructive">{errorMsg}</p>}
      <Button
        type="submit"
        variant="amber"
        shape="pill"
        disabled={status === "sending"}
        className="w-full py-3.5 text-base font-bold"
      >
        {status === "sending" ? "Enviando…" : "Avisame"}
      </Button>
    </form>
  );
}

// ── TallerLandingPage ─────────────────────────────────────────────────────────

function TallerLandingPage() {
  const { slug } = Route.useParams();
  const {
    data: taller,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["taller", slug],
    queryFn: () => apiGetTaller(slug),
    staleTime: 0,
  });

  // Hooks antes del early-return (regla de hooks de React)
  const [soldOutModalDismissed, setSoldOutModalDismissed] = useState(false);
  const tallerId = taller?.id ?? null;
  const { data: instructorMedia } = useEntityMedia("instructor", tallerId);
  const instructorAsset = instructorMedia[0] ?? null;
  const instructorVariant = instructorAsset
    ? findVariant(instructorAsset.variants, "display")
    : null;

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

  const proxima = taller.proxima_edicion;
  const isFrozen = taller.frozen_at != null;
  const isFullySoldOut = !isFrozen && taller.cupos_disponibles === 0 && proxima == null;
  const switchToProxima =
    !isFrozen && taller.cupos_disponibles === 0 && proxima != null && proxima.cupos_disponibles > 0;
  const formTaller: Taller = switchToProxima ? ({ ...taller, ...proxima } as Taller) : taller;

  // Cuando está sold out, las fechas de toda la página muestran la 2da edición
  const optsLong: Intl.DateTimeFormatOptions = { weekday: "long", day: "numeric", month: "long" };
  const fechaInicio = new Date(formTaller.fecha_inicio + "T12:00:00");
  const fechaFin = new Date(formTaller.fecha_fin + "T12:00:00");
  const fechaInicioStr = fechaInicio.toLocaleDateString("es-AR", optsLong);
  const fechaFinStr = fechaFin.toLocaleDateString("es-AR", optsLong);

  return (
    <>
      {switchToProxima && !soldOutModalDismissed && (
        <SoldOutModal
          proxima={proxima!}
          currentEdicion={taller.numero_edicion}
          onDismiss={() => setSoldOutModalDismissed(true)}
        />
      )}
      <PublicLayout
        topBar={{ variant: "workshops", cta: { label: "Inscribirme", href: "#inscripcion" } }}
      >
        <div className="min-h-dvh bg-background">
          {/* ── Hero ───────────────────────────────────────────────────────── */}
          <section className="relative bg-ink overflow-hidden">
            <Grain opacity={10} />
            <div className="relative max-w-[1100px] mx-auto px-4 sm:px-6 py-16 sm:py-24">
              <p className="font-mono text-2xs tracking-[0.3em] uppercase text-rosa mb-4">
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
                  color: "color-mix(in oklch, var(--color-rosa) 80%, white)",
                }}
              >
                {taller.subtitulo}
              </p>
              <p
                className="font-display font-black lowercase leading-tight tracking-[-0.02em] mt-2"
                style={{
                  fontSize: "clamp(1.5rem, 4vw, 3rem)",
                  color: "color-mix(in oklch, var(--color-rosa) 55%, white 45%)",
                }}
              >
                {ordinalEdicion(taller.numero_edicion)} edición
              </p>

              {/* Contexto de ediciones */}
              {(taller.edicion_anterior ||
                (taller.proxima_edicion && taller.cupos_disponibles === 0)) && (
                <div className="mt-5 flex flex-wrap items-center gap-4">
                  {taller.edicion_anterior && (
                    <Link
                      to="/workshops/$slug"
                      params={{ slug: taller.edicion_anterior.slug }}
                      className="text-xs text-background/35 hover:text-background/60 transition"
                    >
                      {ordinalEdicion(taller.edicion_anterior.numero_edicion)} edición — agotada
                    </Link>
                  )}
                  {taller.proxima_edicion && taller.cupos_disponibles === 0 && (
                    <Link
                      to="/workshops/$slug"
                      params={{ slug: taller.proxima_edicion.slug }}
                      className="inline-flex items-center gap-2 rounded-full border border-rosa/50 bg-rosa/10 px-4 py-1.5 text-sm font-semibold text-rosa hover:bg-rosa/20 transition"
                    >
                      {ordinalEdicion(taller.proxima_edicion.numero_edicion)} edición{" "}
                      <span className="opacity-70">
                        · {taller.proxima_edicion.cupos_disponibles} cupos
                      </span>
                    </Link>
                  )}
                </div>
              )}

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
                  className="inline-flex items-center gap-2 rounded-full bg-rosa text-ink px-7 py-3.5 text-base font-bold hover:brightness-110 active:scale-[0.97] transition-all"
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

                {/* Cuándo */}
                {formTaller.sesiones && formTaller.sesiones.length > 0 && (
                  <section>
                    <p className="font-mono text-2xs tracking-[0.25em] uppercase text-rosa mb-4">
                      Cuándo
                    </p>
                    <TallerCalendario sesiones={formTaller.sesiones} horario={formTaller.horario} />
                  </section>
                )}

                {/* Clase teórica */}
                {taller.programa_teorica.length > 0 && (
                  <section>
                    <div className="mb-4">
                      <p className="font-mono text-2xs tracking-[0.25em] uppercase text-rosa mb-1">
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
                      en la clase siguiente. Nos dividiremos en equipos y tendrán 1 semana de
                      preproducción.
                    </p>
                  </section>
                )}

                {/* Clase práctica */}
                {taller.programa_practica.length > 0 && (
                  <section>
                    <div className="mb-4">
                      <p className="font-mono text-2xs tracking-[0.25em] uppercase text-rosa mb-1">
                        Clase 2 — Práctica
                      </p>
                      <h2 className="font-display text-2xl font-bold text-ink lowercase tracking-tight">
                        {fechaFinStr}, {taller.horario}
                      </h2>
                    </div>
                    <div className="flex flex-col gap-4">
                      {taller.programa_practica.map((item, i) => (
                        <p key={i} className="text-sm leading-relaxed text-foreground/80">
                          {item}
                        </p>
                      ))}
                    </div>
                  </section>
                )}

                {/* About */}
                <section className="rounded-2xl border border-border/60 bg-muted/20 px-6 py-7">
                  <p className="font-mono text-2xs tracking-[0.25em] uppercase text-muted-foreground mb-4">
                    Sobre
                  </p>
                  <div className="flex items-start gap-5 mb-5">
                    {(instructorVariant || taller.instructor_foto_url) &&
                      (instructorAsset && instructorAsset.variants.length > 0 ? (
                        <ResponsiveImage
                          variants={instructorAsset.variants}
                          alt={taller.instructor_nombre}
                          lqip={instructorAsset.lqip}
                          className="shrink-0 w-20 h-20 rounded-full object-cover object-top border border-border/40"
                          sizes="80px"
                        />
                      ) : (
                        <img
                          src={taller.instructor_foto_url}
                          alt={taller.instructor_nombre}
                          className="shrink-0 w-20 h-20 rounded-full object-cover object-top border border-border/40"
                        />
                      ))}
                    <h2
                      className="font-display font-black lowercase leading-[0.9] tracking-[-0.02em] text-ink self-center"
                      style={{ fontSize: "clamp(1.75rem, 3.5vw, 2.5rem)" }}
                    >
                      {taller.instructor_nombre}
                    </h2>
                  </div>
                  <p className="text-base text-ink/80 leading-relaxed">{taller.instructor_bio}</p>
                  {taller.instructor_proyectos?.length > 0 && (
                    <div className="mt-6">
                      <p className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground mb-3">
                        Trabajó con
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {(Array.isArray(taller.instructor_proyectos)
                          ? taller.instructor_proyectos
                          : String(taller.instructor_proyectos)
                              .split(",")
                              .map((s: string) => s.trim())
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
                    {(() => {
                      const porcentaje =
                        taller.precio_total > 0
                          ? Math.round((taller.precio_sena / taller.precio_total) * 100)
                          : 0;
                      const senaText = `Seña del ${porcentaje}% al inscribirte (${formatARS(taller.precio_sena)})`;
                      return [senaText, `Resto antes de la primera clase`];
                    })().map((item) => (
                      <li
                        key={item}
                        className="flex items-start gap-2 text-xs text-muted-foreground"
                      >
                        <CheckCircle2
                          className="h-3.5 w-3.5 shrink-0 mt-0.5 text-verde"
                          strokeWidth={1.5}
                        />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Formulario de inscripción */}
                <div id="inscripcion" className="scroll-mt-20">
                  {isFrozen ? (
                    <div className="rounded-2xl border border-border/60 bg-muted/20 px-5 py-6 text-center">
                      <p className="text-sm font-medium text-ink mb-1">Inscripciones cerradas</p>
                      <p className="text-xs text-muted-foreground">
                        Esta edición ya no acepta nuevas inscripciones.
                      </p>
                    </div>
                  ) : isFullySoldOut ? (
                    <>
                      <div className="mb-4 rounded-xl border border-border/60 bg-ink px-4 py-3 text-background">
                        <p className="text-xs font-mono uppercase tracking-widest opacity-50 mb-0.5">
                          {ordinalEdicion(taller.numero_edicion)} edición
                        </p>
                        <p className="font-bold text-sm">Sold out</p>
                        <p className="text-xs opacity-60 mt-1">Sin fechas próximas por ahora.</p>
                      </div>
                      <InteresadoForm slug={taller.slug} />
                    </>
                  ) : (
                    <>
                      {switchToProxima && (
                        <div className="mb-4 rounded-xl border border-border/60 bg-ink px-4 py-3 text-background">
                          <p className="text-xs font-mono uppercase tracking-widest opacity-50 mb-0.5">
                            {ordinalEdicion(taller.numero_edicion)} edición
                          </p>
                          <p className="font-bold text-sm">Sold out</p>
                          <p className="text-xs opacity-60 mt-1">
                            Te anotamos en la {ordinalEdicion(proxima!.numero_edicion)} edición (
                            {new Date(proxima!.fecha_inicio + "T12:00:00").toLocaleDateString(
                              "es-AR",
                              { day: "numeric", month: "long" },
                            )}{" "}
                            y{" "}
                            {new Date(proxima!.fecha_fin + "T12:00:00").toLocaleDateString(
                              "es-AR",
                              {
                                day: "numeric",
                                month: "long",
                              },
                            )}
                            )
                          </p>
                        </div>
                      )}
                      <WorkshopInscripcionForm taller={formTaller} />
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* ── Footer mínimo ──────────────────────────────────────────────── */}
          <footer className="border-t border-border/60 py-8 mt-8">
            <div className="max-w-[1100px] mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
              <Logo className="h-5 w-auto opacity-50" />
              <span>{taller.direccion}</span>
              <Link to="/rental" className="hover:text-ink transition">
                Volver al catálogo
              </Link>
            </div>
          </footer>
        </div>
      </PublicLayout>
    </>
  );
}
