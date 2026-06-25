/**
 * Utilidades YouTube para el sistema de media (F0c).
 *
 * extractYoutubeId: extrae el video_id de cualquier forma de URL YouTube.
 * youtubeNocookieUrl: URL de embed sin cookies (youtube-nocookie.com).
 */

/** Regex de video_id de YouTube: exactamente 11 chars [A-Za-z0-9_-]. */
const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;

/**
 * Extrae el video_id de una URL de YouTube o lo devuelve si ya es un ID.
 * Devuelve null si el input es inválido.
 */
export function extractYoutubeId(urlOrId: string | null | undefined): string | null {
  const s = (urlOrId ?? "").trim();
  if (!s) return null;

  // ID directo
  if (VIDEO_ID_RE.test(s)) return s;

  try {
    const u = new URL(s);
    const host = u.hostname.replace(/^www\./, "");

    if (host === "youtu.be") {
      const vid = u.pathname.slice(1, 12);
      return VIDEO_ID_RE.test(vid) ? vid : null;
    }

    if (host.includes("youtube.com")) {
      // /watch?v=ID
      const v = u.searchParams.get("v");
      if (v && VIDEO_ID_RE.test(v)) return v;
      // /embed/ID, /shorts/ID, /v/ID
      const m = u.pathname.match(/\/(?:embed|shorts|v)\/([A-Za-z0-9_-]{11})/);
      if (m) return m[1];
    }
  } catch {
    /* URL inválida */
  }
  return null;
}

/** URL de embed con youtube-nocookie.com (sin cookies hasta que el usuario hace play). */
export function youtubeNocookieUrl(videoId: string): string {
  return `https://www.youtube-nocookie.com/embed/${videoId}`;
}

/** URL pública del thumbnail del video (para img de preview antes de cargar el iframe). */
export function youtubeThumbnailUrl(videoId: string): string {
  return `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
}
