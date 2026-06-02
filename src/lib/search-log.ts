/**
 * search-log.ts — registro de búsquedas del catálogo público (analítica interna).
 *
 * El buscador filtra en el front; este módulo manda el término "asentado" al
 * backend para saber qué busca la gente (y qué buscan sin encontrar).
 *
 * **Lógica ÚNICA de logging acá.** Hay DOS superficies de búsqueda separadas
 * (catálogo desktop `index.tsx` y mobile `CatalogoMovil.tsx`, cada una con su
 * propio estado `query`/`filtered`); ambas registran a través de esta misma
 * función `logSearch` — no se duplica la decisión de cuándo/cómo enviar.
 *
 * - **Debounce**: solo registra cuando el usuario deja de tipear (~900ms), no
 *   en cada tecla — evita guardar "s", "so", "son", "sony" por cada keystroke.
 * - **Dedupe**: no re-registra el mismo término asentado de corrido (re-renders).
 * - **Best-effort**: si el POST falla, se ignora; nunca rompe el catálogo.
 *
 * Nota: `timer`/`ultimoEnviado` son estado a nivel de módulo (compartido). Es
 * correcto porque desktop y mobile no conviven en pantalla (el catálogo renderiza
 * una u otra según el viewport), nunca las dos a la vez.
 *
 * El crudo se guarda tal cual en el backend; la normalización (agrupar variantes)
 * vive allá. Acá solo decidimos cuándo mandar.
 */

import { apiLogSearch } from "@/lib/api";

const DEBOUNCE_MS = 900;
const MIN_LEN = 2;

let timer: ReturnType<typeof setTimeout> | undefined;
let ultimoEnviado = "";

/** Encola el registro de una búsqueda. Llamar libremente en cada cambio de
 *  query; el debounce + dedupe internos deciden si y cuándo se manda. */
export function logSearch(query: string, resultCount: number): void {
  const q = query.trim();
  if (timer) clearTimeout(timer);
  if (q.length < MIN_LEN) return;

  timer = setTimeout(() => {
    const clave = q.toLowerCase();
    if (clave === ultimoEnviado) return; // mismo término asentado → no duplicar
    ultimoEnviado = clave;
    apiLogSearch(q, Math.max(0, resultCount)).catch(() => {
      /* best-effort: la analítica no puede romper la búsqueda */
    });
  }, DEBOUNCE_MS);
}
