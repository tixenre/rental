/**
 * Helper único para compartir equipos — usado por la ficha (`/equipo/$slug`)
 * y por las cards del catálogo (`EquipmentCard`). No recrear la lógica de
 * armado de URL / share nativo en cada lugar (ver docs/MEMORIA.md 2026-05-29:
 * modularidad a prueba de balas).
 *
 * La URL siempre es absoluta y canónica (`SITE_URL` + slug-id), NO
 * `window.location.origin` — así el link compartido apunta al dominio oficial
 * aunque el visitante haya llegado por otro host/preview.
 */
import type { Equipment } from "@/data/equipment";
import { SITE_URL } from "./site";
import { buildEquipoSlug } from "./equipo-slug";

export type ShareResult = "shared" | "copied" | "cancelled";

/** URL canónica absoluta de un equipo, lista para compartir o previsualizar. */
export function equipoShareUrl(item: Pick<Equipment, "id" | "brand" | "name">): string {
  return `${SITE_URL}/equipo/${buildEquipoSlug(item)}`;
}

/**
 * Comparte un equipo: usa el share nativo del SO (Web Share API, típico en
 * mobile) si está disponible; si no, copia el link al portapapeles. Devuelve
 * qué pasó para que el caller muestre el feedback ("Copiado").
 */
export async function shareEquipo(
  item: Pick<Equipment, "id" | "brand" | "name">,
): Promise<ShareResult> {
  if (typeof window === "undefined") return "cancelled";
  const url = equipoShareUrl(item);
  try {
    if (navigator.share) {
      await navigator.share({ title: item.name, url });
      return "shared";
    }
    await navigator.clipboard.writeText(url);
    return "copied";
  } catch {
    // El usuario canceló el diálogo nativo, o el portapapeles falló.
    return "cancelled";
  }
}
