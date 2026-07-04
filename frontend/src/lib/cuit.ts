/**
 * cuit.ts — validación de formato de CUIT/CUIL (dígito verificador mod-11).
 *
 * Espeja el algoritmo de `identity/anchor.py::cuil_valido` en el backend —
 * ahí es donde REALMENTE se hace cumplir (esto es solo feedback inmediato
 * mientras se tipea, no reemplaza esa validación). El checksum de 11 dígitos
 * es el mismo para CUIT (facturación) y CUIL (identidad, RENAPER) — números
 * distintos, mismo algoritmo.
 */

const PESOS = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];

/** Deja solo los 11 dígitos de un CUIT/CUIL. null si no quedan exactamente 11. */
export function normalizarCuit(raw: string): string | null {
  const digitos = raw.replace(/\D/g, "");
  return digitos.length === 11 ? digitos : null;
}

/** true si el dígito verificador (mod-11) del CUIT/CUIL es correcto. */
export function cuitValido(raw: string): boolean {
  const n = normalizarCuit(raw);
  if (!n) return false;
  const suma = n
    .slice(0, 10)
    .split("")
    .reduce((acc, d, i) => acc + Number(d) * PESOS[i], 0);
  const resto = 11 - (suma % 11);
  const verificador = resto === 11 ? 0 : resto === 10 ? 9 : resto;
  return verificador === Number(n[10]);
}
