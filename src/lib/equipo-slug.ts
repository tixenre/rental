/**
 * Generación de URL slug-id mixto para equipos.
 *
 * URL format: `<marca>-<nombre>-<id>` (e.g. `sony-fx3-cuerpo-47`).
 *
 * Por qué slug-id (estilo Stack Overflow, GitHub Issues):
 * - Keywords en URL → mejor SEO (Google los pondera).
 * - Más confianza al click — el usuario sabe qué hay antes de clickear.
 * - Mejor para compartir y para social previews.
 * - Si el equipo se renombra, el slug cambia pero el ID al final no.
 *   Las URLs viejas siguen funcionando (el backend usa solo el ID).
 *
 * Tipos de input válidos en la URL:
 * - `47` → solo ID (back-compat).
 * - `sony-fx3-47` → slug-id (recomendado).
 * - `sony-fx3` → solo slug (NO soportado — el backend devuelve 400).
 */

import type { Equipment } from "@/data/equipment";

/**
 * Normaliza un string a slug: lowercase, sin acentos, sin caracteres
 * especiales, espacios → guiones.
 */
function slugify(input: string): string {
  return (input ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // sacar acentos
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80); // hard cap para URLs no enormes
}

/**
 * Construye la URL canónica de un equipo.
 *
 * @example
 * buildEquipoSlug({ id: "47", brand: "Sony", name: "FX3 Cuerpo" })
 * // → "sony-fx3-cuerpo-47"
 */
export function buildEquipoSlug(item: Pick<Equipment, "id" | "brand" | "name">): string {
  const slug = slugify(`${item.brand} ${item.name}`);
  if (!slug) return String(item.id);
  return `${slug}-${item.id}`;
}

/**
 * Extrae el ID numérico de una URL slug-id.
 * Devuelve null si no se puede parsear (mal armada).
 *
 * @example
 * extractIdFromSlug("sony-fx3-cuerpo-47") // → "47"
 * extractIdFromSlug("47")                  // → "47"
 * extractIdFromSlug("sony-fx3")            // → null
 */
export function extractIdFromSlug(slug: string): string | null {
  if (/^\d+$/.test(slug)) return slug;
  const m = slug.match(/-(\d+)$/);
  return m ? m[1] : null;
}
