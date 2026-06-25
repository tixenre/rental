import type { MediaVariant } from "@/lib/media/types";
import { buildSrcSet, findVariant, DISPLAY_VARIANT } from "@/lib/media/types";

interface ResponsiveImageProps
  extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, "src" | "srcSet"> {
  /** Variantes del asset (display, display-sm, display-thumb…). */
  variants: MediaVariant[];
  alt: string;
  /**
   * Nombre de la variante a usar como src principal. Default "display".
   * Si no existe, se usa la primera variante disponible.
   */
  preferName?: string;
  /**
   * Valor del atributo `sizes`. Default: catálogo de equipos (1200/600px).
   * Override para usos donde el slot de imagen tiene otro tamaño.
   */
  sizes?: string;
}

/**
 * Componente único de imagen responsiva — fuente única para toda la web.
 *
 * - srcset construido desde las variantes "display*" con sus anchos reales.
 * - width/height del atributo IMG vienen del backend → previene CLS sin JS.
 * - Fallback seguro: si solo hay una variante o no hay ancho, renderiza
 *   un <img> simple sin srcset (legacy pre-F0a, cero rotura).
 */
export function ResponsiveImage({
  variants,
  alt,
  preferName = DISPLAY_VARIANT,
  sizes = "(max-width: 600px) 600px, 1200px",
  ...imgProps
}: ResponsiveImageProps) {
  const primary = findVariant(variants, preferName);
  if (!primary) return null;

  const srcSet = buildSrcSet(variants);

  return (
    <img
      src={primary.url}
      srcSet={srcSet}
      sizes={srcSet ? sizes : undefined}
      width={primary.width > 0 ? primary.width : undefined}
      height={primary.height > 0 ? primary.height : undefined}
      alt={alt}
      {...imgProps}
    />
  );
}
