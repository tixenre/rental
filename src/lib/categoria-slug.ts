/**
 * categoria-slug.ts — Helper para slugificar nombres de categorías.
 *
 * Reglas:
 * - Lowercase
 * - Sin acentos
 * - Espacios y caracteres especiales → "-"
 * - Trim guiones extra
 *
 * Mantener sincronizado con el helper backend en `seo.py:_build_categoria_slug`.
 */

export function buildCategoriaSlug(nombre: string): string {
  return nombre
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Inverso lazy: matchea un slug contra una lista de nombres. */
export function findCategoriaBySlug<T extends { nombre: string }>(
  slug: string,
  categorias: T[],
): T | undefined {
  const target = slug.toLowerCase();
  return categorias.find((c) => buildCategoriaSlug(c.nombre) === target);
}
