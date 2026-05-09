import type { SVGProps } from "react";
import type { Category } from "@/data/equipment";

/**
 * Ilustraciones brand Rambla — trazo grueso, esquinas redondeadas, monocromas.
 * Heredan el color con `currentColor` para que se pinten desde el contenedor.
 */

type IllProps = SVGProps<SVGSVGElement>;

const base: IllProps = {
  viewBox: "0 0 64 64",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2.5,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

// Cámara de cine con lente y visor
function Camara(props: IllProps) {
  return (
    <svg {...base} {...props}>
      <rect x="6" y="22" width="30" height="22" rx="3" />
      <circle cx="14" cy="16" r="4" />
      <circle cx="24" cy="16" r="4" />
      <path d="M14 20v2M24 20v2" />
      <rect x="36" y="27" width="18" height="12" rx="2" />
      <circle cx="45" cy="33" r="3" />
      <path d="M10 48l4 6M32 48l-4 6" />
    </svg>
  );
}

// Lente con anillos de foco
function Lente(props: IllProps) {
  return (
    <svg {...base} {...props}>
      <rect x="8" y="20" width="48" height="24" rx="3" />
      <path d="M16 20v24M22 20v24M44 20v24M50 20v24" />
      <circle cx="32" cy="32" r="6" />
      <path d="M30 30l1.5 1.5" />
    </svg>
  );
}

// Reflector / panel LED tipo Aputure con yugo y trípode
function Iluminacion(props: IllProps) {
  return (
    <svg {...base} {...props}>
      <rect x="14" y="10" width="30" height="20" rx="3" />
      <path d="M20 16h18M20 20h18M20 24h18" />
      <path d="M44 14l8 4M44 26l8-4" />
      <path d="M29 30v6M29 36l-8 18M29 36l8 18M29 36h-2M29 36h2" />
    </svg>
  );
}

// Micrófono shotgun con peluche
function Audio(props: IllProps) {
  return (
    <svg {...base} {...props}>
      <rect x="6" y="20" width="30" height="14" rx="7" />
      <path d="M10 20v14M14 20v14M18 20v14M22 20v14M26 20v14M30 20v14" />
      <rect x="36" y="24" width="10" height="6" rx="1.5" />
      <path d="M46 27h6" />
      <path d="M50 24v6" />
      <path d="M52 18v18" />
    </svg>
  );
}

// Silla de director plegable (guiño al manual)
function Silla(props: IllProps) {
  return (
    <svg {...base} {...props}>
      {/* respaldo */}
      <path d="M16 14h32" />
      <path d="M16 18h32" />
      {/* asiento */}
      <path d="M14 32h36" />
      {/* patas en X */}
      <path d="M16 14l16 38M48 14L32 52" />
      <path d="M16 52l16-38M48 52L32 14" />
      {/* travesaño inferior */}
      <path d="M14 52h36" />
    </svg>
  );
}

// Claqueta abierta
function Claqueta(props: IllProps) {
  return (
    <svg {...base} {...props}>
      {/* tapa */}
      <path d="M8 18l44-6 2 8-44 6z" />
      <path d="M14 14l-2 6M22 13l-2 6M30 12l-2 6M38 11l-2 6M46 10l-2 6" />
      {/* cuerpo */}
      <rect x="8" y="26" width="48" height="26" rx="2" />
      <path d="M14 34h12M14 40h20M14 46h16" />
    </svg>
  );
}

// Cable XLR con conectores
function Cable(props: IllProps) {
  return (
    <svg {...base} {...props}>
      <rect x="4" y="26" width="14" height="12" rx="2" />
      <circle cx="9" cy="32" r="1" />
      <circle cx="13" cy="30" r="1" />
      <circle cx="13" cy="34" r="1" />
      <path d="M18 32c8 0 8 14 16 14s8-14 16-14" />
      <rect x="46" y="26" width="14" height="12" rx="2" />
      <circle cx="51" cy="32" r="1" />
      <circle cx="55" cy="30" r="1" />
      <circle cx="55" cy="34" r="1" />
    </svg>
  );
}

const map: Record<Category, (p: IllProps) => React.ReactElement> = {
  Cámaras: Camara,
  Lentes: Lente,
  Iluminación: Iluminacion,
  Audio: Audio,
  Soportes: Silla,
  Accesorios: Claqueta,
  Adaptadores: Cable,
};

export function CategoryIllustration({
  category,
  className,
  ...rest
}: { category: Category } & IllProps) {
  const Component = map[category] ?? Camara;
  return <Component className={className} {...rest} />;
}

export const Illustrations = { Camara, Lente, Iluminacion, Audio, Silla, Claqueta, Cable };
