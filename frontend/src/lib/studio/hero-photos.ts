/**
 * useHeroPhotos — fuente única de las fotos del hero (catálogo home).
 *
 * El hero (desktop `HeroSection` y mobile `HeroBanner`) muestra las fotos del
 * Estudio que el dueño sube desde el back-office → viven en R2 (tabla
 * `estudio_fotos`, servidas por `/api/estudio`). Misma fuente que la página
 * `/estudio` y que las fotos de equipos: nada de paths estáticos paralelos.
 *
 * Las fotos llegan ordenadas por `orden` (la principal primero). Si la API no
 * devuelve nada todavía (carga inicial / error de red), cae al fallback
 * estático commiteado en el repo, así el hero nunca queda en negro.
 */
import { useQuery } from "@tanstack/react-query";
import { apiGetEstudio } from "@/lib/api";

// Fallback: archivos estáticos en public/estudio/. Solo se usan si R2 no
// responde. La fuente real son las fotos del admin (R2).
export const HERO_PHOTOS_FALLBACK = [
  "/estudio/Rambla_Estudio_S7V9470.jpg",
  "/estudio/Rambla_Estudio_S7V9483.jpg",
  "/estudio/Rambla_Estudio_S7V9510-HDR-Edit.jpg",
  "/estudio/Rambla_Estudio_S7V9519-HDR.jpg",
];

// Cuántas fotos rota el hero como máximo (las primeras según `orden`).
const HERO_MAX = 5;

/** Devuelve las URLs de las fotos del hero: R2 (admin) si hay, fallback si no. */
export function useHeroPhotos(): string[] {
  const { data } = useQuery({
    queryKey: ["estudio"],
    queryFn: apiGetEstudio,
    staleTime: 5 * 60 * 1000,
  });

  const fotos = data?.fotos ?? [];
  if (fotos.length === 0) return HERO_PHOTOS_FALLBACK;

  return [...fotos]
    .sort((a, b) => Number(b.es_principal) - Number(a.es_principal) || a.orden - b.orden)
    .slice(0, HERO_MAX)
    .map((f) => f.url);
}
