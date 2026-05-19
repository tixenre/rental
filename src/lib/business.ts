/**
 * business.ts — Datos del negocio (single source of truth).
 *
 * Antes el teléfono estaba duplicado en `WhatsappPill` y `CatalogoMovil`.
 * Si en el futuro se mueve a `app_settings`, sólo cambia este archivo.
 */

import { whatsappLink } from "./whatsapp";

/** Teléfono internacional del negocio para click-to-chat de WhatsApp. */
export const BUSINESS_PHONE = "+5492235852510";

/**
 * Arma el link a wa.me del negocio con un mensaje opcional pre-llenado.
 * Devuelve `null` si el teléfono no es parseable (no debería pasar).
 */
export function businessWhatsappLink(message?: string): string | null {
  return whatsappLink({ phone: BUSINESS_PHONE, message });
}
