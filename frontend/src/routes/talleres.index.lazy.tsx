import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Calendar, MapPin, Users } from "lucide-react";

import { PublicLayout } from "@/components/rental/PublicLayout";
import { apiGetTalleres, type Taller } from "@/lib/api";
import { formatARS } from "@/lib/format";

export const Route = createLazyFileRoute("/talleres/")({
  component: TalleresPage,
});

// ── Talleres pasados (hardcodeados, sin landing) ──────────────────────────────
type PastWorkshop = {
  nombre: string;
  subtitulo: string;
  descripcion: string;
  fechaLabel: string;
  direccion: string;
};

const TALLERES_PASADOS: PastWorkshop[] = [
  {
    nombre: "Taller de Rodaje",
    subtitulo: "rambla × filmar escuela",
    descripcion:
      "Espacio práctico de análisis y grabación. Los alumnos debaten y crean escenas de películas, video clips, publicidades y fashion films con equipos profesionales de Rambla Rental.",
    fechaLabel: "Abril – junio 2026 · Miércoles",
    direccion: "Chaco 1392 — Rambla Estudio",
  },
  {
    nombre: "Taller de Rodaje",
    subtitulo: "rambla × filmar escuela",
    descripcion:
      "Espacio práctico de análisis y grabación. Los alumnos debaten y crean escenas de películas, video clips, publicidades y fashion films con equipos profesionales de Rambla Rental.",
    fechaLabel: "Octubre – diciembre 2025 · Miércoles",
    direccion: "Chaco 1392 — Rambla Estudio",
  },
];

// ── Grain overlay ─────────────────────────────────────────────────────────────
function Grain() {
  return (
    <div
      className="pointer-events-none absolute inset-0 opacity-[0.06]"
      style={{
        backgroundImage: "radial-gradient(circle, white 1px, transparent 1px)",
        backgroundSize: "5px 5px",
      }}
    />
  );
}

// ── Card activa (horizontal) ──────────────────────────────────────────────────
function WorkshopCard({ taller }: { taller: Taller }) {
  const fechaInicio = new Date(taller.fecha_inicio + "T12:00:00");
  const fechaFin = new Date(taller.fecha_fin + "T12:00:00");
  const optsDate: Intl.DateTimeFormatOptions = { day: "numeric", month: "long" };
  const fechaStr =
    fechaInicio.getTime() === fechaFin.getTime()
      ? fechaInicio.toLocaleDateString("es-AR", optsDate)
      : `${fechaInicio.toLocaleDateString("es-AR", optsDate)} – ${fechaFin.toLocaleDateString("es-AR", optsDate)}`;

  const cuposLabel =
    taller.cupos_disponibles > 0
      ? `${taller.cupos_disponibles} lugar${taller.cupos_disponibles === 1 ? "" : "es"} disponible${taller.cupos_disponibles === 1 ? "" : "s"}`
      : "Lista de espera";

  return (
    <Link
      to="/talleres/$slug"
      params={{ slug: taller.slug }}
      className="group flex flex-col sm:flex-row rounded-2xl border border-border/60 bg-background overflow-hidden hover:border-rosa/40 hover:shadow-md transition-all duration-200"
    >
      {/* Bloque oscuro izquierdo */}
      <div className="relative bg-ink sm:w-64 shrink-0 px-6 pt-7 pb-6 flex flex-col justify-between overflow-hidden min-h-[130px] sm:min-h-0">
        <Grain />
        <div className="relative">
          <p className="font-mono text-[0.625rem] tracking-[0.25em] uppercase text-rosa mb-3">
            Workshop
          </p>
          <h2
            className="font-display font-black lowercase leading-[0.9] tracking-[-0.015em] text-background"
            style={{ fontSize: "clamp(1.2rem, 2vw, 1.5rem)" }}
          >
            {taller.nombre}
          </h2>
          <p className="text-background/55 mt-1.5 text-sm">{taller.subtitulo}</p>
        </div>
      </div>

      {/* Cuerpo derecho */}
      <div className="flex-1 px-6 sm:px-8 py-5 flex flex-col justify-between gap-3">
        <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Calendar className="h-3.5 w-3.5 shrink-0" />
            {fechaStr} · {taller.horario}
          </span>
          <span className="flex items-center gap-1.5">
            <MapPin className="h-3.5 w-3.5 shrink-0" />
            {taller.direccion}
          </span>
          <span className="flex items-center gap-1.5">
            <Users className="h-3.5 w-3.5 shrink-0" />
            {cuposLabel}
          </span>
        </div>
        <p className="text-sm text-muted-foreground line-clamp-2">{taller.descripcion}</p>
        <div className="flex items-center justify-between pt-1">
          <p className="text-xl font-bold text-ink tabular-nums">{formatARS(taller.precio_total)}</p>
          <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink group-hover:gap-3 transition-[gap]">
            Ver taller <ArrowRight className="h-4 w-4" />
          </span>
        </div>
      </div>
    </Link>
  );
}

// ── Card pasada (horizontal, sin link) ────────────────────────────────────────
function PastWorkshopCard({ pw }: { pw: PastWorkshop }) {
  return (
    <div className="flex flex-col sm:flex-row rounded-2xl border border-border/30 overflow-hidden opacity-55">
      {/* Bloque oscuro izquierdo */}
      <div className="relative bg-ink sm:w-64 shrink-0 px-6 pt-7 pb-6 flex flex-col justify-between overflow-hidden min-h-[130px] sm:min-h-0">
        <Grain />
        <div className="relative">
          <p className="font-mono text-[0.625rem] tracking-[0.25em] uppercase text-rosa/70 mb-3">
            Workshop
          </p>
          <h2
            className="font-display font-black lowercase leading-[0.9] tracking-[-0.015em] text-background"
            style={{ fontSize: "clamp(1.2rem, 2vw, 1.5rem)" }}
          >
            {pw.nombre}
          </h2>
          <p className="text-background/55 mt-1.5 text-sm">{pw.subtitulo}</p>
        </div>
        <span className="relative self-start mt-5 inline-block rounded-full border border-background/20 text-background/50 text-[0.6rem] font-mono tracking-widest uppercase px-3 py-1">
          Finalizado
        </span>
      </div>

      {/* Cuerpo derecho */}
      <div className="flex-1 px-6 sm:px-8 py-5 flex flex-col justify-center gap-3">
        <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Calendar className="h-3.5 w-3.5 shrink-0" />
            {pw.fechaLabel}
          </span>
          <span className="flex items-center gap-1.5">
            <MapPin className="h-3.5 w-3.5 shrink-0" />
            {pw.direccion}
          </span>
        </div>
        <p className="text-sm text-muted-foreground line-clamp-2">{pw.descripcion}</p>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
function TalleresPage() {
  const { data: talleres = [], isLoading, isError } = useQuery({
    queryKey: ["talleres"],
    queryFn: apiGetTalleres,
    staleTime: 1000 * 60 * 5,
  });

  return (
    <PublicLayout>
      {/* Header full-bleed rosa */}
      <section className="bg-rosa text-ink px-4 sm:px-6 pt-12 pb-14">
        <div className="max-w-[900px] mx-auto">
          <p className="font-mono text-[0.6875rem] tracking-[0.2em] uppercase text-ink/55 mb-3">
            Rambla
          </p>
          <h1
            className="font-display font-black lowercase leading-[0.88] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(2.5rem, 6vw, 4rem)" }}
          >
            workshops
            <br />
            &amp; talleres
          </h1>
          <p className="mt-4 text-base text-ink/70 max-w-lg">
            Espacios de aprendizaje en Rambla Estudio. Clases prácticas con profesionales
            de la industria audiovisual y fotográfica.
          </p>
        </div>
      </section>

      <div className="max-w-[900px] mx-auto px-4 sm:px-6 py-10 sm:py-14 flex flex-col gap-4">
        {isLoading && (
          <div className="py-16 text-center text-muted-foreground text-sm">Cargando talleres…</div>
        )}
        {isError && (
          <div className="py-16 text-center text-muted-foreground text-sm">
            No se pudieron cargar los talleres. Intentá de nuevo.
          </div>
        )}

        {!isLoading && !isError && talleres.length === 0 && (
          <div className="py-8 text-center text-muted-foreground text-sm">
            No hay talleres activos por el momento. Seguinos en Instagram para enterarte de los próximos.
          </div>
        )}

        {talleres.map((t) => (
          <WorkshopCard key={t.id} taller={t} />
        ))}

        {/* Ediciones anteriores */}
        <div className="mt-6 flex flex-col gap-3">
          <p className="font-mono text-[0.6875rem] tracking-[0.2em] uppercase text-muted-foreground">
            Ediciones anteriores
          </p>
          {TALLERES_PASADOS.map((pw, i) => (
            <PastWorkshopCard key={i} pw={pw} />
          ))}
        </div>
      </div>
    </PublicLayout>
  );
}
