/**
 * Helpers de InlineSvg que no son componentes.
 *
 * Viven en su propio módulo para que InlineSvg.tsx exporte solo componentes y
 * Fast Refresh funcione bien.
 */

/** ¿La URL es probablemente un SVG? Heurística por extensión. */
export function isSvgUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  try {
    const path = new URL(url).pathname.toLowerCase();
    return path.endsWith(".svg");
  } catch {
    return url.toLowerCase().endsWith(".svg");
  }
}
