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
 * Comparte un link arbitrario (no necesariamente un equipo): usa el share nativo
 * del SO (Web Share API, típico en mobile) si está disponible; si no, copia al
 * portapapeles. Devuelve qué pasó para el feedback del caller.
 *
 * Robusto ante el gotcha de iOS/Safari: si `navigator.share` se invoca DESPUÉS de
 * un `await` (ej. crear el link en el backend), el browser puede perder el "user
 * gesture" y tirar `NotAllowedError`. En ese caso caemos a copiar — NO lo
 * tratamos como cancelación. Solo `AbortError` (el usuario cerró la hoja de
 * compartir) es "cancelled".
 */
export async function shareLink(url: string, title?: string, text?: string): Promise<ShareResult> {
  if (typeof window === "undefined") return "cancelled";
  if (navigator.share) {
    try {
      const data: ShareData = { url };
      if (title) data.title = title;
      if (text) data.text = text; // WhatsApp pre-llena el mensaje con el texto + el link.
      await navigator.share(data);
      return "shared";
    } catch (e) {
      // Hoja cerrada por el usuario → cancelado. Cualquier otro error (gesto
      // perdido tras el await en iOS, share bloqueado) → intentamos copiar.
      if (e instanceof DOMException && e.name === "AbortError") return "cancelled";
    }
  }
  try {
    // Sin share nativo (desktop): copiamos el mensaje + el link, no un link pelado,
    // así al pegarlo en WhatsApp va con contexto (y la preview igual se genera).
    await navigator.clipboard.writeText(text ? `${text}\n${url}` : url);
    return "copied";
  } catch {
    return "cancelled";
  }
}

/**
 * Comparte un equipo (ficha + cards del catálogo). Delega en `shareLink` con la
 * URL canónica del equipo — una sola forma de compartir en todo el front.
 */
export async function shareEquipo(
  item: Pick<Equipment, "id" | "brand" | "name">,
): Promise<ShareResult> {
  return shareLink(equipoShareUrl(item), item.name);
}
