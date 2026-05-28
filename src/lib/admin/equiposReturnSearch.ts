/**
 * Persistencia del estado de filtros/búsqueda/sort de /admin/equipos cuando
 * el admin entra a editar o crear un equipo, para restaurarlo al volver.
 *
 * sessionStorage en vez de URL search params del editor: evita ensuciar la
 * URL de edición con un blob JSON, no necesita schema nuevo en el router, y
 * es ámbito tab — suficiente para este flujo.
 */

const KEY = "admin:equipos:returnSearch";

/** Guardar el search actual antes de navegar al editor. */
export function stashEquiposReturnSearch(search: unknown): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(search));
  } catch {
    /* sin blocker — si falla, la restauración se omite y volvemos sin filtros */
  }
}

/** Leer y limpiar el search guardado. Devuelve {} si no hay nada. */
export function popEquiposReturnSearch(): Record<string, unknown> {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return {};
    sessionStorage.removeItem(KEY);
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return {};
  }
}
