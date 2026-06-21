import { useQuery } from "@tanstack/react-query";
import isologoSvgRaw from "@/assets/rambla-isologo.svg?raw";
import isologoMonoSvgRaw from "@/assets/rambla-isologo-mono.svg?raw";

/**
 * Isologo de Rambla (la R con puntas) — inline.
 *
 * - Default: colores propios de marca (amber + R blanca), o el que el admin sube
 *   en /admin/diseño si existe. Para fondos claros (favicon, etc.).
 * - `mono`: silueta en `currentColor` con la R recortada (negativo). Pensado para
 *   ir sobre los fondos de color de los topbars (amber/naranja/rosa/verde): con
 *   `text-white` la silueta queda blanca y la R muestra el color del área.
 */
export function LogoMark({ className = "", mono = false }: { className?: string; mono?: boolean }) {
  const { data: customSvg } = useQuery({
    queryKey: ["settings", "isologo_svg"],
    queryFn: () =>
      fetch("/api/settings/isologo_svg")
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => (d?.value as string | null) ?? null)
        .catch(() => null),
    staleTime: 60_000,
    enabled: !mono,
  });

  const svg = mono ? isologoMonoSvgRaw : (customSvg ?? isologoSvgRaw);

  return (
    <span
      className={`inline-block shrink-0 ${className || "h-8 w-8"}`}
      dangerouslySetInnerHTML={{ __html: svg }}
      role="img"
      aria-label="Rambla"
    />
  );
}
