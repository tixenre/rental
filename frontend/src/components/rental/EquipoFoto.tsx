import { useState } from "react";
import type { CSSProperties, ImgHTMLAttributes, ReactNode } from "react";
import { buildFotoSrcSet, buildAvifSrcSet } from "@/lib/srcset";

/**
 * EquipoFoto — fuente ÚNICA del `<picture>` de una foto de equipo en el catálogo.
 *
 * Consume las columnas DENORMALIZADAS que ya vienen en el payload de `/api/equipos`
 * (`fotoUrl`, `fotoUrlSm`, `fotoUrlThumb`, `fotoUrl*Avif`, `fotoLqip`) — NO el shape
 * `variants[]` de `/api/media/entity/` que usa `ResponsiveImage`. Son dos componentes
 * por dos shapes de datos: el catálogo trae todo junto en el listado (sin fetch por
 * equipo), la galería de la ficha pide de a una entidad. Cada shape, UNA fuente — sin
 * reimplementar el `<picture>` a mano en cada superficie.
 *
 * Renderiza `<picture><source type=image/avif><img webp></picture>` cuando hay AVIF;
 * cae a `<img>` plano si no. Blur-up LQIP opcional. Maneja el estado de error adentro
 * (onError → fallback), así los call sites no duplican `useState(imgFailed)`.
 */
export interface EquipoFotoColumns {
  fotoUrl?: string | null;
  fotoUrlSm?: string | null;
  fotoUrlThumb?: string | null;
  fotoUrlAvif?: string | null;
  fotoUrlSmAvif?: string | null;
  fotoUrlThumbAvif?: string | null;
  fotoLqip?: string | null;
}

interface EquipoFotoProps extends Omit<ImgHTMLAttributes<HTMLImageElement>, "src" | "srcSet"> {
  /** Columnas denorm de la foto. `foto={item}` funciona — `Equipment` las cumple. */
  foto: EquipoFotoColumns;
  alt: string;
  sizes: string;
  /** Qué mostrar sin foto o si la carga falla — `<EmptyImage/>` o `<CatIcon/>` ya construido. */
  fallback: ReactNode;
  /** Blur-up con `fotoLqip` (default true). `false` para los thumbs que hoy no lo usan. */
  blur?: boolean;
}

export function EquipoFoto({
  foto,
  alt,
  sizes,
  fallback,
  blur = true,
  style,
  ...img
}: EquipoFotoProps) {
  const [failed, setFailed] = useState(false);
  if (!foto.fotoUrl || failed) return <>{fallback}</>;

  const avifSrcSet = buildAvifSrcSet(foto.fotoUrlAvif, foto.fotoUrlSmAvif, foto.fotoUrlThumbAvif);
  const webpSrcSet = buildFotoSrcSet(foto.fotoUrl, foto.fotoUrlSm, foto.fotoUrlThumb);
  const blurStyle: CSSProperties | undefined =
    blur && foto.fotoLqip
      ? {
          backgroundImage: `url("${foto.fotoLqip}")`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }
      : undefined;

  const imgEl = (
    <img
      {...img}
      src={foto.fotoUrl}
      srcSet={webpSrcSet}
      sizes={webpSrcSet ? sizes : undefined}
      alt={alt}
      onError={() => setFailed(true)}
      style={{ ...blurStyle, ...style }}
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
