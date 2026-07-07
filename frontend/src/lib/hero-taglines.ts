import { useQuery } from "@tanstack/react-query";

export type HeroTagline = [string, string];

export const HERO_TAGLINES_DEFAULT: HeroTagline[] = [
  ["rental, estudio,", "rambla."],
  ["en rambla,", "en mardel."],
  ["en rambla,", "tu proyecto."],
  ["en rambla,", "tu rodaje."],
];

export function parseHeroTaglines(raw: string): HeroTagline[] {
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.length > 0) return parsed as HeroTagline[];
  } catch {
    // ignore
  }
  return HERO_TAGLINES_DEFAULT;
}

/** Key propia (distinta de la que usa el admin para el string crudo, ver
 *  BrandingSection) — evita la colisión donde dos queryFn con shapes
 *  distintos (string vs HeroTagline[]) compartían ["settings","hero_taglines"]. */
export const HERO_TAGLINES_QUERY_KEY = ["settings", "hero_taglines", "parsed"] as const;

/** Fuente única del hero tagline público (home + catálogo mobile) — ya
 *  parseado a `HeroTagline[]`, con fallback a los defaults ante error. */
export function useHeroTaglines() {
  const { data } = useQuery({
    queryKey: HERO_TAGLINES_QUERY_KEY,
    queryFn: async () => {
      try {
        const res = await fetch("/api/settings/hero_taglines");
        if (!res.ok) return HERO_TAGLINES_DEFAULT;
        const d = await res.json();
        return parseHeroTaglines(d.value as string);
      } catch {
        return HERO_TAGLINES_DEFAULT;
      }
    },
    staleTime: 5 * 60 * 1000,
  });
  return data ?? HERO_TAGLINES_DEFAULT;
}
