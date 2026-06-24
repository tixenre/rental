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
  // Si solo tenemos fotoUrl (sin variantes), no hay srcset útil.
  if (parts.length === 1 && !fotoUrlSm && !fotoUrlThumb) return undefined;
  return parts.join(", ");
}
