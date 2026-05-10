/**
 * Origen canónico del frontend Lovable para autenticación.
 *
 * Google OAuth administrado por Lovable sólo funciona desde dominios Lovable
 * (preview *.lovable.app / *.lovableproject.com o el dominio publicado).
 * Railway (backend FastAPI) NO sirve `/~oauth/initiate`, por eso el login
 * siempre debe iniciar desde este origen.
 *
 * Cuando publiques o conectes un dominio propio, actualizá `CANONICAL_ORIGIN`
 * o seteá VITE_PUBLIC_APP_ORIGIN.
 */

const ENV_ORIGIN = (import.meta.env.VITE_PUBLIC_APP_ORIGIN as string | undefined)?.replace(/\/$/, "");

const CANONICAL_ORIGIN = "https://id-preview--cd1cc884-084b-435b-8af0-167f25bc78ca.lovable.app";

/** True si el host actual soporta el broker OAuth de Lovable. */
export function isLovableHost(hostname: string): boolean {
  return (
    hostname.endsWith(".lovable.app") ||
    hostname.endsWith(".lovableproject.com") ||
    hostname === "localhost" ||
    hostname === "127.0.0.1"
  );
}

/**
 * Origen a usar para el flujo OAuth. Si ya estamos en un host Lovable válido
 * usamos el origen actual (preview / publicado / custom domain). Si no, caemos
 * al canónico para evitar que Railway intente manejar `/~oauth/initiate`.
 */
export function getAppOrigin(): string {
  if (ENV_ORIGIN) return ENV_ORIGIN;
  if (typeof window !== "undefined" && isLovableHost(window.location.hostname)) {
    return window.location.origin;
  }
  return CANONICAL_ORIGIN;
}

/** @deprecated usar getAppOrigin() para respetar el host actual. */
export const APP_ORIGIN = ENV_ORIGIN || CANONICAL_ORIGIN;
