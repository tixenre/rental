import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import logoWordmark from "@/assets/rambla-wordmark.webp";

type Size = "sm" | "md" | "lg";

const SIZE_CLASS: Record<Size, string> = {
  sm: "h-7",
  md: "h-9 sm:h-11",
  lg: "h-12",
};

/**
 * Logo único de marca. Fetcha `/api/settings/logo_url` (admin puede sobrescribir
 * desde back-office). Si no hay setting, usa el wordmark del repo.
 *
 * Usar en: TopBar, login pages, footer. Si se necesita un logo sin link
 * (ej. dentro de un header que ya es link), pasar `linkTo={null}`.
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
  const { data: logoSetting } = useQuery({
    queryKey: ["settings", "logo_url"],
    queryFn: () =>
      fetch("/api/settings/logo_url").then((r) => (r.ok ? r.json() : null)).catch(() => null),
    // Cache buster (?v=<ts>) del setting invalida el cache del navegador.
    staleTime: 30_000,
  });
  const src = (logoSetting?.value as string | null) ?? logoWordmark;

  const img = (
    <img
      src={src}
      alt="Rambla Rental"
      className={`${SIZE_CLASS[size]} w-auto object-contain ${className}`}
    />
  );

  if (linkTo === null) return img;
  return (
    <Link to={linkTo} className="inline-flex items-center">
      {img}
    </Link>
  );
}
