/**
 * Helpers para click-to-chat de WhatsApp via wa.me.
 *
 * Estrategia:
 * - Normalizar teléfonos: quitar caracteres no numéricos, agregar prefijo
 *   internacional (+54 9 para Argentina) si falta.
 * - Construir URL `https://wa.me/<numero>?text=<mensaje>`.
 *
 * NO usamos libphonenumber-js (pesado, ~80KB). Validación simple optimizada
 * para Argentina — el 99% de los clientes son AR.
 */

/**
 * Limpia y normaliza un teléfono al formato internacional sin signos.
 * Devuelve `null` si no se puede parsear (string vacío, sin dígitos suficientes).
 *
 * Reglas para Argentina:
 * - "11 1234-5678" → "5491112345678"   (asume celular, agrega 54 9 + área 11)
 * - "0223 555 5555" → "542235555555"   (remueve 0 inicial, agrega 54)
 * - "+54 9 223 555-5555" → "5492235555555"
 * - "223 555 5555" → "542235555555"   (agrega 54 si tiene 10 dígitos = código área + número)
 */
export function normalizePhone(raw: string | null | undefined): string | null {
  if (!raw) return null;

  // Sacar todo lo que no sea dígito, salvo + al inicio.
  const startsWithPlus = raw.trim().startsWith("+");
  let digits = raw.replace(/[^0-9]/g, "");
  if (!digits) return null;

  // Sacar 0 inicial (formato local AR).
  if (digits.startsWith("0")) {
    digits = digits.slice(1);
  }

  // Si vino con + o ya empieza con 54, está OK.
  if (startsWithPlus || digits.startsWith("54")) {
    return digits;
  }

  // Argentina: ~10 dígitos (código área 2-3 dígitos + número 6-8).
  // Agregamos prefijo 54 (sin 9 — wa.me lo maneja).
  if (digits.length >= 10 && digits.length <= 12) {
    return "54" + digits;
  }

  // Demasiado corto/largo → no se puede parsear con confianza.
  return null;
}

/**
 * Construye URL de wa.me para abrir chat con número + mensaje opcional.
 *
 * @returns null si el teléfono no es parseable. Caller debe deshabilitar el botón.
 */
export function whatsappLink(opts: {
  phone: string | null | undefined;
  message?: string;
}): string | null {
  const normalized = normalizePhone(opts.phone);
  if (!normalized) return null;

  const base = `https://wa.me/${normalized}`;
  if (!opts.message) return base;
  return `${base}?text=${encodeURIComponent(opts.message)}`;
}

/**
 * Display human-readable del teléfono ya normalizado.
 * "5491112345678" → "+54 9 11 1234-5678"
 *
 * Si no se puede formatear, devuelve el normalizado tal cual con + al inicio.
 */
export function formatPhoneDisplay(phone: string | null | undefined): string {
  const norm = normalizePhone(phone);
  if (!norm) return phone ?? "";

  // Formato Argentina: +54 9 <2-4 dígitos área> <4 dígitos> <4 dígitos>
  if (norm.startsWith("54")) {
    const rest = norm.slice(2);
    // Si empieza con 9 (celular), separamos el 9
    if (rest.startsWith("9") && rest.length >= 11) {
      const num = rest.slice(1);
      // Heurística: si los primeros 2 dígitos son 11 (CABA) o 15 (?), área de 2.
      // Para Mar del Plata (223) o Buenos Aires sin CABA → área de 3.
      const areaLen = num.startsWith("11") ? 2 : 3;
      const area = num.slice(0, areaLen);
      const restNum = num.slice(areaLen);
      const half = Math.ceil(restNum.length / 2);
      return `+54 9 ${area} ${restNum.slice(0, half)}-${restNum.slice(half)}`;
    }
    // Sin 9 (fijo): +54 <área> <número>
    if (rest.length >= 10) {
      const areaLen = rest.startsWith("11") ? 2 : 3;
      const area = rest.slice(0, areaLen);
      const restNum = rest.slice(areaLen);
      const half = Math.ceil(restNum.length / 2);
      return `+54 ${area} ${restNum.slice(0, half)}-${restNum.slice(half)}`;
    }
  }

  return "+" + norm;
}
