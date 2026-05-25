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
  // simpleicons CDN devuelve SVG monocromo — InlineSvg lo tiñe al
  // currentColor del card, así que pedimos negro y el cliente decide.
  return `https://cdn.simpleicons.org/${slug}/000`;
}

function initials(nombre: string): string {
  const words = nombre
    .trim()
    .split(/\s+/)
    .filter((w) => w.length > 0);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

/**
 * Card del carrusel "Marcas destacadas". Cuadrado, solo logo (sin nombre
 * ni count visible — el nombre va en `aria-label` y el count se sirve en
 * tooltip nativo via `title`).
 *
 * Diseño: el logo SVG se tiñe al `text-ink` del card (currentColor),
 * unificando todos los logos al color del tema. Para preservar el color
 * original de un logo, subí PNG en lugar de SVG.
 */
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

  const label = `${brand.nombre} · ${count} ${count === 1 ? "equipo" : "equipos"}`;

  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={isSelected ? `Quitar filtro ${brand.nombre}` : `Filtrar por ${brand.nombre}`}
      aria-pressed={isSelected}
      className={cn(
        "group relative grid h-32 w-32 flex-shrink-0 place-items-center rounded-lg border p-5 transition text-ink",
        isSelected
          ? "border-amber bg-amber-soft"
          : "border-hairline bg-surface hover:border-ink hover:bg-amber-soft",
      )}
    >
      {showImg ? (
        // `brightness-0` colapsa todo el logo a un silueta sólida negra,
        // sin importar si vino en SVG con fills, PNG a color, gradient, etc.
        // Resultado uniforme con el resto del tema. Si en el futuro hay
        // dark mode, agregar `dark:invert` acá para que se vea en blanco.
        <span className="h-full w-full grid place-items-center [&>img]:max-h-full [&>img]:max-w-full [&>img]:object-contain [&>span]:h-full [&>span]:w-full brightness-0">
          {isSvgUrl(logoUrl) ? (
            <InlineSvg
              url={logoUrl!}
              ariaLabel={brand.nombre}
              fallback={
                <img src={logoUrl!} alt={brand.nombre} onError={() => setImgFailed(true)} />
              }
            />
          ) : (
            <img src={logoUrl!} alt={brand.nombre} onError={() => setImgFailed(true)} />
          )}
        </span>
      ) : (
        <span className="font-display text-3xl leading-none">{initials(brand.nombre)}</span>
      )}
    </button>
  );
}
