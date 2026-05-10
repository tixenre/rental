/**
 * Origen canónico del frontend Lovable.
 *
 * El flujo de Google OAuth administrado por Lovable sólo funciona desde
 * dominios de Lovable (preview *.lovable.app / *.lovableproject.com o el
 * dominio publicado). Si la app se sirve desde otro host (por ejemplo el
 * backend FastAPI en Railway), el endpoint `/~oauth/initiate` no existe y
 * tira 404. Antes de iniciar OAuth, redirigimos al usuario a este origen.
 *
 * Cuando publiques la app y/o conectes un dominio propio, actualizá esta
 * constante (o agregá VITE_PUBLIC_APP_ORIGIN en .env).
 */

const ENV_ORIGIN = (import.meta.env.VITE_PUBLIC_APP_ORIGIN as string | undefined)?.replace(/\/$/, "");

const FALLBACK_ORIGIN = "https://id-preview--cd1cc884-084b-435b-8af0-167f25bc78ca.lovable.app";

export const APP_ORIGIN = ENV_ORIGIN || FALLBACK_ORIGIN;

/** True si el host actual soporta el broker OAuth de Lovable. */
export function isLovableHost(hostname: string): boolean {
  return (
    hostname.endsWith(".lovable.app") ||
    hostname.endsWith(".lovableproject.com") ||
    hostname === "localhost" ||
    hostname === "127.0.0.1"
  );
}
