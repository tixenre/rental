import type { MediaVariant } from "@/lib/media/types";
import { buildSrcSet, findVariant, DISPLAY_VARIANT } from "@/lib/media/types";

/** Construye el srcset de variantes de un content_type dado (ej. "image/avif"). */
function buildSrcSetForType(variants: MediaVariant[], contentType: string): string | undefined {
  const filtered = variants
    .filter((v) => v.name.startsWith("display") && v.content_type === contentType && v.width > 0)
    .sort((a, b) => a.width - b.width);
  if (filtered.length < 1) return undefined;
  return filtered.map((v) => `${v.url} ${v.width}w`).join(", ");
}

interface ResponsiveImageProps extends Omit<
  React.ImgHTMLAttributes<HTMLImageElement>,
  "src" | "srcSet"
> {
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
  /**
   * LQIP data URI (F0e): se usa como fondo CSS blur-up mientras carga la imagen.
   * Muestra el placeholder inmediatamente sin esperar la variante CDN.
   */
  lqip?: string | null;
}

/**
 * Componente único de imagen responsiva — fuente única para toda la web.
 *
 * - srcset construido desde las variantes "display*" con sus anchos reales.
 * - width/height del atributo IMG vienen del backend → previene CLS sin JS.
 * - blur-up: si hay lqip, se usa como fondo CSS mientras carga la imagen.
 * - Fallback seguro: si solo hay una variante o no hay ancho, renderiza
 *   un <img> simple sin srcset (legacy pre-F0a, cero rotura).
 */
export function ResponsiveImage({
  variants,
  alt,
  preferName = DISPLAY_VARIANT,
  sizes = "(max-width: 600px) 600px, 1200px",
  lqip,
  style,
  ...imgProps
}: ResponsiveImageProps) {
  const primary = findVariant(variants, preferName);
  if (!primary) return null;

  const webpSrcSet = buildSrcSet(variants);
  const avifSrcSet = buildSrcSetForType(variants, "image/avif");

  const blurStyle: React.CSSProperties = lqip
    ? {
        backgroundImage: `url("${lqip}")`,
        backgroundSize: "cover",
        backgroundPosition: "center",
      }
    : {};

  const imgEl = (
    <img
      src={primary.url}
      srcSet={webpSrcSet}
      sizes={webpSrcSet ? sizes : undefined}
      width={primary.width > 0 ? primary.width : undefined}
      height={primary.height > 0 ? primary.height : undefined}
      alt={alt}
      style={{ ...blurStyle, ...style }}
      {...imgProps}
    />
  );

  if (!avifSrcSet) return imgEl;

  return (
    <picture>
      <source type="image/avif" srcSet={avifSrcSet} sizes={sizes} />
      {imgEl}
    </picture>
  );
}
