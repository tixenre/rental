import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Calendar, MapPin, Users } from "lucide-react";

import { PublicLayout } from "@/components/rental/PublicLayout";
import { apiGetTalleres, type Taller } from "@/lib/api";
import { formatARS } from "@/lib/format";

export const Route = createLazyFileRoute("/talleres/")({
  component: TalleresPage,
});

function WorkshopCard({ taller }: { taller: Taller }) {
  const fechaInicio = new Date(taller.fecha_inicio + "T12:00:00");
  const fechaFin = new Date(taller.fecha_fin + "T12:00:00");
  const optsDate: Intl.DateTimeFormatOptions = { day: "numeric", month: "long" };
  const fechaStr =
    fechaInicio.getTime() === fechaFin.getTime()
      ? fechaInicio.toLocaleDateString("es-AR", optsDate)
      : `${fechaInicio.toLocaleDateString("es-AR", optsDate)} y ${fechaFin.toLocaleDateString("es-AR", optsDate)}`;

  const cuposLabel =
    taller.cupos_disponibles > 0
      ? `${taller.cupos_disponibles} lugar${taller.cupos_disponibles === 1 ? "" : "es"} disponible${taller.cupos_disponibles === 1 ? "" : "s"}`
      : "Lista de espera";

  return (
    <Link
      to="/talleres/$slug"
      params={{ slug: taller.slug }}
      className="group block rounded-2xl border border-border/60 bg-background overflow-hidden hover:border-amber/60 hover:shadow-md transition-all duration-200"
    >
      <div className="bg-ink px-6 pt-8 pb-6 relative overflow-hidden">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage: "radial-gradient(circle, white 1px, transparent 1px)",
            backgroundSize: "5px 5px",
          }}
        />
        <p className="font-mono text-[0.625rem] tracking-[0.25em] uppercase text-amber mb-3">
          Workshop
        </p>
        <h2
          className="font-display font-black lowercase leading-[0.9] tracking-[-0.015em] text-background"
          style={{ fontSize: "clamp(1.75rem, 4vw, 2.25rem)" }}
        >
          {taller.nombre}
        </h2>
        <p className="text-background/60 mt-2 text-sm font-medium">{taller.subtitulo}</p>
      </div>
      <div className="px-6 py-5 flex flex-col gap-3">
        <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
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
          <p className="text-lg font-bold text-ink tabular-nums">
            {formatARS(taller.precio_total)}
          </p>
          <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink group-hover:gap-2.5 transition-[gap]">
            Ver taller <ArrowRight className="h-4 w-4" />
          </span>
        </div>
      </div>
    </Link>
  );
}

function TalleresPage() {
  const {
    data: talleres = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["talleres"],
    queryFn: apiGetTalleres,
    staleTime: 1000 * 60 * 5,
  });

  return (
    <PublicLayout>
      {/* Header full-bleed oscuro */}
      <section className="bg-ink text-background px-4 sm:px-6 pt-12 pb-14">
        <div className="max-w-[900px] mx-auto">
          <p className="font-mono text-[0.6875rem] tracking-[0.2em] uppercase text-amber mb-3">
            Rambla
          </p>
          <h1
            className="font-display font-black lowercase leading-[0.88] tracking-[-0.02em] text-background"
            style={{ fontSize: "clamp(2.5rem, 6vw, 4rem)" }}
          >
            workshops
            <br />
            &amp; talleres
          </h1>
          <p className="mt-4 text-base text-background/65 max-w-lg">
            Espacios de aprendizaje en Rambla Estudio. Clases prácticas con profesionales de la
            industria audiovisual y fotográfica.
          </p>
        </div>
      </section>

      {/* Cards */}
      <div className="max-w-[900px] mx-auto px-4 sm:px-6 py-10 sm:py-14">
        {isLoading && (
          <div className="py-16 text-center text-muted-foreground text-sm">Cargando talleres…</div>
        )}

        {isError && (
          <div className="py-16 text-center text-muted-foreground text-sm">
            No se pudieron cargar los talleres. Intentá de nuevo.
          </div>
        )}

        {!isLoading && !isError && talleres.length === 0 && (
          <div className="py-16 text-center text-muted-foreground text-sm">
            No hay talleres activos por el momento. Seguinos en Instagram para enterarte de los
            próximos.
          </div>
        )}

        {talleres.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2">
            {talleres.map((t) => (
              <WorkshopCard key={t.id} taller={t} />
            ))}
          </div>
        )}
      </div>
    </PublicLayout>
  );
}
