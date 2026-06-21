import { Logo } from "@/components/rental/Logo";

type Section = "rental" | "estudio" | "workshops";

const CONFIG: Record<Section, { color: string; label: string; eyebrow: string }> = {
  rental: {
    color: "text-amber",
    label: "rental.",
    eyebrow: "Equipos audiovisuales",
  },
  estudio: {
    color: "text-naranja",
    label: "estudio.",
    eyebrow: "Foto & video",
  },
  workshops: {
    color: "text-rosa",
    label: "workshops.",
    eyebrow: "Talleres & formación",
  },
};

/**
 * Banner de sección: fondo ink + grain, wordmark enorme en el color de marca
 * de la sección y label debajo. Un banner por cada vertical de Rambla.
 */
export function SectionBanner({
  section,
  className = "",
}: {
  section: Section;
  className?: string;
}) {
  const { color, label, eyebrow } = CONFIG[section];

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
        <p className={`font-mono text-[0.625rem] tracking-[0.3em] uppercase ${color} opacity-70`}>
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
