/**
 * Rambla Rental — Brand asset manifest
 * Importá las URLs vía Vite (`?url` / import directo) desde acá en vez de
 * hardcodear paths. Mantiene un solo lugar si los assets se mueven.
 *
 *   import { wordmark, isologo } from "@/assets/brand";
 *   <img src={wordmark} alt="rambla" />
 */
import wordmarkSvg from "./rambla-wordmark.svg";
import wordmarkPng from "./rambla-wordmark.png";
import wordmarkWebp from "./rambla-wordmark.webp";
import isologoSvg from "./rambla-ico.svg";
import badgePng from "./rambla-badge.png";
import sealPng from "./rambla-icon-seal.png";
import iconRPng from "./rambla-icon-r.png";
import iconChairPng from "./rambla-icon-chair.png";

/** Logo principal (SVG themable vía currentColor — preferí éste). */
export const wordmark = wordmarkSvg;
/** Wordmark raster fallback (og-image, email, contextos sin SVG). */
export const wordmarkRaster = { webp: wordmarkWebp, png: wordmarkPng };

/** Isologo / seal "R" (SVG monocromo themable). */
export const isologo = isologoSvg;

/** Assets raster de marca (merch, mobile topbar, ilustración). */
export const brand = {
  badge: badgePng, // seal circular
  seal: sealPng, // sello detallado
  iconR: iconRPng, // ícono "R" isologo
  iconChair: iconChairPng, // ícono silla branded
} as const;

export const brandManifest = {
  wordmark: { svg: wordmarkSvg, png: wordmarkPng, webp: wordmarkWebp, themable: true },
  isologo: { svg: isologoSvg, themable: true },
  badge: { png: badgePng },
  seal: { png: sealPng },
  iconR: { png: iconRPng },
  iconChair: { png: iconChairPng },
} as const;
