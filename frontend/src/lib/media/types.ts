/**
 * Tipos unificados del sistema de media (F0b).
 *
 * MediaVariant: una variante CDN de un asset (display/display-sm/display-thumb/og).
 *   width/height vienen del backend → anti-CLS sin JS (img width/height attributes).
 *
 * EntityMediaAsset: un asset de una entidad con sus variantes.
 *   Cubre nuevas fotos (media_id → variantes reales) y legacy (media_id null →
 *   variante sintética "display" con la url almacenada — cero rotura).
 */

export interface MediaVariant {
  name: string;
  url: string;
  width: number;
  height: number;
  content_type: string;
}

export interface EntityMediaAsset {
  id: number;
  media_id: number | null;
  orden: number;
  es_principal: boolean;
  /**
   * LQIP (Low Quality Image Placeholder, F0e): data URI de un JPEG 4×4px.
   * Usar como fondo CSS con `filter: blur(...)` mientras carga la variante CDN.
   * Null para assets pre-F0e o si la generación falló silenciosamente.
   */
  lqip?: string | null;
  variants: MediaVariant[];
}

export interface EntityMediaResponse {
  assets: EntityMediaAsset[];
}

/** Variante preferida para la imagen principal de la galería. */
export const DISPLAY_VARIANT = "display";
/** Variante para thumbnails en tiras de miniaturas. */
export const THUMB_VARIANT = "display-thumb";
/** Variante fallback para thumbnails si thumb no está disponible. */
export const SM_VARIANT = "display-sm";

/** Devuelve la variante por nombre; si no existe, la primera disponible. */
export function findVariant(variants: MediaVariant[], name: string): MediaVariant | undefined {
  return variants.find((v) => v.name === name) ?? variants[0];
}

/** Construye srcset de todas las variantes "display*" con sus anchos reales. */
export function buildSrcSet(variants: MediaVariant[]): string | undefined {
  const displayVariants = variants
    .filter((v) => v.name.startsWith("display") && v.width > 0)
    .sort((a, b) => a.width - b.width);
  if (displayVariants.length < 2) return undefined;
  return displayVariants.map((v) => `${v.url} ${v.width}w`).join(", ");
}
