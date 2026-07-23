import { Logo } from "@/components/rental/shell/Logo";
import { AREAS, type AreaKey } from "@/data/areas";

// Eyebrow editorial del banner (copy propio; el resto —label y color— sale de
// la fuente única `areas.ts`, no se duplica la lista de áreas).
const EYEBROW: Record<AreaKey, string> = {
  rental: "Equipos audiovisuales",
  estudio: "Foto & video",
  escuela: "Talleres & formación",
};

/**
 * Banner de sección: fondo ink + grain, wordmark enorme en el color de marca
 * de la sección y label debajo. Un banner por cada vertical de Rambla.
 */
export function SectionBanner({
  section,
  className = "",
}: {
  section: AreaKey;
  className?: string;
}) {
  const { label, accent: color } = AREAS[section];
  const eyebrow = EYEBROW[section];

  return (
    <div className={`relative bg-ink overflow-hidden flex flex-col justify-end ${className}`}>
      {/* Grain texture */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.06]"
        style={{
          backgroundImage: "radial-gradient(circle, white 1px, transparent 1px)",
          backgroundSize: "5px 5px",
        }}
      />

      {/* Contenido */}
      <div className="relative px-8 sm:px-12 pb-8 sm:pb-12 pt-10 sm:pt-14 flex flex-col gap-3">
        {/* Eyebrow */}
        <p className={`font-mono text-2xs tracking-[0.3em] uppercase ${color} opacity-70`}>
          {eyebrow}
        </p>

        {/* Wordmark */}
        <Logo linkTo={null} color={color} className="!h-auto w-full max-w-[min(100%,520px)]" />

        {/* Label de sección */}
        <p
          className={`font-display font-black lowercase leading-[0.88] tracking-[-0.02em] ${color}`}
          style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}
        >
          {label}
        </p>
      </div>
    </div>
  );
}
