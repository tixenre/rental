/**
 * srcset de las fotos de equipo (catálogo).
 *
 * El backend deriva dos variantes WebP de cada foto principal: `display` (1200px)
 * y `display-sm` (600px). Para una card que en mobile se ve a ~300-400px, servir
 * la de 600 en vez de la de 1200 baja ~4× los bytes. El navegador elige según
 * `sizes` + DPR.
 *
 * Fallback seguro: si la foto no tiene la variante chica (legacy sin media_id, o
 * aún sin backfill), `fotoUrlSm` es null → devolvemos undefined y el `<img>` usa
 * solo `src` (cero rotura, sin srcset).
 */
export function buildFotoSrcSet(
  fotoUrl?: string | null,
  fotoUrlSm?: string | null,
): string | undefined {
  if (!fotoUrl || !fotoUrlSm) return undefined;
  return `${fotoUrlSm} 600w, ${fotoUrl} 1200w`;
}
