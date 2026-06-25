import { useState } from "react";
import { cn } from "@/lib/utils";
import type { EntityMediaAsset } from "@/lib/media/types";
import { findVariant, DISPLAY_VARIANT, THUMB_VARIANT, SM_VARIANT } from "@/lib/media/types";
import { ResponsiveImage } from "./ResponsiveImage";
import { Lightbox } from "@/components/rental/Lightbox";

interface MediaGalleryProps {
  assets: EntityMediaAsset[];
  alt: string;
  className?: string;
  /** Clases para el contenedor de la imagen principal. */
  mainClassName?: string;
  /** Clases para la tira de miniaturas. */
  thumbsClassName?: string;
  /**
   * Tamaño del slot de imagen para el atributo `sizes`.
   * Default: catálogo de equipos.
   */
  sizes?: string;
}

/**
 * Galería pública responsiva — fuente única para páginas de entidad.
 *
 * - Imagen principal seleccionada con `<ResponsiveImage>` (srcset + anti-CLS).
 * - Tira de miniaturas (display-thumb → display-sm → display) debajo si hay >1 foto.
 * - Click en imagen principal → Lightbox fullscreen.
 * - Click en miniatura → cambia la selección.
 */
export function MediaGallery({
  assets,
  alt,
  className,
  mainClassName,
  thumbsClassName,
  sizes,
}: MediaGalleryProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  if (!assets.length) return null;

  const selected = assets[Math.min(selectedIndex, assets.length - 1)];

  const lightboxPhotos = assets.map((a) => {
    const v = findVariant(a.variants, DISPLAY_VARIANT);
    return { url: v?.url ?? "", alt };
  });

  const thumbVariant = (asset: EntityMediaAsset) =>
    findVariant(asset.variants, THUMB_VARIANT) ??
    findVariant(asset.variants, SM_VARIANT) ??
    asset.variants[0];

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {/* Imagen principal */}
      <button
        type="button"
        className={cn("block w-full cursor-zoom-in", mainClassName)}
        onClick={() => {
          setLightboxIndex(selectedIndex);
          setLightboxOpen(true);
        }}
        aria-label="Ver en pantalla completa"
      >
        <ResponsiveImage
          variants={selected.variants}
          alt={alt}
          sizes={sizes}
          lqip={selected.lqip}
          className="w-full h-full object-cover"
          draggable={false}
        />
      </button>

      {/* Tira de miniaturas — solo si hay más de una foto */}
      {assets.length > 1 && (
        <div
          className={cn("flex gap-2 overflow-x-auto", thumbsClassName)}
          role="list"
          aria-label="Miniaturas de galería"
        >
          {assets.map((asset, i) => {
            const thumb = thumbVariant(asset);
            if (!thumb) return null;
            const isSelected = i === selectedIndex;
            return (
              <button
                key={asset.id}
                type="button"
                role="listitem"
                onClick={() => setSelectedIndex(i)}
                aria-label={`Foto ${i + 1}${asset.es_principal ? " (principal)" : ""}`}
                aria-pressed={isSelected}
                className={cn(
                  "shrink-0 w-16 h-16 rounded overflow-hidden border-2 transition-colors",
                  isSelected ? "border-amber" : "border-transparent hover:border-amber/40",
                )}
              >
                <img
                  src={thumb.url}
                  width={thumb.width > 0 ? thumb.width : 64}
                  height={thumb.height > 0 ? thumb.height : 64}
                  alt={`Miniatura ${i + 1}`}
                  className="w-full h-full object-cover"
                  draggable={false}
                />
              </button>
            );
          })}
        </div>
      )}

      <Lightbox
        open={lightboxOpen}
        onClose={() => setLightboxOpen(false)}
        photos={lightboxPhotos}
        index={lightboxIndex}
        onIndexChange={setLightboxIndex}
      />
    </div>
  );
}
