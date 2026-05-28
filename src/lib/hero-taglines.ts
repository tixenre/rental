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
