/**
 * cuit.ts — validación de formato de CUIT/CUIL (dígito verificador mod-11) +
 * verificación contra el padrón de ARCA.
 *
 * Espeja el algoritmo de `identity/anchor.py::cuil_valido` en el backend —
 * ahí es donde REALMENTE se hace cumplir (esto es solo feedback inmediato
 * mientras se tipea, no reemplaza esa validación). El checksum de 11 dígitos
 * es el mismo para CUIT (facturación) y CUIL (identidad, RENAPER) — números
 * distintos, mismo algoritmo.
 */

import { authedPostJson } from "./authedFetch";
import type { PerfilImpuestos } from "./iva";

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

export type VerificacionCuit =
  | {
      encontrado: true;
      cuit: string;
      perfil_impuestos: PerfilImpuestos;
      razon_social: string;
      domicilio_fiscal: string;
    }
  | { encontrado: false; motivo: string };

/**
 * Verifica el CUIT contra el padrón de ARCA (`POST /api/cliente/facturacion/
 * verificar-cuit`) — como Didit con RENAPER: si ARCA lo confirma, la
 * condición IVA/razón social/domicilio quedan persistidas en la cuenta al
 * toque (no hace falta que el cliente los autocomplete a mano). Best-effort:
 * nunca tira — `encontrado: false` con el motivo real es la vía normal de
 * "no se pudo", no una excepción.
 */
export async function verificarCuitArca(cuit: string): Promise<VerificacionCuit> {
  return authedPostJson<VerificacionCuit>("/api/cliente/facturacion/verificar-cuit", { cuit });
}
