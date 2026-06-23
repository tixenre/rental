/**
 * search/normalize.ts — normalización + matching de búsqueda (lado cliente).
 *
 * ESPEJO del motor backend (`backend/busqueda`). El catálogo público filtra en
 * el navegador (instantáneo, ideal mobile) en vez de pegarle al server; para que
 * se comporte IGUAL que la búsqueda del back-office, comparte estas reglas de
 * normalización. El corpus `backend/tests/data/normalizacion_corpus.json` es el
 * contrato: el test de Python lo enforce y esta implementación lo espeja. Si
 * cambiás una regla, actualizá las DOS (Python y este archivo) y el corpus.
 *
 * Reglas (idénticas a `backend/busqueda/normalizar.py`):
 *   1. minúsculas
 *   2. sin acentos/diacríticos — "Batería" → "bateria"
 *   3. todo lo no-alfanumérico pasa a espacio — "A7-III" → "a7 iii", "f/2.8" → "f 2 8"
 *   4. espacios colapsados y recortados
 *
 * Antes esta lógica estaba copiada (con variantes) en `index.tsx`,
 * `CatalogoMovil.tsx` y otros lugares. Esta es la fuente única del front.
 */

/** Normaliza un término a su forma canónica de búsqueda. */
export function normalizar(texto: string): string {
  return (texto ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // diacríticos combinantes
    .replace(/[^a-z0-9]+/g, " ") // no-alfanumérico → espacio (guiones, puntos…)
    .trim()
    .replace(/\s+/g, " ");
}

/** Normaliza y parte en tokens (palabras). */
export function tokenizar(texto: string): string[] {
  const norm = normalizar(texto);
  return norm ? norm.split(" ") : [];
}

/** Campos buscables de un ítem. `nombre` pondera el ranking (un match al inicio
 *  del nombre va arriba); `extra` (marca, categoría, specs, descripción) entra
 *  al match pero pesa menos. */
export interface CamposBusqueda {
  nombre: string;
  extra?: string;
}

/**
 * Puntúa un ítem ya normalizado. Devuelve -1 si NO matchea (algún token falta).
 * Pesos discretos: prefijo del nombre > contiene en el nombre > prefijo/contiene
 * en el resto. Replica el espíritu del ranking del backend (el mejor match
 * primero, consistente).
 */
function puntuar(nombreNorm: string, haystack: string, qnorm: string, tokens: string[]): number {
  for (const t of tokens) if (!haystack.includes(t)) return -1; // AND entre tokens
  let score = 0;
  if (nombreNorm.startsWith(qnorm)) score += 100;
  else if (nombreNorm.includes(qnorm)) score += 50;
  if (haystack.startsWith(qnorm)) score += 20;
  else if (haystack.includes(qnorm)) score += 10;
  return score;
}

/**
 * Filtra y ORDENA por relevancia. Query vacía → devuelve los ítems sin tocar
 * (conserva el orden original, p.ej. popularidad). El orden es estable: ante
 * igual score, respeta el orden de entrada.
 */
export function filtrarOrdenar<T>(
  items: T[],
  query: string,
  campos: (item: T) => CamposBusqueda,
): T[] {
  const qnorm = normalizar(query);
  if (!qnorm) return items;
  const tokens = qnorm.split(" ").filter(Boolean);

  const scored: { item: T; s: number; i: number }[] = [];
  items.forEach((item, i) => {
    const { nombre, extra } = campos(item);
    const nombreNorm = normalizar(nombre);
    const haystack = normalizar(`${nombre} ${extra ?? ""}`);
    const s = puntuar(nombreNorm, haystack, qnorm, tokens);
    if (s >= 0) scored.push({ item, s, i });
  });
  scored.sort((a, b) => b.s - a.s || a.i - b.i);
  return scored.map((x) => x.item);
}
