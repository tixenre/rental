/**
 * useHeroPhotos — fuente única de las fotos del hero (catálogo home).
 *
 * El hero (desktop `HeroSection` y mobile `HeroBanner`) muestra las fotos del
 * Estudio que el dueño sube desde el back-office → viven en R2 (tabla
 * `estudio_fotos`, servidas por `/api/estudio`). Misma fuente que la página
 * `/estudio` y que las fotos de equipos: nada de paths estáticos paralelos.
 *
 * `urlSm` es la variante 800px (keep-aspect) para srcset. NULL = foto subida
 * antes del backfill → el componente cae a `url` sin srcset (cero rotura).
 */
import { useQuery } from "@tanstack/react-query";
import { apiGetEstudio } from "@/lib/api";

export interface HeroPhoto {
  url: string;
  urlSm?: string;
  urlAvif?: string;
  urlSmAvif?: string;
}

// Cuántas fotos rota el hero como máximo (las primeras según `orden`).
const HERO_MAX = 5;

/** Devuelve las fotos del hero desde R2 (admin). Vacío mientras carga. */
export function useHeroPhotos(): HeroPhoto[] {
  const { data } = useQuery({
    queryKey: ["estudio"],
    queryFn: apiGetEstudio,
    staleTime: 5 * 60 * 1000,
  });

  const fotos = data?.fotos ?? [];
  if (fotos.length === 0) return [];

  return [...fotos]
    .sort((a, b) => Number(b.es_principal) - Number(a.es_principal) || a.orden - b.orden)
    .slice(0, HERO_MAX)
    .map((f) => ({
      url: f.url,
      urlSm: f.url_sm ?? undefined,
      urlAvif: f.url_avif ?? undefined,
      urlSmAvif: f.url_sm_avif ?? undefined,
    }));
}
