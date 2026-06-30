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
import type { ReactEventHandler } from "react";
import { apiGetEstudio } from "@/lib/api";

export interface HeroPhoto {
  url: string;
  urlSm?: string;
  urlAvif?: string;
  urlSmAvif?: string;
}

// Cuántas fotos rota el hero como máximo (las primeras según `orden`).
const HERO_MAX = 5;

const HERO_SIZES = "100vw";

/**
 * heroImgProps — fuente ÚNICA de cómo se sirve la imagen del hero (mobile y
 * desktop comparten esto, sin reimplementar).
 *
 * El hero es el LCP del catálogo → el backend inyecta un `<link rel=preload
 * as=image>` para que sea descubrible en el HTML inicial. Un preload con
 * `type=image/avif` matchea de forma determinista SOLO contra un `<img>` directo,
 * no contra un `<source>` dentro de `<picture>` (matching frágil en Chromium →
 * doble descarga + LCP peor). Por eso el hero usa `<img src=avif>` directo en vez
 * de `<picture>`: es la única superficie que se preloadea.
 *
 * Fallback para el ~5% de browsers sin AVIF (Safari<16.1/iOS<16): `onError`
 * reescribe a webp una sola vez (anti-loop por `dataset.fellBack`). El backend
 * toma la MISMA decisión sobre la MISMA foto (mismo orden es_principal/orden) →
 * si la principal no tiene AVIF, ni el preload ni el `<img>` lo usan.
 */
export function heroImgProps(
  photo: HeroPhoto,
  opts: { eager: boolean },
): {
  src: string;
  srcSet: string | undefined;
  sizes: string;
  loading: "eager" | "lazy";
  fetchPriority: "high" | undefined;
  decoding: "async";
  onError: ReactEventHandler<HTMLImageElement>;
} {
  const webpSrcSet = photo.urlSm ? `${photo.urlSm} 800w, ${photo.url} 1600w` : undefined;
  const avifSrcSet = photo.urlSmAvif
    ? `${photo.urlSmAvif} 800w, ${photo.urlAvif} 1600w`
    : undefined;
  const hasAvif = Boolean(photo.urlAvif);

  return {
    src: hasAvif ? photo.urlAvif! : photo.url,
    srcSet: hasAvif ? (avifSrcSet ?? undefined) : webpSrcSet,
    sizes: HERO_SIZES,
    loading: opts.eager ? "eager" : "lazy",
    fetchPriority: opts.eager ? "high" : undefined,
    decoding: "async",
    onError: (e) => {
      // El AVIF no cargó (browser sin soporte / variante caída) → caer a webp.
      const img = e.currentTarget;
      if (img.dataset.fellBack) return; // ya cayó: no loopear si el webp también falla
      img.dataset.fellBack = "1";
      if (webpSrcSet) img.srcset = webpSrcSet;
      else img.removeAttribute("srcset");
      img.src = photo.url;
    },
  };
}

/** Devuelve las fotos del hero desde R2 (admin). Vacío mientras carga. */
export function useHeroPhotos(): HeroPhoto[] {
  const { data } = useQuery({
    queryKey: ["estudio-fotos"],
    queryFn: apiGetEstudio,
  });

  const fotos = data?.fotos ?? [];
  if (fotos.length === 0) return [];

  // Mismo orden que el backend (`es_principal DESC, orden ASC, id ASC`) — incluido el
  // desempate por `id` — para que la foto que el front muestra como principal sea EXACTO
  // la misma que el backend preloadea. Si discrepan, vuelve la doble descarga del LCP.
  return [...fotos]
    .sort(
      (a, b) => Number(b.es_principal) - Number(a.es_principal) || a.orden - b.orden || a.id - b.id,
    )
    .slice(0, HERO_MAX)
    .map((f) => ({
      url: f.url,
      urlSm: f.url_sm ?? undefined,
      urlAvif: f.url_avif ?? undefined,
      urlSmAvif: f.url_sm_avif ?? undefined,
    }));
}
