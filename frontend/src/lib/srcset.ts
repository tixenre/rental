/**
 * srcset AVIF de las fotos de equipo. Espeja buildFotoSrcSet para las variantes AVIF.
 * Retorna undefined si no hay AVIF disponible → el browser usa el <img> WebP/JPEG.
 */
export function buildAvifSrcSet(
  fotoUrlAvif?: string | null,
  fotoUrlSmAvif?: string | null,
  fotoUrlThumbAvif?: string | null,
): string | undefined {
  if (!fotoUrlAvif) return undefined;
  const parts: string[] = [];
  if (fotoUrlThumbAvif) parts.push(`${fotoUrlThumbAvif} 160w`);
  if (fotoUrlSmAvif) parts.push(`${fotoUrlSmAvif} 600w`);
  parts.push(`${fotoUrlAvif} 1200w`);
  // Retornar aunque solo haya 1 variante: el <source type="image/avif"> le dice al
  // browser que existe AVIF, ahorrando ~20-30% vs WebP aunque no haya sm/thumb todavía.
  return parts.join(", ");
}

/**
 * srcset de las fotos de equipo (catálogo).
 *
 * El backend deriva tres variantes WebP de cada foto principal: `display` (1200px),
 * `display-sm` (600px) y `display-thumb` (160px). El navegador elige según `sizes` + DPR:
 * - slots de ~48px → thumb (160w); slots de ~300-400px → sm (600w); resto → display (1200w).
 *
 * Fallback seguro: si alguna variante falta (legacy sin media_id, o sin backfill),
 * se omite del srcset — el `<img>` usa la más chica disponible o solo `src` (cero rotura).
 */
export function buildFotoSrcSet(
  fotoUrl?: string | null,
  fotoUrlSm?: string | null,
  fotoUrlThumb?: string | null,
): string | undefined {
  if (!fotoUrl) return undefined;
  const parts: string[] = [];
  if (fotoUrlThumb) parts.push(`${fotoUrlThumb} 160w`);
  if (fotoUrlSm) parts.push(`${fotoUrlSm} 600w`);
  parts.push(`${fotoUrl} 1200w`);
  // Sin variantes, no hay srcset útil.
  if (parts.length === 1 && !fotoUrlSm && !fotoUrlThumb) return undefined;
  return parts.join(", ");
}
