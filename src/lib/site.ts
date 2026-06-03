/**
 * URL pública canónica del sitio — fuente ÚNICA para el front.
 *
 * Antes el dominio estaba hardcodeado como `const SITE_URL = "..."` en ~6
 * archivos (rutas + `index.html`), lo que dejó el dominio desincronizado
 * cuando cambió (se compartía `ramblarental.com` en vez del canónico). Ahora
 * todo el front importa de acá. Override por ambiente con `VITE_SITE_URL`
 * (gana, misma convención que `VITE_API_URL` / `VITE_GA4_ID`).
 *
 * El backend tiene su propia fuente única (`config.SITE_URL`, env `SITE_URL`)
 * usada por sitemap y mails — mantener ambos alineados. Dominio canónico de
 * prod: https://www.ramblarental.com.ar
 */
export const SITE_URL = (
  (import.meta.env.VITE_SITE_URL as string | undefined) ?? "https://www.ramblarental.com.ar"
).replace(/\/+$/, "");
