import { useState } from "react";
import { type Brand } from "@/types/brand";
import { cn } from "@/lib/utils";
import { InlineSvg, isSvgUrl } from "@/components/ui/InlineSvg";

/**
 * Mapeo de marcas a slugs de simple-icons.org (CDN gratuito de logos SVG, MIT).
 * Si la marca está acá y no tiene logo_url propio, usamos el CDN como fallback.
 * Slugs disponibles: https://simpleicons.org
 */
const SIMPLE_ICONS_SLUGS: Record<string, string> = {
  sony: "sony",
  canon: "canon",
  nikon: "nikon",
  fujifilm: "fujifilm",
  panasonic: "panasonic",
  leica: "leica",
  hasselblad: "hasselblad",
  gopro: "gopro",
  dji: "dji",
  kodak: "kodak",
  polaroid: "polaroid",
  olympus: "olympus",
  shure: "shure",
  sennheiser: "sennheiser",
  bose: "bose",
  jbl: "jbl",
  apple: "apple",
  samsung: "samsung",
  manfrotto: "manfrotto",
};

function brandToSlug(nombre: string): string {
  return nombre.toLowerCase().trim().split(/\s+/)[0];
}

function fallbackLogoUrl(nombre: string): string | null {
  const slug = SIMPLE_ICONS_SLUGS[brandToSlug(nombre)];
  if (!slug) return null;
  // Color "111" = casi negro. Sirve sobre fondos claros (bg-surface, amber-soft).
  return `https://cdn.simpleicons.org/${slug}/111`;
}

function initials(nombre: string): string {
  const words = nombre.trim().split(/\s+/).filter((w) => w.length > 0);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

export function BrandCard({
  brand,
  count,
  isSelected,
  onClick,
}: {
  brand: Brand;
  count: number;
  isSelected?: boolean;
  onClick: () => void;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  const logoUrl = brand.logo_url || fallbackLogoUrl(brand.nombre);
  const showImg = !!logoUrl && !imgFailed;

  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative flex h-32 w-32 flex-shrink-0 flex-col items-center justify-center gap-2 rounded-lg border transition",
        isSelected
          ? "border-amber bg-amber-soft"
          : "border-hairline bg-surface hover:border-ink hover:bg-amber-soft"
      )}
    >
      {/* Logo / Iniciales — object-contain para que SVGs no se recorten.
          SVGs inlined → herendan color del `text-ink` parent (currentColor). */}
      <div className="h-14 w-14 grid place-items-center overflow-hidden rounded bg-background text-ink">
        {showImg ? (
          isSvgUrl(logoUrl) ? (
            <InlineSvg
              url={logoUrl!}
              ariaLabel={brand.nombre}
              className="h-full w-full p-1.5"
              fallback={
                <img
                  src={logoUrl!}
                  alt={brand.nombre}
                  className="h-full w-full object-contain p-1.5"
                  onError={() => setImgFailed(true)}
                />
              }
            />
          ) : (
            <img
              src={logoUrl!}
              alt={brand.nombre}
              className="h-full w-full object-contain p-1.5"
              onError={() => setImgFailed(true)}
            />
          )
        ) : (
          <span className="font-display text-lg text-ink">
            {initials(brand.nombre)}
          </span>
        )}
      </div>

      {/* Nombre + contador */}
      <div className="flex flex-col items-center gap-1 text-center px-1">
        <span className="text-sm font-display leading-tight text-ink line-clamp-2">
          {brand.nombre}
        </span>
        <span className="font-mono text-[10px] tabular text-muted-foreground">
          {count}
        </span>
      </div>
    </button>
  );
}
