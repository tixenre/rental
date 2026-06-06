import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import wordmarkSvgRaw from "@/assets/rambla-wordmark.svg?raw";

type Size = "sm" | "md" | "lg";

const SIZE_CLASS: Record<Size, string> = {
  sm: "h-7",
  md: "h-9 sm:h-11",
  lg: "h-12",
};

/**
 * Logo único de marca — wordmark SVG **inline** (themable vía `currentColor`).
 *
 * Fuente única: el SVG canónico bundleado, o el que el admin sube en
 * /admin/diseño → "Marca (SVG)" (setting `wordmark_svg`, texto saneado por el
 * backend). Se inyecta inline (no `<img>`) para que tome el color del contexto:
 * `text-amber` por default, y la inversión a blanco del top bar (filtro al
 * snapear) funciona sobre el mismo elemento.
 *
 * Usar en: TopBar, login pages, footer. `linkTo={null}` lo deja sin link.
 */
export function Logo({
  size = "md",
  linkTo = "/",
  className = "",
}: {
  size?: Size;
  linkTo?: string | null;
  className?: string;
}) {
  const { data: customSvg } = useQuery({
    queryKey: ["settings", "wordmark_svg"],
    queryFn: () =>
      fetch("/api/settings/wordmark_svg")
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => (d?.value as string | null) ?? null)
        .catch(() => null),
    staleTime: 60_000,
  });
  const svg = customSvg ?? wordmarkSvgRaw;

  const mark = (
    <span
      className={`logo-wordmark inline-block w-auto text-amber ${SIZE_CLASS[size]} ${className}`}
      role="img"
      aria-label="Rambla Rental"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );

  if (linkTo === null) return mark;
  return (
    <Link to={linkTo} className="inline-flex items-center">
      {mark}
    </Link>
  );
}
